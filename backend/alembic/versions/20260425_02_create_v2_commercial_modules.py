from alembic import op
import sqlalchemy as sa


revision = "20260425_02"
down_revision = "20260425_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "v2_suppliers",
        sa.Column("supplier_id", sa.String(length=40), primary_key=True),
        sa.Column("tenant_id", sa.String(length=40), sa.ForeignKey("v2_tenants.tenant_id"), nullable=False),
        sa.Column("shop_id", sa.String(length=40), sa.ForeignKey("v2_shops.shop_id"), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("phone", sa.String(length=40), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_v2_suppliers_tenant_id", "v2_suppliers", ["tenant_id"])
    op.create_index("ix_v2_suppliers_shop_id", "v2_suppliers", ["shop_id"])

    op.create_table(
        "v2_purchase_orders",
        sa.Column("purchase_order_id", sa.String(length=40), primary_key=True),
        sa.Column("tenant_id", sa.String(length=40), sa.ForeignKey("v2_tenants.tenant_id"), nullable=False),
        sa.Column("shop_id", sa.String(length=40), sa.ForeignKey("v2_shops.shop_id"), nullable=False),
        sa.Column("supplier_id", sa.String(length=40), sa.ForeignKey("v2_suppliers.supplier_id"), nullable=False),
        sa.Column("order_no", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="received"),
        sa.Column("total_amount", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("note", sa.String(length=500), nullable=True),
        sa.Column("created_by_account_id", sa.String(length=40), sa.ForeignKey("v2_accounts.account_id"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_v2_purchase_orders_tenant_id", "v2_purchase_orders", ["tenant_id"])
    op.create_index("ix_v2_purchase_orders_shop_id", "v2_purchase_orders", ["shop_id"])
    op.create_index("ix_v2_purchase_orders_supplier_id", "v2_purchase_orders", ["supplier_id"])
    op.create_index("ix_v2_purchase_orders_order_no", "v2_purchase_orders", ["order_no"])

    op.create_table(
        "v2_purchase_order_lines",
        sa.Column("purchase_order_line_id", sa.String(length=40), primary_key=True),
        sa.Column("purchase_order_id", sa.String(length=40), sa.ForeignKey("v2_purchase_orders.purchase_order_id"), nullable=False),
        sa.Column("tenant_id", sa.String(length=40), sa.ForeignKey("v2_tenants.tenant_id"), nullable=False),
        sa.Column("shop_id", sa.String(length=40), sa.ForeignKey("v2_shops.shop_id"), nullable=False),
        sa.Column("inventory_item_id", sa.String(length=40), sa.ForeignKey("v2_inventory_items.inventory_item_id"), nullable=False),
        sa.Column("item_name", sa.String(length=160), nullable=False),
        sa.Column("quantity", sa.Numeric(12, 3), nullable=False),
        sa.Column("unit", sa.String(length=24), nullable=False),
        sa.Column("unit_cost", sa.Numeric(12, 2), nullable=False),
        sa.Column("line_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_v2_purchase_order_lines_purchase_order_id", "v2_purchase_order_lines", ["purchase_order_id"])
    op.create_index("ix_v2_purchase_order_lines_tenant_id", "v2_purchase_order_lines", ["tenant_id"])
    op.create_index("ix_v2_purchase_order_lines_shop_id", "v2_purchase_order_lines", ["shop_id"])
    op.create_index("ix_v2_purchase_order_lines_inventory_item_id", "v2_purchase_order_lines", ["inventory_item_id"])

    op.create_table(
        "v2_customers",
        sa.Column("customer_id", sa.String(length=40), primary_key=True),
        sa.Column("tenant_id", sa.String(length=40), sa.ForeignKey("v2_tenants.tenant_id"), nullable=False),
        sa.Column("shop_id", sa.String(length=40), sa.ForeignKey("v2_shops.shop_id"), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("phone", sa.String(length=40), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_v2_customers_tenant_id", "v2_customers", ["tenant_id"])
    op.create_index("ix_v2_customers_shop_id", "v2_customers", ["shop_id"])

    op.create_table(
        "v2_finance_transactions",
        sa.Column("finance_transaction_id", sa.String(length=40), primary_key=True),
        sa.Column("tenant_id", sa.String(length=40), sa.ForeignKey("v2_tenants.tenant_id"), nullable=False),
        sa.Column("shop_id", sa.String(length=40), sa.ForeignKey("v2_shops.shop_id"), nullable=False),
        sa.Column("transaction_type", sa.String(length=40), nullable=False),
        sa.Column("direction", sa.String(length=16), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("source_type", sa.String(length=40), nullable=False),
        sa.Column("source_id", sa.String(length=40), nullable=False),
        sa.Column("counterparty_name", sa.String(length=160), nullable=True),
        sa.Column("note", sa.String(length=500), nullable=True),
        sa.Column("created_by_account_id", sa.String(length=40), sa.ForeignKey("v2_accounts.account_id"), nullable=False),
        sa.Column("occurred_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_v2_finance_transactions_tenant_id", "v2_finance_transactions", ["tenant_id"])
    op.create_index("ix_v2_finance_transactions_shop_id", "v2_finance_transactions", ["shop_id"])
    op.create_index("ix_v2_finance_transactions_transaction_type", "v2_finance_transactions", ["transaction_type"])
    op.create_index("ix_v2_finance_transactions_source_type", "v2_finance_transactions", ["source_type"])
    op.create_index("ix_v2_finance_transactions_source_id", "v2_finance_transactions", ["source_id"])

    op.create_table(
        "v2_sales_returns",
        sa.Column("sales_return_id", sa.String(length=40), primary_key=True),
        sa.Column("tenant_id", sa.String(length=40), sa.ForeignKey("v2_tenants.tenant_id"), nullable=False),
        sa.Column("shop_id", sa.String(length=40), sa.ForeignKey("v2_shops.shop_id"), nullable=False),
        sa.Column("sales_order_id", sa.String(length=40), sa.ForeignKey("v2_sales_orders.sales_order_id"), nullable=False),
        sa.Column("sales_order_line_id", sa.String(length=40), sa.ForeignKey("v2_sales_order_lines.sales_order_line_id"), nullable=False),
        sa.Column("inventory_item_id", sa.String(length=40), sa.ForeignKey("v2_inventory_items.inventory_item_id"), nullable=False),
        sa.Column("quantity", sa.Numeric(12, 3), nullable=False),
        sa.Column("refund_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("reason", sa.String(length=500), nullable=True),
        sa.Column("created_by_account_id", sa.String(length=40), sa.ForeignKey("v2_accounts.account_id"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_v2_sales_returns_tenant_id", "v2_sales_returns", ["tenant_id"])
    op.create_index("ix_v2_sales_returns_shop_id", "v2_sales_returns", ["shop_id"])
    op.create_index("ix_v2_sales_returns_sales_order_id", "v2_sales_returns", ["sales_order_id"])
    op.create_index("ix_v2_sales_returns_sales_order_line_id", "v2_sales_returns", ["sales_order_line_id"])
    op.create_index("ix_v2_sales_returns_inventory_item_id", "v2_sales_returns", ["inventory_item_id"])


def downgrade() -> None:
    op.drop_table("v2_sales_returns")
    op.drop_table("v2_finance_transactions")
    op.drop_table("v2_customers")
    op.drop_table("v2_purchase_order_lines")
    op.drop_table("v2_purchase_orders")
    op.drop_table("v2_suppliers")
