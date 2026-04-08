from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ShopMembership(Base):
    __tablename__ = "shop_memberships"
    __table_args__ = (UniqueConstraint("shop_id", "actor_id", name="uq_shop_memberships_shop_actor"),)

    membership_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    shop_id: Mapped[str] = mapped_column(ForeignKey("shops.shop_id"), nullable=False, index=True)
    actor_id: Mapped[str] = mapped_column(ForeignKey("owner_accounts.actor_id"), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="owner")
    is_default_shop: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False)
