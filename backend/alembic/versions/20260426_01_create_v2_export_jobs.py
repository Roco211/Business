"""create v2 export jobs

Revision ID: 20260426_01
Revises: 20260425_03
Create Date: 2026-04-26
"""

from alembic import op
import sqlalchemy as sa


revision = "20260426_01"
down_revision = "20260425_03"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "v2_export_jobs",
        sa.Column("export_job_id", sa.String(length=40), nullable=False),
        sa.Column("tenant_id", sa.String(length=40), nullable=False),
        sa.Column("shop_id", sa.String(length=40), nullable=False),
        sa.Column("account_id", sa.String(length=40), nullable=False),
        sa.Column("export_type", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("requested_limit", sa.Integer(), nullable=False),
        sa.Column("row_count", sa.Integer(), nullable=False),
        sa.Column("filename", sa.String(length=120), nullable=False),
        sa.Column("content_type", sa.String(length=80), nullable=False),
        sa.Column("storage_kind", sa.String(length=24), nullable=False),
        sa.Column("result_content", sa.Text(), nullable=True),
        sa.Column("error_code", sa.String(length=80), nullable=True),
        sa.Column("error_message", sa.String(length=255), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["v2_accounts.account_id"]),
        sa.ForeignKeyConstraint(["shop_id"], ["v2_shops.shop_id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["v2_tenants.tenant_id"]),
        sa.PrimaryKeyConstraint("export_job_id"),
    )
    op.create_index("ix_v2_export_jobs_account_id", "v2_export_jobs", ["account_id"])
    op.create_index("ix_v2_export_jobs_export_type", "v2_export_jobs", ["export_type"])
    op.create_index("ix_v2_export_jobs_expires_at", "v2_export_jobs", ["expires_at"])
    op.create_index("ix_v2_export_jobs_shop_id", "v2_export_jobs", ["shop_id"])
    op.create_index("ix_v2_export_jobs_status", "v2_export_jobs", ["status"])
    op.create_index("ix_v2_export_jobs_tenant_id", "v2_export_jobs", ["tenant_id"])


def downgrade() -> None:
    op.drop_index("ix_v2_export_jobs_tenant_id", table_name="v2_export_jobs")
    op.drop_index("ix_v2_export_jobs_status", table_name="v2_export_jobs")
    op.drop_index("ix_v2_export_jobs_shop_id", table_name="v2_export_jobs")
    op.drop_index("ix_v2_export_jobs_expires_at", table_name="v2_export_jobs")
    op.drop_index("ix_v2_export_jobs_export_type", table_name="v2_export_jobs")
    op.drop_index("ix_v2_export_jobs_account_id", table_name="v2_export_jobs")
    op.drop_table("v2_export_jobs")
