from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Shop(Base):
    __tablename__ = "shops"

    shop_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    owner_name: Mapped[str] = mapped_column(String(80), nullable=False)
    industry: Mapped[str] = mapped_column(String(32), nullable=False)
    locale: Mapped[str] = mapped_column(String(16), nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False)
    require_price_confirmation: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    require_new_item_confirmation: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    low_confidence_threshold: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    default_low_stock_threshold: Mapped[Decimal | None] = mapped_column(Numeric(12, 3), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False)
