from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Confirmation(Base):
    __tablename__ = "confirmations"

    confirmation_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    task_run_id: Mapped[str] = mapped_column(ForeignKey("task_runs.task_run_id"), nullable=False, unique=True)
    confirmation_type: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    fields: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    requested_by_employee_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    resolution_payload: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    approved_by_actor_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)

    task_run = relationship("TaskRun")
