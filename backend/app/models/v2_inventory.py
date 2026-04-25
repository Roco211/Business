from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.services.v2_time import utc_now_naive


class V2InventoryItem(Base):
    __tablename__ = "v2_inventory_items"

    inventory_item_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("v2_tenants.tenant_id"), nullable=False, index=True)
    sku: Mapped[str | None] = mapped_column(String(64), nullable=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    barcode: Mapped[str | None] = mapped_column(String(64), nullable=True)
    default_unit: Mapped[str] = mapped_column(String(24), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False, default=utc_now_naive)
    updated_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False, default=utc_now_naive)


class V2InventoryStockSnapshot(Base):
    __tablename__ = "v2_inventory_stock_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "shop_id",
            "inventory_item_id",
            name="uq_v2_inventory_stock_snapshots_shop_item",
        ),
    )

    snapshot_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("v2_tenants.tenant_id"), nullable=False, index=True)
    shop_id: Mapped[str] = mapped_column(ForeignKey("v2_shops.shop_id"), nullable=False, index=True)
    inventory_item_id: Mapped[str] = mapped_column(
        ForeignKey("v2_inventory_items.inventory_item_id"),
        nullable=False,
        index=True,
    )
    current_quantity: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False, default=0)
    current_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    low_stock_threshold: Mapped[Decimal | None] = mapped_column(Numeric(12, 3), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False, default=utc_now_naive)


class V2InventoryLedgerEvent(Base):
    __tablename__ = "v2_inventory_ledger_events"

    event_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("v2_tenants.tenant_id"), nullable=False, index=True)
    shop_id: Mapped[str] = mapped_column(ForeignKey("v2_shops.shop_id"), nullable=False, index=True)
    inventory_item_id: Mapped[str] = mapped_column(
        ForeignKey("v2_inventory_items.inventory_item_id"),
        nullable=False,
        index=True,
    )
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    quantity_delta: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    quantity_after: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    unit: Mapped[str] = mapped_column(String(24), nullable=False)
    price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    source_id: Mapped[str] = mapped_column(String(40), nullable=False)
    reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_by_account_id: Mapped[str] = mapped_column(ForeignKey("v2_accounts.account_id"), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False, default=utc_now_naive)


class V2StockCheckRecord(Base):
    """库存盘点记录 - 记录每次盘点的实际库存与系统库存对比"""
    __tablename__ = "v2_stock_check_records"

    check_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("v2_tenants.tenant_id"), nullable=False, index=True)
    shop_id: Mapped[str] = mapped_column(ForeignKey("v2_shops.shop_id"), nullable=False, index=True)
    inventory_item_id: Mapped[str] = mapped_column(
        ForeignKey("v2_inventory_items.inventory_item_id"),
        nullable=False,
        index=True,
    )
    system_quantity: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    actual_quantity: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    difference: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    unit: Mapped[str] = mapped_column(String(24), nullable=False)
    check_method: Mapped[str] = mapped_column(String(32), nullable=False, default="manual")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_by_account_id: Mapped[str] = mapped_column(ForeignKey("v2_accounts.account_id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False, default=utc_now_naive)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
