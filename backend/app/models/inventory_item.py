from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class InventoryItem(Base):
    __tablename__ = "inventory_items"

    item_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    shop_id: Mapped[str] = mapped_column(ForeignKey("shops.shop_id"), nullable=False)
    sku: Mapped[str | None] = mapped_column(String(64), nullable=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    category: Mapped[str | None] = mapped_column(String(64), nullable=True)
    barcode: Mapped[str | None] = mapped_column(String(64), nullable=True)
    default_unit: Mapped[str] = mapped_column(String(24), nullable=False)
    current_stock: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False, default=Decimal("0"))
    current_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    low_stock_threshold: Mapped[Decimal | None] = mapped_column(Numeric(12, 3), nullable=True)
    image_media_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False)
