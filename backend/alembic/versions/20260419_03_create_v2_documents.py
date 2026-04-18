from alembic import op
import sqlalchemy as sa


revision = "20260419_03"
down_revision = "20260419_02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "v2_documents",
        sa.Column("document_id", sa.String(length=40), nullable=False),
        sa.Column("tenant_id", sa.String(length=40), nullable=False),
        sa.Column("shop_id", sa.String(length=40), nullable=False),
        sa.Column("context_session_id", sa.String(length=40), nullable=False),
        sa.Column("media_asset_id", sa.String(length=40), nullable=False),
        sa.Column("model_call_log_id", sa.String(length=40), nullable=True),
        sa.Column("created_by_account_id", sa.String(length=40), nullable=False),
        sa.Column("document_type", sa.String(length=32), nullable=False),
        sa.Column("extraction_status", sa.String(length=24), nullable=False),
        sa.Column("extracted_fields", sa.JSON(), nullable=False),
        sa.Column("confidence_summary", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["context_session_id"], ["v2_context_sessions.context_session_id"]),
        sa.ForeignKeyConstraint(["created_by_account_id"], ["v2_accounts.account_id"]),
        sa.ForeignKeyConstraint(["media_asset_id"], ["v2_media_assets.media_asset_id"]),
        sa.ForeignKeyConstraint(["model_call_log_id"], ["v2_model_call_logs.model_call_log_id"]),
        sa.ForeignKeyConstraint(["shop_id"], ["v2_shops.shop_id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["v2_tenants.tenant_id"]),
        sa.PrimaryKeyConstraint("document_id"),
    )
    op.create_index("ix_v2_documents_tenant_id", "v2_documents", ["tenant_id"], unique=False)
    op.create_index("ix_v2_documents_shop_id", "v2_documents", ["shop_id"], unique=False)
    op.create_index("ix_v2_documents_context_session_id", "v2_documents", ["context_session_id"], unique=False)
    op.create_index("ix_v2_documents_media_asset_id", "v2_documents", ["media_asset_id"], unique=False)
    op.create_index("ix_v2_documents_model_call_log_id", "v2_documents", ["model_call_log_id"], unique=False)
    op.create_index(
        "ix_v2_documents_created_by_account_id",
        "v2_documents",
        ["created_by_account_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_v2_documents_created_by_account_id", table_name="v2_documents")
    op.drop_index("ix_v2_documents_model_call_log_id", table_name="v2_documents")
    op.drop_index("ix_v2_documents_media_asset_id", table_name="v2_documents")
    op.drop_index("ix_v2_documents_context_session_id", table_name="v2_documents")
    op.drop_index("ix_v2_documents_shop_id", table_name="v2_documents")
    op.drop_index("ix_v2_documents_tenant_id", table_name="v2_documents")
    op.drop_table("v2_documents")
