from alembic import op
import sqlalchemy as sa


revision = "20260425_01"
down_revision = "20260419_05"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "v2_sales_orders",
        sa.Column("sales_order_id", sa.String(length=40), nullable=False),
        sa.Column("tenant_id", sa.String(length=40), nullable=False),
        sa.Column("shop_id", sa.String(length=40), nullable=False),
        sa.Column("order_no", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("customer_name", sa.String(length=120), nullable=True),
        sa.Column("payment_method", sa.String(length=32), nullable=False),
        sa.Column("total_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("note", sa.String(length=500), nullable=True),
        sa.Column("created_by_account_id", sa.String(length=40), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["v2_tenants.tenant_id"]),
        sa.ForeignKeyConstraint(["shop_id"], ["v2_shops.shop_id"]),
        sa.ForeignKeyConstraint(["created_by_account_id"], ["v2_accounts.account_id"]),
        sa.PrimaryKeyConstraint("sales_order_id"),
    )
    op.create_index("ix_v2_sales_orders_tenant_id", "v2_sales_orders", ["tenant_id"], unique=False)
    op.create_index("ix_v2_sales_orders_shop_id", "v2_sales_orders", ["shop_id"], unique=False)
    op.create_index("ix_v2_sales_orders_order_no", "v2_sales_orders", ["order_no"], unique=False)

    op.create_table(
        "v2_sales_order_lines",
        sa.Column("sales_order_line_id", sa.String(length=40), nullable=False),
        sa.Column("sales_order_id", sa.String(length=40), nullable=False),
        sa.Column("tenant_id", sa.String(length=40), nullable=False),
        sa.Column("shop_id", sa.String(length=40), nullable=False),
        sa.Column("inventory_item_id", sa.String(length=40), nullable=False),
        sa.Column("item_name", sa.String(length=160), nullable=False),
        sa.Column("quantity", sa.Numeric(12, 3), nullable=False),
        sa.Column("unit", sa.String(length=24), nullable=False),
        sa.Column("unit_price", sa.Numeric(12, 2), nullable=False),
        sa.Column("line_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["sales_order_id"], ["v2_sales_orders.sales_order_id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["v2_tenants.tenant_id"]),
        sa.ForeignKeyConstraint(["shop_id"], ["v2_shops.shop_id"]),
        sa.ForeignKeyConstraint(["inventory_item_id"], ["v2_inventory_items.inventory_item_id"]),
        sa.PrimaryKeyConstraint("sales_order_line_id"),
    )
    op.create_index(
        "ix_v2_sales_order_lines_sales_order_id",
        "v2_sales_order_lines",
        ["sales_order_id"],
        unique=False,
    )
    op.create_index("ix_v2_sales_order_lines_tenant_id", "v2_sales_order_lines", ["tenant_id"], unique=False)
    op.create_index("ix_v2_sales_order_lines_shop_id", "v2_sales_order_lines", ["shop_id"], unique=False)
    op.create_index(
        "ix_v2_sales_order_lines_inventory_item_id",
        "v2_sales_order_lines",
        ["inventory_item_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_v2_sales_order_lines_inventory_item_id", table_name="v2_sales_order_lines")
    op.drop_index("ix_v2_sales_order_lines_shop_id", table_name="v2_sales_order_lines")
    op.drop_index("ix_v2_sales_order_lines_tenant_id", table_name="v2_sales_order_lines")
    op.drop_index("ix_v2_sales_order_lines_sales_order_id", table_name="v2_sales_order_lines")
    op.drop_table("v2_sales_order_lines")
    op.drop_index("ix_v2_sales_orders_order_no", table_name="v2_sales_orders")
    op.drop_index("ix_v2_sales_orders_shop_id", table_name="v2_sales_orders")
    op.drop_index("ix_v2_sales_orders_tenant_id", table_name="v2_sales_orders")
    op.drop_table("v2_sales_orders")
