from alembic import op
import sqlalchemy as sa


revision = "20260405_03"
down_revision = "20260405_02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "media_uploads",
        sa.Column("media_id", sa.String(length=40), nullable=False),
        sa.Column("shop_id", sa.String(length=40), nullable=False),
        sa.Column("uploader_actor_type", sa.String(length=16), nullable=False),
        sa.Column("uploader_actor_id", sa.String(length=40), nullable=False),
        sa.Column("media_type", sa.String(length=24), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=120), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("upload_url", sa.String(length=255), nullable=False),
        sa.Column("public_url", sa.String(length=255), nullable=False),
        sa.Column("checksum_sha256", sa.String(length=128), nullable=True),
        sa.Column("uploaded_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["shop_id"], ["shops.shop_id"]),
        sa.PrimaryKeyConstraint("media_id"),
    )
    op.create_index(
        "ix_media_uploads_shop_id_created_at",
        "media_uploads",
        ["shop_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_media_uploads_shop_id_created_at", table_name="media_uploads")
    op.drop_table("media_uploads")
