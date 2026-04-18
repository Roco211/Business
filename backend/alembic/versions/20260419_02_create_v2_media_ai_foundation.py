from alembic import op
import sqlalchemy as sa


revision = "20260419_02"
down_revision = "20260419_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "v2_media_assets",
        sa.Column("media_asset_id", sa.String(length=40), nullable=False),
        sa.Column("tenant_id", sa.String(length=40), nullable=False),
        sa.Column("shop_id", sa.String(length=40), nullable=False),
        sa.Column("context_session_id", sa.String(length=40), nullable=False),
        sa.Column("uploaded_by_account_id", sa.String(length=40), nullable=False),
        sa.Column("media_type", sa.String(length=32), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=120), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("storage_provider", sa.String(length=32), nullable=False),
        sa.Column("object_key", sa.String(length=255), nullable=False),
        sa.Column("upload_url", sa.String(length=255), nullable=False),
        sa.Column("public_url", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("checksum_sha256", sa.String(length=128), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("uploaded_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["context_session_id"], ["v2_context_sessions.context_session_id"]),
        sa.ForeignKeyConstraint(["shop_id"], ["v2_shops.shop_id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["v2_tenants.tenant_id"]),
        sa.ForeignKeyConstraint(["uploaded_by_account_id"], ["v2_accounts.account_id"]),
        sa.PrimaryKeyConstraint("media_asset_id"),
    )
    op.create_index("ix_v2_media_assets_tenant_id", "v2_media_assets", ["tenant_id"], unique=False)
    op.create_index("ix_v2_media_assets_shop_id", "v2_media_assets", ["shop_id"], unique=False)
    op.create_index(
        "ix_v2_media_assets_context_session_id",
        "v2_media_assets",
        ["context_session_id"],
        unique=False,
    )
    op.create_index(
        "ix_v2_media_assets_uploaded_by_account_id",
        "v2_media_assets",
        ["uploaded_by_account_id"],
        unique=False,
    )

    op.create_table(
        "v2_model_call_logs",
        sa.Column("model_call_log_id", sa.String(length=40), nullable=False),
        sa.Column("tenant_id", sa.String(length=40), nullable=False),
        sa.Column("shop_id", sa.String(length=40), nullable=False),
        sa.Column("context_session_id", sa.String(length=40), nullable=False),
        sa.Column("requested_by_account_id", sa.String(length=40), nullable=False),
        sa.Column("media_asset_id", sa.String(length=40), nullable=True),
        sa.Column("task_run_id", sa.String(length=40), nullable=True),
        sa.Column("conversation_session_id", sa.String(length=40), nullable=True),
        sa.Column("provider_type", sa.String(length=32), nullable=False),
        sa.Column("provider_key", sa.String(length=64), nullable=False),
        sa.Column("model_name", sa.String(length=120), nullable=False),
        sa.Column("operation_type", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("request_payload", sa.JSON(), nullable=True),
        sa.Column("response_payload", sa.JSON(), nullable=True),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("cost_micros", sa.Integer(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["context_session_id"], ["v2_context_sessions.context_session_id"]),
        sa.ForeignKeyConstraint(["conversation_session_id"], ["v2_conversation_sessions.session_id"]),
        sa.ForeignKeyConstraint(["media_asset_id"], ["v2_media_assets.media_asset_id"]),
        sa.ForeignKeyConstraint(["requested_by_account_id"], ["v2_accounts.account_id"]),
        sa.ForeignKeyConstraint(["shop_id"], ["v2_shops.shop_id"]),
        sa.ForeignKeyConstraint(["task_run_id"], ["v2_task_runs.task_run_id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["v2_tenants.tenant_id"]),
        sa.PrimaryKeyConstraint("model_call_log_id"),
    )
    op.create_index("ix_v2_model_call_logs_tenant_id", "v2_model_call_logs", ["tenant_id"], unique=False)
    op.create_index("ix_v2_model_call_logs_shop_id", "v2_model_call_logs", ["shop_id"], unique=False)
    op.create_index(
        "ix_v2_model_call_logs_context_session_id",
        "v2_model_call_logs",
        ["context_session_id"],
        unique=False,
    )
    op.create_index(
        "ix_v2_model_call_logs_requested_by_account_id",
        "v2_model_call_logs",
        ["requested_by_account_id"],
        unique=False,
    )
    op.create_index("ix_v2_model_call_logs_media_asset_id", "v2_model_call_logs", ["media_asset_id"], unique=False)
    op.create_index("ix_v2_model_call_logs_task_run_id", "v2_model_call_logs", ["task_run_id"], unique=False)
    op.create_index(
        "ix_v2_model_call_logs_conversation_session_id",
        "v2_model_call_logs",
        ["conversation_session_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_v2_model_call_logs_conversation_session_id", table_name="v2_model_call_logs")
    op.drop_index("ix_v2_model_call_logs_task_run_id", table_name="v2_model_call_logs")
    op.drop_index("ix_v2_model_call_logs_media_asset_id", table_name="v2_model_call_logs")
    op.drop_index("ix_v2_model_call_logs_requested_by_account_id", table_name="v2_model_call_logs")
    op.drop_index("ix_v2_model_call_logs_context_session_id", table_name="v2_model_call_logs")
    op.drop_index("ix_v2_model_call_logs_shop_id", table_name="v2_model_call_logs")
    op.drop_index("ix_v2_model_call_logs_tenant_id", table_name="v2_model_call_logs")
    op.drop_table("v2_model_call_logs")
    op.drop_index("ix_v2_media_assets_uploaded_by_account_id", table_name="v2_media_assets")
    op.drop_index("ix_v2_media_assets_context_session_id", table_name="v2_media_assets")
    op.drop_index("ix_v2_media_assets_shop_id", table_name="v2_media_assets")
    op.drop_index("ix_v2_media_assets_tenant_id", table_name="v2_media_assets")
    op.drop_table("v2_media_assets")
