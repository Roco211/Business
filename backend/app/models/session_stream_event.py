from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, DateTime, ForeignKey, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class SessionStreamEvent(Base):
    __tablename__ = "session_stream_events"

    event_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.session_id"), nullable=False)
    seq: Mapped[int] = mapped_column(BigInteger, nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    task_run_id: Mapped[str | None] = mapped_column(ForeignKey("task_runs.task_run_id"), nullable=True)
    message_id: Mapped[str | None] = mapped_column(ForeignKey("messages.message_id"), nullable=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False)

    session = relationship("SessionRecord")
    task_run = relationship("TaskRun")
    message = relationship("Message")
