from alembic import op
import sqlalchemy as sa


revision = "20260407_01"
down_revision = "20260405_05"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "pilot_controls",
        sa.Column("shop_id", sa.String(length=40), nullable=False),
        sa.Column("trial_provider_profile", sa.String(length=120), nullable=False),
        sa.Column("approved_calibration_artifact_id", sa.String(length=80), nullable=True),
        sa.Column("approved_calibration_report_path", sa.String(length=512), nullable=True),
        sa.Column("cutover_mode", sa.String(length=24), nullable=False),
        sa.Column("opened_at", sa.DateTime(), nullable=True),
        sa.Column("opened_by_actor_id", sa.String(length=40), nullable=True),
        sa.Column("closed_at", sa.DateTime(), nullable=True),
        sa.Column("closed_by_actor_id", sa.String(length=40), nullable=True),
        sa.Column("last_preflight_at", sa.DateTime(), nullable=True),
        sa.Column("last_preflight_status", sa.String(length=24), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "cutover_mode IN ('closed', 'shadow', 'open')",
            name="ck_pilot_controls_cutover_mode",
        ),
        sa.ForeignKeyConstraint(["shop_id"], ["shops.shop_id"]),
        sa.PrimaryKeyConstraint("shop_id"),
    )


def downgrade() -> None:
    op.drop_table("pilot_controls")
