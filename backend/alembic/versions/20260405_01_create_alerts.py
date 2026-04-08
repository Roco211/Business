from alembic import op
import sqlalchemy as sa


revision = "20260405_01"
down_revision = "20260404_04"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "alerts",
        sa.Column("alert_id", sa.String(length=40), nullable=False),
        sa.Column("shop_id", sa.String(length=40), nullable=False),
        sa.Column("alert_type", sa.String(length=24), nullable=False),
        sa.Column("item_id", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("stock", sa.Numeric(12, 3), nullable=False),
        sa.Column("threshold", sa.Numeric(12, 3), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["item_id"], ["inventory_items.item_id"]),
        sa.ForeignKeyConstraint(["shop_id"], ["shops.shop_id"]),
        sa.PrimaryKeyConstraint("alert_id"),
    )
    op.create_index(
        "ix_alerts_shop_id_status_alert_type",
        "alerts",
        ["shop_id", "status", "alert_type"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_alerts_shop_id_status_alert_type", table_name="alerts")
    op.drop_table("alerts")
