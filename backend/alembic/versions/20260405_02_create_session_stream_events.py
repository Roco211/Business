from alembic import op
import sqlalchemy as sa


revision = "20260405_02"
down_revision = "20260405_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "session_stream_events",
        sa.Column("event_id", sa.String(length=40), nullable=False),
        sa.Column("session_id", sa.String(length=40), nullable=False),
        sa.Column("seq", sa.BigInteger(), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("task_run_id", sa.String(length=40), nullable=True),
        sa.Column("message_id", sa.String(length=40), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["message_id"], ["messages.message_id"]),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.session_id"]),
        sa.ForeignKeyConstraint(["task_run_id"], ["task_runs.task_run_id"]),
        sa.PrimaryKeyConstraint("event_id"),
    )
    op.create_index(
        "ix_session_stream_events_session_id_seq",
        "session_stream_events",
        ["session_id", "seq"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_session_stream_events_session_id_seq", table_name="session_stream_events")
    op.drop_table("session_stream_events")
