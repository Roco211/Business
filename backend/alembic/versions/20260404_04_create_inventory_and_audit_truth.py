from alembic import op
import sqlalchemy as sa


revision = "20260404_04"
down_revision = "20260404_03"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "inventory_items",
        sa.Column("item_id", sa.String(length=40), nullable=False),
        sa.Column("shop_id", sa.String(length=40), nullable=False),
        sa.Column("sku", sa.String(length=64), nullable=True),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("category", sa.String(length=64), nullable=True),
        sa.Column("barcode", sa.String(length=64), nullable=True),
        sa.Column("default_unit", sa.String(length=24), nullable=False),
        sa.Column("current_stock", sa.Numeric(12, 3), nullable=False),
        sa.Column("current_price", sa.Numeric(12, 2), nullable=True),
        sa.Column("low_stock_threshold", sa.Numeric(12, 3), nullable=True),
        sa.Column("image_media_id", sa.String(length=40), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["shop_id"], ["shops.shop_id"]),
        sa.PrimaryKeyConstraint("item_id"),
    )
    op.create_index("ix_inventory_items_shop_id_name", "inventory_items", ["shop_id", "name"], unique=False)

    op.create_table(
        "inventory_events",
        sa.Column("inventory_event_id", sa.String(length=40), nullable=False),
        sa.Column("shop_id", sa.String(length=40), nullable=False),
        sa.Column("item_id", sa.String(length=40), nullable=False),
        sa.Column("event_type", sa.String(length=24), nullable=False),
        sa.Column("quantity_delta", sa.Numeric(12, 3), nullable=False),
        sa.Column("quantity_after", sa.Numeric(12, 3), nullable=False),
        sa.Column("unit", sa.String(length=24), nullable=False),
        sa.Column("price", sa.Numeric(12, 2), nullable=True),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("task_run_id", sa.String(length=40), nullable=True),
        sa.Column("created_by", sa.String(length=40), nullable=False),
        sa.Column("reason", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["shop_id"], ["shops.shop_id"]),
        sa.ForeignKeyConstraint(["item_id"], ["inventory_items.item_id"]),
        sa.ForeignKeyConstraint(["task_run_id"], ["task_runs.task_run_id"]),
        sa.PrimaryKeyConstraint("inventory_event_id"),
    )
    op.create_index(
        "ix_inventory_events_shop_id_item_created_at",
        "inventory_events",
        ["shop_id", "item_id", "created_at"],
        unique=False,
    )

    op.create_table(
        "audit_logs",
        sa.Column("audit_log_id", sa.String(length=40), nullable=False),
        sa.Column("shop_id", sa.String(length=40), nullable=False),
        sa.Column("scope", sa.String(length=32), nullable=False),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("actor_type", sa.String(length=16), nullable=False),
        sa.Column("actor_id", sa.String(length=40), nullable=False),
        sa.Column("task_run_id", sa.String(length=40), nullable=True),
        sa.Column("target_type", sa.String(length=32), nullable=True),
        sa.Column("target_id", sa.String(length=40), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["shop_id"], ["shops.shop_id"]),
        sa.ForeignKeyConstraint(["task_run_id"], ["task_runs.task_run_id"]),
        sa.PrimaryKeyConstraint("audit_log_id"),
    )
    op.create_index("ix_audit_logs_shop_id_created_at", "audit_logs", ["shop_id", "created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_audit_logs_shop_id_created_at", table_name="audit_logs")
    op.drop_table("audit_logs")
    op.drop_index("ix_inventory_events_shop_id_item_created_at", table_name="inventory_events")
    op.drop_table("inventory_events")
    op.drop_index("ix_inventory_items_shop_id_name", table_name="inventory_items")
    op.drop_table("inventory_items")
