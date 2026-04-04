from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Alert(Base):
    __tablename__ = "alerts"

    alert_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    shop_id: Mapped[str] = mapped_column(ForeignKey("shops.shop_id"), nullable=False)
    alert_type: Mapped[str] = mapped_column(String(24), nullable=False)
    item_id: Mapped[str] = mapped_column(ForeignKey("inventory_items.item_id"), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    stock: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    threshold: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
