from alembic import op
import sqlalchemy as sa


revision = "20260418_06"
down_revision = "20260418_05"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "v2_audit_logs",
        sa.Column("audit_log_id", sa.String(length=40), nullable=False),
        sa.Column("tenant_id", sa.String(length=40), nullable=False),
        sa.Column("shop_id", sa.String(length=40), nullable=False),
        sa.Column("actor_type", sa.String(length=20), nullable=False),
        sa.Column("actor_id", sa.String(length=40), nullable=False),
        sa.Column("session_id", sa.String(length=40), nullable=True),
        sa.Column("task_run_id", sa.String(length=40), nullable=True),
        sa.Column("action", sa.String(length=80), nullable=False),
        sa.Column("target_type", sa.String(length=40), nullable=True),
        sa.Column("target_id", sa.String(length=40), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["v2_conversation_sessions.session_id"]),
        sa.ForeignKeyConstraint(["shop_id"], ["v2_shops.shop_id"]),
        sa.ForeignKeyConstraint(["task_run_id"], ["v2_task_runs.task_run_id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["v2_tenants.tenant_id"]),
        sa.PrimaryKeyConstraint("audit_log_id"),
    )
    op.create_index("ix_v2_audit_logs_tenant_id", "v2_audit_logs", ["tenant_id"], unique=False)
    op.create_index("ix_v2_audit_logs_shop_id", "v2_audit_logs", ["shop_id"], unique=False)
    op.create_index("ix_v2_audit_logs_session_id", "v2_audit_logs", ["session_id"], unique=False)
    op.create_index("ix_v2_audit_logs_task_run_id", "v2_audit_logs", ["task_run_id"], unique=False)

    op.create_table(
        "v2_outbox_events",
        sa.Column("outbox_event_id", sa.String(length=40), nullable=False),
        sa.Column("tenant_id", sa.String(length=40), nullable=False),
        sa.Column("shop_id", sa.String(length=40), nullable=False),
        sa.Column("aggregate_type", sa.String(length=40), nullable=False),
        sa.Column("aggregate_id", sa.String(length=40), nullable=False),
        sa.Column("event_type", sa.String(length=80), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("available_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["shop_id"], ["v2_shops.shop_id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["v2_tenants.tenant_id"]),
        sa.PrimaryKeyConstraint("outbox_event_id"),
    )
    op.create_index("ix_v2_outbox_events_tenant_id", "v2_outbox_events", ["tenant_id"], unique=False)
    op.create_index("ix_v2_outbox_events_shop_id", "v2_outbox_events", ["shop_id"], unique=False)
    op.create_index("ix_v2_outbox_events_status", "v2_outbox_events", ["status"], unique=False)
    op.create_index(
        "ix_v2_outbox_events_available_at",
        "v2_outbox_events",
        ["available_at"],
        unique=False,
    )
    op.create_index(
        "ix_v2_outbox_events_aggregate_type_aggregate_id",
        "v2_outbox_events",
        ["aggregate_type", "aggregate_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_v2_outbox_events_aggregate_type_aggregate_id",
        table_name="v2_outbox_events",
    )
    op.drop_index("ix_v2_outbox_events_available_at", table_name="v2_outbox_events")
    op.drop_index("ix_v2_outbox_events_status", table_name="v2_outbox_events")
    op.drop_index("ix_v2_outbox_events_shop_id", table_name="v2_outbox_events")
    op.drop_index("ix_v2_outbox_events_tenant_id", table_name="v2_outbox_events")
    op.drop_table("v2_outbox_events")

    op.drop_index("ix_v2_audit_logs_task_run_id", table_name="v2_audit_logs")
    op.drop_index("ix_v2_audit_logs_session_id", table_name="v2_audit_logs")
    op.drop_index("ix_v2_audit_logs_shop_id", table_name="v2_audit_logs")
    op.drop_index("ix_v2_audit_logs_tenant_id", table_name="v2_audit_logs")
    op.drop_table("v2_audit_logs")
