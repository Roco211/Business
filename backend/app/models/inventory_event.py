from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class InventoryEvent(Base):
    __tablename__ = "inventory_events"

    inventory_event_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    shop_id: Mapped[str] = mapped_column(ForeignKey("shops.shop_id"), nullable=False)
    item_id: Mapped[str] = mapped_column(ForeignKey("inventory_items.item_id"), nullable=False)
    event_type: Mapped[str] = mapped_column(String(24), nullable=False)
    quantity_delta: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    quantity_after: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    unit: Mapped[str] = mapped_column(String(24), nullable=False)
    price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    task_run_id: Mapped[str | None] = mapped_column(ForeignKey("task_runs.task_run_id"), nullable=True)
    created_by: Mapped[str] = mapped_column(String(40), nullable=False)
    reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False)
