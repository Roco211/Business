from alembic import op
import sqlalchemy as sa


revision = "20260419_05"
down_revision = "20260419_04"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "v2_stock_check_records",
        sa.Column("check_id", sa.String(length=40), nullable=False),
        sa.Column("tenant_id", sa.String(length=40), nullable=False),
        sa.Column("shop_id", sa.String(length=40), nullable=False),
        sa.Column("inventory_item_id", sa.String(length=40), nullable=False),
        sa.Column("system_quantity", sa.Numeric(12, 3), nullable=False),
        sa.Column("actual_quantity", sa.Numeric(12, 3), nullable=False),
        sa.Column("difference", sa.Numeric(12, 3), nullable=False),
        sa.Column("unit", sa.String(length=24), nullable=False),
        sa.Column("check_method", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("notes", sa.String(length=500), nullable=True),
        sa.Column("created_by_account_id", sa.String(length=40), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["v2_tenants.tenant_id"]),
        sa.ForeignKeyConstraint(["shop_id"], ["v2_shops.shop_id"]),
        sa.ForeignKeyConstraint(["inventory_item_id"], ["v2_inventory_items.inventory_item_id"]),
        sa.ForeignKeyConstraint(["created_by_account_id"], ["v2_accounts.account_id"]),
        sa.PrimaryKeyConstraint("check_id"),
    )
    op.create_index(
        "ix_v2_stock_check_records_tenant_id",
        "v2_stock_check_records",
        ["tenant_id"],
        unique=False,
    )
    op.create_index(
        "ix_v2_stock_check_records_shop_id",
        "v2_stock_check_records",
        ["shop_id"],
        unique=False,
    )
    op.create_index(
        "ix_v2_stock_check_records_inventory_item_id",
        "v2_stock_check_records",
        ["inventory_item_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_v2_stock_check_records_inventory_item_id", table_name="v2_stock_check_records")
    op.drop_index("ix_v2_stock_check_records_shop_id", table_name="v2_stock_check_records")
    op.drop_index("ix_v2_stock_check_records_tenant_id", table_name="v2_stock_check_records")
    op.drop_table("v2_stock_check_records")
