"""create shops and sessions tables"""

from alembic import op
import sqlalchemy as sa


revision = "20260404_01"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "shops",
        sa.Column("shop_id", sa.String(length=40), primary_key=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("owner_name", sa.String(length=80), nullable=False),
        sa.Column("industry", sa.String(length=32), nullable=False),
        sa.Column("locale", sa.String(length=16), nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        sa.Column("require_price_confirmation", sa.Boolean(), nullable=False),
        sa.Column("require_new_item_confirmation", sa.Boolean(), nullable=False),
        sa.Column("low_confidence_threshold", sa.Numeric(5, 4), nullable=False),
        sa.Column("default_low_stock_threshold", sa.Numeric(12, 3), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "sessions",
        sa.Column("session_id", sa.String(length=40), primary_key=True),
        sa.Column("shop_id", sa.String(length=40), sa.ForeignKey("shops.shop_id"), nullable=False),
        sa.Column("session_type", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("participants", sa.JSON(), nullable=False),
        sa.Column("last_event_seq", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("last_message_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("sessions")
    op.drop_table("shops")
