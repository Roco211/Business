from alembic import op
import sqlalchemy as sa


revision = "20260419_04"
down_revision = "20260419_03"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("v2_model_call_logs", sa.Column("prompt_version", sa.String(length=120), nullable=True))
    op.add_column("v2_model_call_logs", sa.Column("schema_version", sa.String(length=120), nullable=True))
    op.add_column("v2_model_call_logs", sa.Column("confidence_score", sa.Float(), nullable=True))
    op.add_column(
        "v2_model_call_logs",
        sa.Column("used_fallback", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("v2_model_call_logs", "used_fallback")
    op.drop_column("v2_model_call_logs", "confidence_score")
    op.drop_column("v2_model_call_logs", "schema_version")
    op.drop_column("v2_model_call_logs", "prompt_version")
