from alembic import op
import sqlalchemy as sa


revision = "20260418_05"
down_revision = "20260418_04"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "v2_inventory_items",
        sa.Column("inventory_item_id", sa.String(length=40), nullable=False),
        sa.Column("tenant_id", sa.String(length=40), nullable=False),
        sa.Column("sku", sa.String(length=64), nullable=True),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("barcode", sa.String(length=64), nullable=True),
        sa.Column("default_unit", sa.String(length=24), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["v2_tenants.tenant_id"]),
        sa.PrimaryKeyConstraint("inventory_item_id"),
    )
    op.create_index("ix_v2_inventory_items_tenant_id", "v2_inventory_items", ["tenant_id"], unique=False)
    op.create_index(
        "ix_v2_inventory_items_tenant_id_name",
        "v2_inventory_items",
        ["tenant_id", "name"],
        unique=False,
    )

    op.create_table(
        "v2_inventory_stock_snapshots",
        sa.Column("snapshot_id", sa.String(length=40), nullable=False),
        sa.Column("tenant_id", sa.String(length=40), nullable=False),
        sa.Column("shop_id", sa.String(length=40), nullable=False),
        sa.Column("inventory_item_id", sa.String(length=40), nullable=False),
        sa.Column("current_quantity", sa.Numeric(12, 3), nullable=False),
        sa.Column("current_price", sa.Numeric(12, 2), nullable=True),
        sa.Column("low_stock_threshold", sa.Numeric(12, 3), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["inventory_item_id"], ["v2_inventory_items.inventory_item_id"]),
        sa.ForeignKeyConstraint(["shop_id"], ["v2_shops.shop_id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["v2_tenants.tenant_id"]),
        sa.PrimaryKeyConstraint("snapshot_id"),
        sa.UniqueConstraint("shop_id", "inventory_item_id", name="uq_v2_inventory_stock_snapshots_shop_item"),
    )
    op.create_index(
        "ix_v2_inventory_stock_snapshots_tenant_id",
        "v2_inventory_stock_snapshots",
        ["tenant_id"],
        unique=False,
    )
    op.create_index(
        "ix_v2_inventory_stock_snapshots_shop_id",
        "v2_inventory_stock_snapshots",
        ["shop_id"],
        unique=False,
    )
    op.create_index(
        "ix_v2_inventory_stock_snapshots_inventory_item_id",
        "v2_inventory_stock_snapshots",
        ["inventory_item_id"],
        unique=False,
    )

    op.create_table(
        "v2_inventory_ledger_events",
        sa.Column("event_id", sa.String(length=40), nullable=False),
        sa.Column("tenant_id", sa.String(length=40), nullable=False),
        sa.Column("shop_id", sa.String(length=40), nullable=False),
        sa.Column("inventory_item_id", sa.String(length=40), nullable=False),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("quantity_delta", sa.Numeric(12, 3), nullable=False),
        sa.Column("quantity_after", sa.Numeric(12, 3), nullable=False),
        sa.Column("unit", sa.String(length=24), nullable=False),
        sa.Column("price", sa.Numeric(12, 2), nullable=True),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("source_id", sa.String(length=40), nullable=False),
        sa.Column("reason", sa.String(length=255), nullable=True),
        sa.Column("created_by_account_id", sa.String(length=40), nullable=False),
        sa.Column("occurred_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["created_by_account_id"], ["v2_accounts.account_id"]),
        sa.ForeignKeyConstraint(["inventory_item_id"], ["v2_inventory_items.inventory_item_id"]),
        sa.ForeignKeyConstraint(["shop_id"], ["v2_shops.shop_id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["v2_tenants.tenant_id"]),
        sa.PrimaryKeyConstraint("event_id"),
    )
    op.create_index(
        "ix_v2_inventory_ledger_events_tenant_id",
        "v2_inventory_ledger_events",
        ["tenant_id"],
        unique=False,
    )
    op.create_index(
        "ix_v2_inventory_ledger_events_shop_id",
        "v2_inventory_ledger_events",
        ["shop_id"],
        unique=False,
    )
    op.create_index(
        "ix_v2_inventory_ledger_events_inventory_item_id",
        "v2_inventory_ledger_events",
        ["inventory_item_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_v2_inventory_ledger_events_inventory_item_id", table_name="v2_inventory_ledger_events")
    op.drop_index("ix_v2_inventory_ledger_events_shop_id", table_name="v2_inventory_ledger_events")
    op.drop_index("ix_v2_inventory_ledger_events_tenant_id", table_name="v2_inventory_ledger_events")
    op.drop_table("v2_inventory_ledger_events")
    op.drop_index(
        "ix_v2_inventory_stock_snapshots_inventory_item_id",
        table_name="v2_inventory_stock_snapshots",
    )
    op.drop_index("ix_v2_inventory_stock_snapshots_shop_id", table_name="v2_inventory_stock_snapshots")
    op.drop_index("ix_v2_inventory_stock_snapshots_tenant_id", table_name="v2_inventory_stock_snapshots")
    op.drop_table("v2_inventory_stock_snapshots")
    op.drop_index("ix_v2_inventory_items_tenant_id_name", table_name="v2_inventory_items")
    op.drop_index("ix_v2_inventory_items_tenant_id", table_name="v2_inventory_items")
    op.drop_table("v2_inventory_items")
