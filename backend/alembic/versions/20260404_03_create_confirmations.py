"""create confirmations table"""

from alembic import op
import sqlalchemy as sa


revision = "20260404_03"
down_revision = "20260404_02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "confirmations",
        sa.Column("confirmation_id", sa.String(length=40), primary_key=True),
        sa.Column("task_run_id", sa.String(length=40), sa.ForeignKey("task_runs.task_run_id"), nullable=False),
        sa.Column("confirmation_type", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("fields", sa.JSON(), nullable=False),
        sa.Column("requested_by_employee_id", sa.String(length=40), nullable=False),
        sa.Column("resolution_payload", sa.JSON(), nullable=True),
        sa.Column("approved_by_actor_id", sa.String(length=40), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("task_run_id", name="uq_confirmations_task_run_id"),
    )
    op.create_index("ix_confirmations_status_created_at", "confirmations", ["status", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_confirmations_status_created_at", table_name="confirmations")
    op.drop_constraint("uq_confirmations_task_run_id", "confirmations", type_="unique")
    op.drop_table("confirmations")
