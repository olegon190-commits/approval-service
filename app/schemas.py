"""Pydantic-схемы запросов и ответов"""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field
from app.models import SourceType, RequestStatus


class CreateApprovalRequest(BaseModel):
    sourceType: SourceType
    sourceId: str = Field(min_length=1)
    title: str = Field(min_length=1, max_length=500)
    description: Optional[str] = Field(default=None, max_length=5000)
    reviewerUserIds: List[str] = Field(default_factory=list)


class ApproveBody(BaseModel):
    comment: Optional[str] = Field(default=None, max_length=2000)


class RejectBody(BaseModel):
    reason: str = Field(min_length=1, max_length=2000)


class CancelBody(BaseModel):
    reason: str = Field(min_length=1, max_length=2000)


class ApprovalRequestOut(BaseModel):
    """Публичный ответ — без секретов, токенов и внутренних данных"""
    id: str
    workspaceId: str
    sourceType: SourceType
    sourceId: str
    title: str
    description: Optional[str]
    reviewerUserIds: List[str]
    status: RequestStatus
    decisionComment: Optional[str]
    decisionReason: Optional[str]
    createdBy: str
    decidedBy: Optional[str]
    createdAt: datetime
    updatedAt: datetime

    @classmethod
    def from_model(cls, m):
        return cls(
            id=m.id,
            workspaceId=m.workspace_id,
            sourceType=m.source_type,
            sourceId=m.source_id,
            title=m.title,
            description=m.description,
            reviewerUserIds=m.reviewer_user_ids or [],
            status=m.status,
            decisionComment=m.decision_comment,
            decisionReason=m.decision_reason,
            createdBy=m.created_by,
            decidedBy=m.decided_by,
            createdAt=m.created_at,
            updatedAt=m.updated_at,
        )


class ApprovalRequestList(BaseModel):
    items: List[ApprovalRequestOut]
    total: int
