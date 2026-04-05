from alembic import op
import sqlalchemy as sa


revision = "20260405_05"
down_revision = "20260405_04"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "owner_accounts",
        sa.Column("actor_id", sa.String(length=40), nullable=False),
        sa.Column("email", sa.String(length=160), nullable=False),
        sa.Column("display_name", sa.String(length=80), nullable=False),
        sa.Column("password_hash", sa.String(length=256), nullable=False),
        sa.Column("password_salt", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("actor_id"),
        sa.UniqueConstraint("email"),
    )

    op.create_table(
        "shop_memberships",
        sa.Column("membership_id", sa.String(length=40), nullable=False),
        sa.Column("shop_id", sa.String(length=40), nullable=False),
        sa.Column("actor_id", sa.String(length=40), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("is_default_shop", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["actor_id"], ["owner_accounts.actor_id"]),
        sa.ForeignKeyConstraint(["shop_id"], ["shops.shop_id"]),
        sa.PrimaryKeyConstraint("membership_id"),
        sa.UniqueConstraint("shop_id", "actor_id", name="uq_shop_memberships_shop_actor"),
    )
    op.create_index("ix_shop_memberships_shop_id", "shop_memberships", ["shop_id"], unique=False)
    op.create_index("ix_shop_memberships_actor_id", "shop_memberships", ["actor_id"], unique=False)

    op.create_table(
        "auth_sessions",
        sa.Column("auth_session_id", sa.String(length=40), nullable=False),
        sa.Column("actor_id", sa.String(length=40), nullable=False),
        sa.Column("shop_id", sa.String(length=40), nullable=False),
        sa.Column("session_token_hash", sa.String(length=256), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["actor_id"], ["owner_accounts.actor_id"]),
        sa.ForeignKeyConstraint(["shop_id"], ["shops.shop_id"]),
        sa.PrimaryKeyConstraint("auth_session_id"),
        sa.UniqueConstraint("session_token_hash"),
    )
    op.create_index("ix_auth_sessions_actor_id", "auth_sessions", ["actor_id"], unique=False)
    op.create_index("ix_auth_sessions_shop_id", "auth_sessions", ["shop_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_auth_sessions_shop_id", table_name="auth_sessions")
    op.drop_index("ix_auth_sessions_actor_id", table_name="auth_sessions")
    op.drop_table("auth_sessions")

    op.drop_index("ix_shop_memberships_actor_id", table_name="shop_memberships")
    op.drop_index("ix_shop_memberships_shop_id", table_name="shop_memberships")
    op.drop_table("shop_memberships")

    op.drop_table("owner_accounts")
