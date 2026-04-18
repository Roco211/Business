from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, JSON, String, UniqueConstraint
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
