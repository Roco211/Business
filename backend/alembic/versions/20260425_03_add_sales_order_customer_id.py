"""add sales order customer id

Revision ID: 20260425_03
Revises: 20260425_02
Create Date: 2026-04-25
"""

from alembic import op
import sqlalchemy as sa


revision = "20260425_03"
down_revision = "20260425_02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("v2_sales_orders", sa.Column("customer_id", sa.String(length=40), nullable=True))
    op.create_index("ix_v2_sales_orders_customer_id", "v2_sales_orders", ["customer_id"])


def downgrade() -> None:
    op.drop_index("ix_v2_sales_orders_customer_id", table_name="v2_sales_orders")
    op.drop_column("v2_sales_orders", "customer_id")
