from alembic import op
import sqlalchemy as sa


revision = "20260418_07"
down_revision = "20260418_06"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "v2_outbox_events",
        sa.Column("last_error_code", sa.String(length=80), nullable=True),
    )
    op.add_column(
        "v2_outbox_events",
        sa.Column("last_error_message", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "v2_outbox_events",
        sa.Column("processed_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "v2_outbox_events",
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.execute("UPDATE v2_outbox_events SET updated_at = created_at WHERE updated_at IS NULL")


def downgrade() -> None:
    op.drop_column("v2_outbox_events", "updated_at")
    op.drop_column("v2_outbox_events", "processed_at")
    op.drop_column("v2_outbox_events", "last_error_message")
    op.drop_column("v2_outbox_events", "last_error_code")
