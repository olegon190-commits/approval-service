"""Модели данных approval-service"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, JSON, Enum as SAEnum, Index
from app.database import Base
import enum


def gen_uuid():
    return str(uuid.uuid4())


def utcnow():
    return datetime.now(timezone.utc)


class SourceType(str, enum.Enum):
    publication = "publication"
    scenario = "scenario"
    edit = "edit"
    external = "external"


class RequestStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"
    cancelled = "cancelled"


FINAL_STATUSES = {RequestStatus.approved, RequestStatus.rejected, RequestStatus.cancelled}


class ApprovalRequest(Base):
    __tablename__ = "approval_requests"

    id = Column(String, primary_key=True, default=gen_uuid)
    workspace_id = Column(String, nullable=False, index=True)
    source_type = Column(SAEnum(SourceType), nullable=False)
    source_id = Column(String, nullable=False)
    title = Column(String, nullable=False)
    description = Column(String, nullable=True)
    reviewer_user_ids = Column(JSON, nullable=False, default=list)
    status = Column(SAEnum(RequestStatus), nullable=False, default=RequestStatus.pending)
    decision_comment = Column(String, nullable=True)
    decision_reason = Column(String, nullable=True)
    created_by = Column(String, nullable=False)
    decided_by = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    idempotency_key = Column(String, nullable=True)

    __table_args__ = (
        Index("ix_workspace_idempotency", "workspace_id", "idempotency_key", unique=False),
    )


class AuditLog(Base):
    """След каждого изменения: кто и что изменил"""
    __tablename__ = "audit_logs"

    id = Column(String, primary_key=True, default=gen_uuid)
    workspace_id = Column(String, nullable=False, index=True)
    request_id = Column(String, nullable=False, index=True)
    actor_user_id = Column(String, nullable=False)
    action = Column(String, nullable=False)
    details = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)


class OutboxEvent(Base):
    """События для будущей интеграции с другими сервисами (outbox pattern)"""
    __tablename__ = "outbox_events"

    id = Column(String, primary_key=True, default=gen_uuid)
    workspace_id = Column(String, nullable=False)
    event_type = Column(String, nullable=False)
    payload = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow)
    published_at = Column(DateTime(timezone=True), nullable=True)
