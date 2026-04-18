from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.services.v2_time import utc_now_naive


class V2SessionStreamEvent(Base):
    __tablename__ = "v2_session_stream_events"
    __table_args__ = (
        UniqueConstraint("session_id", "seq", name="uq_v2_session_stream_events_session_seq"),
        Index("ix_v2_session_stream_events_session_id_seq", "session_id", "seq"),
    )

    event_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("v2_tenants.tenant_id"), nullable=False, index=True)
    shop_id: Mapped[str] = mapped_column(ForeignKey("v2_shops.shop_id"), nullable=False, index=True)
    session_id: Mapped[str] = mapped_column(
        ForeignKey("v2_conversation_sessions.session_id"),
        nullable=False,
        index=True,
    )
    seq: Mapped[int] = mapped_column(nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    task_run_id: Mapped[str | None] = mapped_column(
        ForeignKey("v2_task_runs.task_run_id"),
        nullable=True,
        index=True,
    )
    message_id: Mapped[str | None] = mapped_column(
        ForeignKey("v2_messages.message_id"),
        nullable=True,
        index=True,
    )
    payload_json: Mapped[dict[str, object]] = mapped_column("payload", JSON, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False, default=utc_now_naive)
