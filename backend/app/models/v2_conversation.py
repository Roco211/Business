from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.services.v2_time import utc_now_naive


class V2ConversationSession(Base):
    __tablename__ = "v2_conversation_sessions"

    session_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("v2_tenants.tenant_id"), nullable=False, index=True)
    shop_id: Mapped[str] = mapped_column(ForeignKey("v2_shops.shop_id"), nullable=False, index=True)
    session_type: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    last_event_seq: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    initiated_by_account_id: Mapped[str] = mapped_column(
        ForeignKey("v2_accounts.account_id"),
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False, default=utc_now_naive)
    updated_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False, default=utc_now_naive)


class V2Message(Base):
    __tablename__ = "v2_messages"
    __table_args__ = (
        UniqueConstraint("session_id", "client_request_id", name="uq_v2_messages_session_client_request"),
    )

    message_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("v2_tenants.tenant_id"), nullable=False, index=True)
    shop_id: Mapped[str] = mapped_column(ForeignKey("v2_shops.shop_id"), nullable=False, index=True)
    session_id: Mapped[str] = mapped_column(
        ForeignKey("v2_conversation_sessions.session_id"),
        nullable=False,
        index=True,
    )
    actor_type: Mapped[str] = mapped_column(String(20), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(40), nullable=False)
    message_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    payload_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    client_request_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False, default=utc_now_naive)


class V2TaskRun(Base):
    __tablename__ = "v2_task_runs"

    task_run_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("v2_tenants.tenant_id"), nullable=False, index=True)
    shop_id: Mapped[str] = mapped_column(ForeignKey("v2_shops.shop_id"), nullable=False, index=True)
    session_id: Mapped[str] = mapped_column(
        ForeignKey("v2_conversation_sessions.session_id"),
        nullable=False,
        index=True,
    )
    source_message_id: Mapped[str] = mapped_column(
        ForeignKey("v2_messages.message_id"),
        nullable=False,
        unique=True,
    )
    intent_type: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    risk_level: Mapped[str] = mapped_column(String(20), nullable=False)
    trace_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    result_summary: Mapped[str | None] = mapped_column(String(255), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False, default=utc_now_naive)
    updated_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False, default=utc_now_naive)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)


class V2TaskDraft(Base):
    __tablename__ = "v2_task_drafts"

    task_draft_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("v2_tenants.tenant_id"), nullable=False, index=True)
    shop_id: Mapped[str] = mapped_column(ForeignKey("v2_shops.shop_id"), nullable=False, index=True)
    task_run_id: Mapped[str] = mapped_column(
        ForeignKey("v2_task_runs.task_run_id"),
        nullable=False,
        unique=True,
    )
    draft_type: Mapped[str] = mapped_column(String(64), nullable=False)
    payload_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    created_by_account_id: Mapped[str] = mapped_column(ForeignKey("v2_accounts.account_id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False, default=utc_now_naive)
    updated_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False, default=utc_now_naive)


class V2Clarification(Base):
    __tablename__ = "v2_clarifications"

    clarification_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("v2_tenants.tenant_id"), nullable=False, index=True)
    shop_id: Mapped[str] = mapped_column(ForeignKey("v2_shops.shop_id"), nullable=False, index=True)
    task_run_id: Mapped[str] = mapped_column(
        ForeignKey("v2_task_runs.task_run_id"),
        nullable=False,
        unique=True,
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    reason_code: Mapped[str] = mapped_column(String(64), nullable=False)
    question_text: Mapped[str] = mapped_column(String(500), nullable=False)
    requested_fields: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    draft_payload: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    answer_payload: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    answered_by_account_id: Mapped[str | None] = mapped_column(
        ForeignKey("v2_accounts.account_id"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False, default=utc_now_naive)
    answered_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)


class V2Confirmation(Base):
    __tablename__ = "v2_confirmations"

    confirmation_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("v2_tenants.tenant_id"), nullable=False, index=True)
    shop_id: Mapped[str] = mapped_column(ForeignKey("v2_shops.shop_id"), nullable=False, index=True)
    task_run_id: Mapped[str] = mapped_column(
        ForeignKey("v2_task_runs.task_run_id"),
        nullable=False,
        unique=True,
    )
    confirmation_type: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    draft_payload: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    approved_by_account_id: Mapped[str | None] = mapped_column(
        ForeignKey("v2_accounts.account_id"),
        nullable=True,
    )
    resolution_payload: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False, default=utc_now_naive)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
