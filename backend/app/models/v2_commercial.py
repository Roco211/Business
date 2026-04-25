from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.services.v2_time import utc_now_naive


class V2Supplier(Base):
    __tablename__ = "v2_suppliers"

    supplier_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("v2_tenants.tenant_id"), nullable=False, index=True)
    shop_id: Mapped[str] = mapped_column(ForeignKey("v2_shops.shop_id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False, default=utc_now_naive)
    updated_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False, default=utc_now_naive)


class V2PurchaseOrder(Base):
    __tablename__ = "v2_purchase_orders"

    purchase_order_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("v2_tenants.tenant_id"), nullable=False, index=True)
    shop_id: Mapped[str] = mapped_column(ForeignKey("v2_shops.shop_id"), nullable=False, index=True)
    supplier_id: Mapped[str] = mapped_column(ForeignKey("v2_suppliers.supplier_id"), nullable=False, index=True)
    order_no: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="received")
    total_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_by_account_id: Mapped[str] = mapped_column(ForeignKey("v2_accounts.account_id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False, default=utc_now_naive)
    updated_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False, default=utc_now_naive)


class V2PurchaseOrderLine(Base):
    __tablename__ = "v2_purchase_order_lines"

    purchase_order_line_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    purchase_order_id: Mapped[str] = mapped_column(ForeignKey("v2_purchase_orders.purchase_order_id"), nullable=False, index=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("v2_tenants.tenant_id"), nullable=False, index=True)
    shop_id: Mapped[str] = mapped_column(ForeignKey("v2_shops.shop_id"), nullable=False, index=True)
    inventory_item_id: Mapped[str] = mapped_column(ForeignKey("v2_inventory_items.inventory_item_id"), nullable=False, index=True)
    item_name: Mapped[str] = mapped_column(String(160), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    unit: Mapped[str] = mapped_column(String(24), nullable=False)
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    line_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False, default=utc_now_naive)


class V2Customer(Base):
    __tablename__ = "v2_customers"

    customer_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("v2_tenants.tenant_id"), nullable=False, index=True)
    shop_id: Mapped[str] = mapped_column(ForeignKey("v2_shops.shop_id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False, default=utc_now_naive)
    updated_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False, default=utc_now_naive)


class V2FinanceTransaction(Base):
    __tablename__ = "v2_finance_transactions"

    finance_transaction_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("v2_tenants.tenant_id"), nullable=False, index=True)
    shop_id: Mapped[str] = mapped_column(ForeignKey("v2_shops.shop_id"), nullable=False, index=True)
    transaction_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    direction: Mapped[str] = mapped_column(String(16), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    source_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    source_id: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    counterparty_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_by_account_id: Mapped[str] = mapped_column(ForeignKey("v2_accounts.account_id"), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False, default=utc_now_naive)


class V2SalesReturn(Base):
    __tablename__ = "v2_sales_returns"

    sales_return_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("v2_tenants.tenant_id"), nullable=False, index=True)
    shop_id: Mapped[str] = mapped_column(ForeignKey("v2_shops.shop_id"), nullable=False, index=True)
    sales_order_id: Mapped[str] = mapped_column(ForeignKey("v2_sales_orders.sales_order_id"), nullable=False, index=True)
    sales_order_line_id: Mapped[str] = mapped_column(ForeignKey("v2_sales_order_lines.sales_order_line_id"), nullable=False, index=True)
    inventory_item_id: Mapped[str] = mapped_column(ForeignKey("v2_inventory_items.inventory_item_id"), nullable=False, index=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    refund_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_by_account_id: Mapped[str] = mapped_column(ForeignKey("v2_accounts.account_id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False, default=utc_now_naive)
