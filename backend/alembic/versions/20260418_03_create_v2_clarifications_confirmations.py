from alembic import op
import sqlalchemy as sa


revision = "20260418_03"
down_revision = "20260418_02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "v2_clarifications",
        sa.Column("clarification_id", sa.String(length=40), nullable=False),
        sa.Column("tenant_id", sa.String(length=40), nullable=False),
        sa.Column("shop_id", sa.String(length=40), nullable=False),
        sa.Column("task_run_id", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("reason_code", sa.String(length=64), nullable=False),
        sa.Column("question_text", sa.String(length=500), nullable=False),
        sa.Column("requested_fields", sa.JSON(), nullable=False),
        sa.Column("draft_payload", sa.JSON(), nullable=True),
        sa.Column("answer_payload", sa.JSON(), nullable=True),
        sa.Column("answered_by_account_id", sa.String(length=40), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("answered_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["answered_by_account_id"], ["v2_accounts.account_id"]),
        sa.ForeignKeyConstraint(["shop_id"], ["v2_shops.shop_id"]),
        sa.ForeignKeyConstraint(["task_run_id"], ["v2_task_runs.task_run_id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["v2_tenants.tenant_id"]),
        sa.PrimaryKeyConstraint("clarification_id"),
        sa.UniqueConstraint("task_run_id"),
    )
    op.create_index("ix_v2_clarifications_tenant_id", "v2_clarifications", ["tenant_id"], unique=False)
    op.create_index("ix_v2_clarifications_shop_id", "v2_clarifications", ["shop_id"], unique=False)

    op.create_table(
        "v2_confirmations",
        sa.Column("confirmation_id", sa.String(length=40), nullable=False),
        sa.Column("tenant_id", sa.String(length=40), nullable=False),
        sa.Column("shop_id", sa.String(length=40), nullable=False),
        sa.Column("task_run_id", sa.String(length=40), nullable=False),
        sa.Column("confirmation_type", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("draft_payload", sa.JSON(), nullable=False),
        sa.Column("approved_by_account_id", sa.String(length=40), nullable=True),
        sa.Column("resolution_payload", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["approved_by_account_id"], ["v2_accounts.account_id"]),
        sa.ForeignKeyConstraint(["shop_id"], ["v2_shops.shop_id"]),
        sa.ForeignKeyConstraint(["task_run_id"], ["v2_task_runs.task_run_id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["v2_tenants.tenant_id"]),
        sa.PrimaryKeyConstraint("confirmation_id"),
        sa.UniqueConstraint("task_run_id"),
    )
    op.create_index("ix_v2_confirmations_tenant_id", "v2_confirmations", ["tenant_id"], unique=False)
    op.create_index("ix_v2_confirmations_shop_id", "v2_confirmations", ["shop_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_v2_confirmations_shop_id", table_name="v2_confirmations")
    op.drop_index("ix_v2_confirmations_tenant_id", table_name="v2_confirmations")
    op.drop_table("v2_confirmations")
    op.drop_index("ix_v2_clarifications_shop_id", table_name="v2_clarifications")
    op.drop_index("ix_v2_clarifications_tenant_id", table_name="v2_clarifications")
    op.drop_table("v2_clarifications")
