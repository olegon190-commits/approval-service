"""Роуты согласования контента"""
from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session
from app.database import get_db
from app.auth import get_auth, AuthContext
from app import models, schemas
from app.models import RequestStatus, FINAL_STATUSES

router = APIRouter(tags=["approval-requests"])


def _log(db: Session, workspace_id: str, request_id: str, actor: str, action: str, details: dict = None):
    """Аудит-лог: кто и что изменил"""
    db.add(models.AuditLog(
        workspace_id=workspace_id,
        request_id=request_id,
        actor_user_id=actor,
        action=action,
        details=details or {},
    ))


def _emit(db: Session, workspace_id: str, event_type: str, payload: dict):
    """Событие в outbox для будущих интеграций"""
    db.add(models.OutboxEvent(
        workspace_id=workspace_id,
        event_type=event_type,
        payload=payload,
    ))


def _get_request_or_404(db: Session, workspace_id: str, request_id: str) -> models.ApprovalRequest:
    """Достаём заявку строго внутри workspace — изоляция данных"""
    req = db.query(models.ApprovalRequest).filter(
        models.ApprovalRequest.id == request_id,
        models.ApprovalRequest.workspace_id == workspace_id,
    ).first()
    if not req:
        raise HTTPException(status_code=404, detail="Approval request not found")
    return req


def _check_workspace(auth: AuthContext, workspace_id: str):
    """Пользователь может работать только со своим workspace"""
    if auth.workspace_id != workspace_id:
        raise HTTPException(status_code=403, detail="Workspace access denied")


def _ensure_not_final(req: models.ApprovalRequest):
    """После финального решения статус менять нельзя"""
    if req.status in FINAL_STATUSES:
        raise HTTPException(
            status_code=409,
            detail=f"Request already in final status: {req.status.value}",
        )


@router.post("/workspaces/{workspace_id}/approval-requests", response_model=schemas.ApprovalRequestOut, status_code=201)
def create_request(
    workspace_id: str,
    body: schemas.CreateApprovalRequest,
    auth: AuthContext = Depends(get_auth),
    db: Session = Depends(get_db),
    idempotency_key: str = Header(None, alias="Idempotency-Key"),
):
    _check_workspace(auth, workspace_id)
    auth.require("approval:create")

    if idempotency_key:
        existing = db.query(models.ApprovalRequest).filter(
            models.ApprovalRequest.workspace_id == workspace_id,
            models.ApprovalRequest.idempotency_key == idempotency_key,
        ).first()
        if existing:
            return schemas.ApprovalRequestOut.from_model(existing)

    req = models.ApprovalRequest(
        workspace_id=workspace_id,
        source_type=body.sourceType,
        source_id=body.sourceId,
        title=body.title,
        description=body.description,
        reviewer_user_ids=body.reviewerUserIds,
        created_by=auth.user_id,
        idempotency_key=idempotency_key,
    )
    db.add(req)
    db.flush()

    _log(db, workspace_id, req.id, auth.user_id, "created", {"title": body.title})
    _emit(db, workspace_id, "approval_request.created", {
        "requestId": req.id,
        "sourceType": body.sourceType.value,
        "sourceId": body.sourceId,
    })

    db.commit()
    db.refresh(req)
    return schemas.ApprovalRequestOut.from_model(req)


@router.get("/workspaces/{workspace_id}/approval-requests", response_model=schemas.ApprovalRequestList)
def list_requests(
    workspace_id: str,
    auth: AuthContext = Depends(get_auth),
    db: Session = Depends(get_db),
):
    _check_workspace(auth, workspace_id)
    auth.require("approval:read")

    q = db.query(models.ApprovalRequest).filter(
        models.ApprovalRequest.workspace_id == workspace_id
    ).order_by(models.ApprovalRequest.created_at.desc())

    items = q.all()
    return schemas.ApprovalRequestList(
        items=[schemas.ApprovalRequestOut.from_model(r) for r in items],
        total=len(items),
    )


@router.get("/workspaces/{workspace_id}/approval-requests/{request_id}", response_model=schemas.ApprovalRequestOut)
def get_request(
    workspace_id: str,
    request_id: str,
    auth: AuthContext = Depends(get_auth),
    db: Session = Depends(get_db),
):
    _check_workspace(auth, workspace_id)
    auth.require("approval:read")
    req = _get_request_or_404(db, workspace_id, request_id)
    return schemas.ApprovalRequestOut.from_model(req)


@router.post("/workspaces/{workspace_id}/approval-requests/{request_id}/approve", response_model=schemas.ApprovalRequestOut)
def approve_request(
    workspace_id: str,
    request_id: str,
    body: schemas.ApproveBody,
    auth: AuthContext = Depends(get_auth),
    db: Session = Depends(get_db),
):
    _check_workspace(auth, workspace_id)
    auth.require("approval:decide")
    req = _get_request_or_404(db, workspace_id, request_id)
    _ensure_not_final(req)

    req.status = RequestStatus.approved
    req.decision_comment = body.comment
    req.decided_by = auth.user_id

    _log(db, workspace_id, req.id, auth.user_id, "approved", {"comment": body.comment})
    _emit(db, workspace_id, "approval_request.approved", {"requestId": req.id})

    db.commit()
    db.refresh(req)
    return schemas.ApprovalRequestOut.from_model(req)


@router.post("/workspaces/{workspace_id}/approval-requests/{request_id}/reject", response_model=schemas.ApprovalRequestOut)
def reject_request(
    workspace_id: str,
    request_id: str,
    body: schemas.RejectBody,
    auth: AuthContext = Depends(get_auth),
    db: Session = Depends(get_db),
):
    _check_workspace(auth, workspace_id)
    auth.require("approval:decide")
    req = _get_request_or_404(db, workspace_id, request_id)
    _ensure_not_final(req)

    req.status = RequestStatus.rejected
    req.decision_reason = body.reason
    req.decided_by = auth.user_id

    _log(db, workspace_id, req.id, auth.user_id, "rejected", {"reason": body.reason})
    _emit(db, workspace_id, "approval_request.rejected", {"requestId": req.id})

    db.commit()
    db.refresh(req)
    return schemas.ApprovalRequestOut.from_model(req)


@router.post("/workspaces/{workspace_id}/approval-requests/{request_id}/cancel", response_model=schemas.ApprovalRequestOut)
def cancel_request(
    workspace_id: str,
    request_id: str,
    body: schemas.CancelBody,
    auth: AuthContext = Depends(get_auth),
    db: Session = Depends(get_db),
):
    _check_workspace(auth, workspace_id)
    auth.require("approval:cancel")
    req = _get_request_or_404(db, workspace_id, request_id)
    _ensure_not_final(req)

    req.status = RequestStatus.cancelled
    req.decision_reason = body.reason
    req.decided_by = auth.user_id

    _log(db, workspace_id, req.id, auth.user_id, "cancelled", {"reason": body.reason})
    _emit(db, workspace_id, "approval_request.cancelled", {"requestId": req.id})

    db.commit()
    db.refresh(req)
    return schemas.ApprovalRequestOut.from_model(req)
