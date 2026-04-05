from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class OcrDocument(Base):
    __tablename__ = "ocr_documents"

    ocr_document_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    shop_id: Mapped[str] = mapped_column(ForeignKey("shops.shop_id"), nullable=False)
    task_run_id: Mapped[str | None] = mapped_column(ForeignKey("task_runs.task_run_id"), nullable=True)
    media_id: Mapped[str] = mapped_column(String(40), nullable=False)
    document_type: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    provider_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    raw_text: Mapped[str | None] = mapped_column(String(), nullable=True)
    extracted_fields: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    low_confidence_fields: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False)

    shop = relationship("Shop")
    task_run = relationship("TaskRun")
