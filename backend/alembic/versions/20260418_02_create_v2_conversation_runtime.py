from alembic import op
import sqlalchemy as sa


revision = "20260418_02"
down_revision = "20260418_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "v2_conversation_sessions",
        sa.Column("session_id", sa.String(length=40), nullable=False),
        sa.Column("tenant_id", sa.String(length=40), nullable=False),
        sa.Column("shop_id", sa.String(length=40), nullable=False),
        sa.Column("session_type", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("initiated_by_account_id", sa.String(length=40), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["initiated_by_account_id"], ["v2_accounts.account_id"]),
        sa.ForeignKeyConstraint(["shop_id"], ["v2_shops.shop_id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["v2_tenants.tenant_id"]),
        sa.PrimaryKeyConstraint("session_id"),
    )
    op.create_index("ix_v2_conversation_sessions_tenant_id", "v2_conversation_sessions", ["tenant_id"], unique=False)
    op.create_index("ix_v2_conversation_sessions_shop_id", "v2_conversation_sessions", ["shop_id"], unique=False)
    op.create_index(
        "ix_v2_conversation_sessions_initiated_by_account_id",
        "v2_conversation_sessions",
        ["initiated_by_account_id"],
        unique=False,
    )

    op.create_table(
        "v2_messages",
        sa.Column("message_id", sa.String(length=40), nullable=False),
        sa.Column("tenant_id", sa.String(length=40), nullable=False),
        sa.Column("shop_id", sa.String(length=40), nullable=False),
        sa.Column("session_id", sa.String(length=40), nullable=False),
        sa.Column("actor_type", sa.String(length=20), nullable=False),
        sa.Column("actor_id", sa.String(length=40), nullable=False),
        sa.Column("message_kind", sa.String(length=32), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("client_request_id", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["v2_conversation_sessions.session_id"]),
        sa.ForeignKeyConstraint(["shop_id"], ["v2_shops.shop_id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["v2_tenants.tenant_id"]),
        sa.PrimaryKeyConstraint("message_id"),
        sa.UniqueConstraint("session_id", "client_request_id", name="uq_v2_messages_session_client_request"),
    )
    op.create_index("ix_v2_messages_tenant_id", "v2_messages", ["tenant_id"], unique=False)
    op.create_index("ix_v2_messages_shop_id", "v2_messages", ["shop_id"], unique=False)
    op.create_index("ix_v2_messages_session_id", "v2_messages", ["session_id"], unique=False)

    op.create_table(
        "v2_task_runs",
        sa.Column("task_run_id", sa.String(length=40), nullable=False),
        sa.Column("tenant_id", sa.String(length=40), nullable=False),
        sa.Column("shop_id", sa.String(length=40), nullable=False),
        sa.Column("session_id", sa.String(length=40), nullable=False),
        sa.Column("source_message_id", sa.String(length=40), nullable=False),
        sa.Column("intent_type", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("risk_level", sa.String(length=20), nullable=False),
        sa.Column("trace_id", sa.String(length=64), nullable=False),
        sa.Column("result_summary", sa.String(length=255), nullable=True),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["session_id"], ["v2_conversation_sessions.session_id"]),
        sa.ForeignKeyConstraint(["shop_id"], ["v2_shops.shop_id"]),
        sa.ForeignKeyConstraint(["source_message_id"], ["v2_messages.message_id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["v2_tenants.tenant_id"]),
        sa.PrimaryKeyConstraint("task_run_id"),
        sa.UniqueConstraint("source_message_id"),
    )
    op.create_index("ix_v2_task_runs_tenant_id", "v2_task_runs", ["tenant_id"], unique=False)
    op.create_index("ix_v2_task_runs_shop_id", "v2_task_runs", ["shop_id"], unique=False)
    op.create_index("ix_v2_task_runs_session_id", "v2_task_runs", ["session_id"], unique=False)
    op.create_index("ix_v2_task_runs_trace_id", "v2_task_runs", ["trace_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_v2_task_runs_trace_id", table_name="v2_task_runs")
    op.drop_index("ix_v2_task_runs_session_id", table_name="v2_task_runs")
    op.drop_index("ix_v2_task_runs_shop_id", table_name="v2_task_runs")
    op.drop_index("ix_v2_task_runs_tenant_id", table_name="v2_task_runs")
    op.drop_table("v2_task_runs")
    op.drop_index("ix_v2_messages_session_id", table_name="v2_messages")
    op.drop_index("ix_v2_messages_shop_id", table_name="v2_messages")
    op.drop_index("ix_v2_messages_tenant_id", table_name="v2_messages")
    op.drop_table("v2_messages")
    op.drop_index("ix_v2_conversation_sessions_initiated_by_account_id", table_name="v2_conversation_sessions")
    op.drop_index("ix_v2_conversation_sessions_shop_id", table_name="v2_conversation_sessions")
    op.drop_index("ix_v2_conversation_sessions_tenant_id", table_name="v2_conversation_sessions")
    op.drop_table("v2_conversation_sessions")
