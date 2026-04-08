"""create messages and task runs tables"""

from alembic import op
import sqlalchemy as sa


revision = "20260404_02"
down_revision = "20260404_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "messages",
        sa.Column("message_id", sa.String(length=40), primary_key=True),
        sa.Column("session_id", sa.String(length=40), sa.ForeignKey("sessions.session_id"), nullable=False),
        sa.Column("actor_type", sa.String(length=16), nullable=False),
        sa.Column("actor_id", sa.String(length=40), nullable=False),
        sa.Column("message_type", sa.String(length=32), nullable=False),
        sa.Column("text", sa.Text(), nullable=True),
        sa.Column("media_ids", sa.JSON(), nullable=False),
        sa.Column("client_request_id", sa.String(length=64), nullable=True),
        sa.Column("task_run_id", sa.String(length=40), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint(
            "session_id",
            "actor_type",
            "actor_id",
            "client_request_id",
            name="uq_messages_session_actor_client_request",
        ),
    )
    op.create_index("ix_messages_session_created_at", "messages", ["session_id", "created_at"])

    op.create_table(
        "task_runs",
        sa.Column("task_run_id", sa.String(length=40), primary_key=True),
        sa.Column("session_id", sa.String(length=40), sa.ForeignKey("sessions.session_id"), nullable=False),
        sa.Column("source_message_id", sa.String(length=40), sa.ForeignKey("messages.message_id"), nullable=False),
        sa.Column("task_type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("assigned_employee_id", sa.String(length=40), nullable=True),
        sa.Column("result_summary", sa.Text(), nullable=True),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("error_message", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_task_runs_session_updated_at", "task_runs", ["session_id", "updated_at"])
    op.create_index("ix_task_runs_source_message_id", "task_runs", ["source_message_id"])


def downgrade() -> None:
    op.drop_index("ix_task_runs_source_message_id", table_name="task_runs")
    op.drop_index("ix_task_runs_session_updated_at", table_name="task_runs")
    op.drop_table("task_runs")
    op.drop_constraint("uq_messages_session_actor_client_request", "messages", type_="unique")
    op.drop_index("ix_messages_session_created_at", table_name="messages")
    op.drop_table("messages")
