from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class PilotControl(Base):
    __tablename__ = "pilot_controls"
    __table_args__ = (
        CheckConstraint(
            "cutover_mode IN ('closed', 'shadow', 'open')",
            name="ck_pilot_controls_cutover_mode",
        ),
    )

    shop_id: Mapped[str] = mapped_column(ForeignKey("shops.shop_id"), primary_key=True)
    trial_provider_profile: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    approved_calibration_artifact_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    approved_calibration_report_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    cutover_mode: Mapped[str] = mapped_column(String(24), nullable=False, default="closed")
    opened_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
    opened_by_actor_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
    closed_by_actor_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    last_preflight_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
    last_preflight_status: Mapped[str | None] = mapped_column(String(24), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
