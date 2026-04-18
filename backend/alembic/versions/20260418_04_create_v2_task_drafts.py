from alembic import op
import sqlalchemy as sa


revision = "20260418_04"
down_revision = "20260418_03"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "v2_task_drafts",
        sa.Column("task_draft_id", sa.String(length=40), nullable=False),
        sa.Column("tenant_id", sa.String(length=40), nullable=False),
        sa.Column("shop_id", sa.String(length=40), nullable=False),
        sa.Column("task_run_id", sa.String(length=40), nullable=False),
        sa.Column("draft_type", sa.String(length=64), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("created_by_account_id", sa.String(length=40), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["created_by_account_id"], ["v2_accounts.account_id"]),
        sa.ForeignKeyConstraint(["shop_id"], ["v2_shops.shop_id"]),
        sa.ForeignKeyConstraint(["task_run_id"], ["v2_task_runs.task_run_id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["v2_tenants.tenant_id"]),
        sa.PrimaryKeyConstraint("task_draft_id"),
        sa.UniqueConstraint("task_run_id"),
    )
    op.create_index("ix_v2_task_drafts_tenant_id", "v2_task_drafts", ["tenant_id"], unique=False)
    op.create_index("ix_v2_task_drafts_shop_id", "v2_task_drafts", ["shop_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_v2_task_drafts_shop_id", table_name="v2_task_drafts")
    op.drop_index("ix_v2_task_drafts_tenant_id", table_name="v2_task_drafts")
    op.drop_table("v2_task_drafts")
