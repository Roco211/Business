from alembic import op
import sqlalchemy as sa


revision = "20260405_04"
down_revision = "20260405_03"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ocr_documents",
        sa.Column("ocr_document_id", sa.String(length=40), nullable=False),
        sa.Column("shop_id", sa.String(length=40), nullable=False),
        sa.Column("task_run_id", sa.String(length=40), nullable=True),
        sa.Column("media_id", sa.String(length=40), nullable=False),
        sa.Column("document_type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("provider_name", sa.String(length=64), nullable=True),
        sa.Column("raw_text", sa.Text(), nullable=True),
        sa.Column("extracted_fields", sa.JSON(), nullable=True),
        sa.Column("low_confidence_fields", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["shop_id"], ["shops.shop_id"]),
        sa.ForeignKeyConstraint(["task_run_id"], ["task_runs.task_run_id"]),
        sa.PrimaryKeyConstraint("ocr_document_id"),
    )
    op.create_index(
        "ix_ocr_documents_shop_id_created_at",
        "ocr_documents",
        ["shop_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_ocr_documents_shop_id_created_at", table_name="ocr_documents")
    op.drop_table("ocr_documents")
