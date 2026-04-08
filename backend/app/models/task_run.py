from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class TaskRun(Base):
    __tablename__ = "task_runs"

    task_run_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.session_id"), nullable=False)
    source_message_id: Mapped[str] = mapped_column(ForeignKey("messages.message_id"), nullable=False)
    task_type: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    assigned_employee_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    result_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)

    session = relationship("SessionRecord")
    source_message = relationship("Message")
