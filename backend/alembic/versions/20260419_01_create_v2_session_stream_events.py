from alembic import op
import sqlalchemy as sa


revision = "20260419_01"
down_revision = "20260418_07"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "v2_conversation_sessions",
        sa.Column("last_event_seq", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_table(
        "v2_session_stream_events",
        sa.Column("event_id", sa.String(length=40), nullable=False),
        sa.Column("tenant_id", sa.String(length=40), nullable=False),
        sa.Column("shop_id", sa.String(length=40), nullable=False),
        sa.Column("session_id", sa.String(length=40), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("task_run_id", sa.String(length=40), nullable=True),
        sa.Column("message_id", sa.String(length=40), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["v2_tenants.tenant_id"]),
        sa.ForeignKeyConstraint(["shop_id"], ["v2_shops.shop_id"]),
        sa.ForeignKeyConstraint(["session_id"], ["v2_conversation_sessions.session_id"]),
        sa.ForeignKeyConstraint(["task_run_id"], ["v2_task_runs.task_run_id"]),
        sa.ForeignKeyConstraint(["message_id"], ["v2_messages.message_id"]),
        sa.PrimaryKeyConstraint("event_id"),
        sa.UniqueConstraint("session_id", "seq", name="uq_v2_session_stream_events_session_seq"),
    )
    op.create_index("ix_v2_session_stream_events_tenant_id", "v2_session_stream_events", ["tenant_id"])
    op.create_index("ix_v2_session_stream_events_shop_id", "v2_session_stream_events", ["shop_id"])
    op.create_index("ix_v2_session_stream_events_session_id", "v2_session_stream_events", ["session_id"])
    op.create_index(
        "ix_v2_session_stream_events_session_id_seq",
        "v2_session_stream_events",
        ["session_id", "seq"],
    )
    op.create_index("ix_v2_session_stream_events_task_run_id", "v2_session_stream_events", ["task_run_id"])
    op.create_index("ix_v2_session_stream_events_message_id", "v2_session_stream_events", ["message_id"])


def downgrade() -> None:
    op.drop_index("ix_v2_session_stream_events_message_id", table_name="v2_session_stream_events")
    op.drop_index("ix_v2_session_stream_events_task_run_id", table_name="v2_session_stream_events")
    op.drop_index("ix_v2_session_stream_events_session_id_seq", table_name="v2_session_stream_events")
    op.drop_index("ix_v2_session_stream_events_session_id", table_name="v2_session_stream_events")
    op.drop_index("ix_v2_session_stream_events_shop_id", table_name="v2_session_stream_events")
    op.drop_index("ix_v2_session_stream_events_tenant_id", table_name="v2_session_stream_events")
    op.drop_table("v2_session_stream_events")
    op.drop_column("v2_conversation_sessions", "last_event_seq")
