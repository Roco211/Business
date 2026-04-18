from alembic import op
import sqlalchemy as sa


revision = "20260418_01"
down_revision = "20260407_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "v2_accounts",
        sa.Column("account_id", sa.String(length=40), nullable=False),
        sa.Column("email", sa.String(length=160), nullable=False),
        sa.Column("display_name", sa.String(length=80), nullable=False),
        sa.Column("password_hash", sa.String(length=256), nullable=False),
        sa.Column("password_salt", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("account_id"),
        sa.UniqueConstraint("email"),
    )
    op.create_table(
        "v2_tenants",
        sa.Column("tenant_id", sa.String(length=40), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("slug", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("plan_code", sa.String(length=40), nullable=False),
        sa.Column("owner_account_id", sa.String(length=40), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["owner_account_id"], ["v2_accounts.account_id"]),
        sa.PrimaryKeyConstraint("tenant_id"),
        sa.UniqueConstraint("slug"),
    )
    op.create_table(
        "v2_shops",
        sa.Column("shop_id", sa.String(length=40), nullable=False),
        sa.Column("tenant_id", sa.String(length=40), nullable=False),
        sa.Column("code", sa.String(length=40), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("locale", sa.String(length=16), nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["v2_tenants.tenant_id"]),
        sa.PrimaryKeyConstraint("shop_id"),
        sa.UniqueConstraint("tenant_id", "code", name="uq_v2_shops_tenant_code"),
    )
    op.create_index("ix_v2_shops_tenant_id", "v2_shops", ["tenant_id"], unique=False)
    op.create_table(
        "v2_tenant_memberships",
        sa.Column("membership_id", sa.String(length=40), nullable=False),
        sa.Column("tenant_id", sa.String(length=40), nullable=False),
        sa.Column("account_id", sa.String(length=40), nullable=False),
        sa.Column("role_key", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("joined_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["v2_accounts.account_id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["v2_tenants.tenant_id"]),
        sa.PrimaryKeyConstraint("membership_id"),
        sa.UniqueConstraint("tenant_id", "account_id", name="uq_v2_tenant_memberships_tenant_account"),
    )
    op.create_index(
        "ix_v2_tenant_memberships_account_id",
        "v2_tenant_memberships",
        ["account_id"],
        unique=False,
    )
    op.create_index(
        "ix_v2_tenant_memberships_tenant_id",
        "v2_tenant_memberships",
        ["tenant_id"],
        unique=False,
    )
    op.create_table(
        "v2_shop_accesses",
        sa.Column("shop_access_id", sa.String(length=40), nullable=False),
        sa.Column("tenant_id", sa.String(length=40), nullable=False),
        sa.Column("shop_id", sa.String(length=40), nullable=False),
        sa.Column("membership_id", sa.String(length=40), nullable=False),
        sa.Column("access_level", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["membership_id"], ["v2_tenant_memberships.membership_id"]),
        sa.ForeignKeyConstraint(["shop_id"], ["v2_shops.shop_id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["v2_tenants.tenant_id"]),
        sa.PrimaryKeyConstraint("shop_access_id"),
        sa.UniqueConstraint("shop_id", "membership_id", name="uq_v2_shop_accesses_shop_membership"),
    )
    op.create_index("ix_v2_shop_accesses_shop_id", "v2_shop_accesses", ["shop_id"], unique=False)
    op.create_index("ix_v2_shop_accesses_tenant_id", "v2_shop_accesses", ["tenant_id"], unique=False)
    op.create_table(
        "v2_auth_sessions",
        sa.Column("auth_session_id", sa.String(length=40), nullable=False),
        sa.Column("account_id", sa.String(length=40), nullable=False),
        sa.Column("access_token_hash", sa.String(length=256), nullable=False),
        sa.Column("refresh_token_hash", sa.String(length=256), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["v2_accounts.account_id"]),
        sa.PrimaryKeyConstraint("auth_session_id"),
        sa.UniqueConstraint("access_token_hash"),
        sa.UniqueConstraint("refresh_token_hash"),
    )
    op.create_index("ix_v2_auth_sessions_account_id", "v2_auth_sessions", ["account_id"], unique=False)
    op.create_table(
        "v2_context_sessions",
        sa.Column("context_session_id", sa.String(length=40), nullable=False),
        sa.Column("auth_session_id", sa.String(length=40), nullable=False),
        sa.Column("account_id", sa.String(length=40), nullable=False),
        sa.Column("tenant_id", sa.String(length=40), nullable=False),
        sa.Column("shop_id", sa.String(length=40), nullable=False),
        sa.Column("membership_id", sa.String(length=40), nullable=False),
        sa.Column("permission_snapshot", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["v2_accounts.account_id"]),
        sa.ForeignKeyConstraint(["auth_session_id"], ["v2_auth_sessions.auth_session_id"]),
        sa.ForeignKeyConstraint(["membership_id"], ["v2_tenant_memberships.membership_id"]),
        sa.ForeignKeyConstraint(["shop_id"], ["v2_shops.shop_id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["v2_tenants.tenant_id"]),
        sa.PrimaryKeyConstraint("context_session_id"),
    )
    op.create_index("ix_v2_context_sessions_account_id", "v2_context_sessions", ["account_id"], unique=False)
    op.create_index("ix_v2_context_sessions_shop_id", "v2_context_sessions", ["shop_id"], unique=False)
    op.create_index("ix_v2_context_sessions_tenant_id", "v2_context_sessions", ["tenant_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_v2_context_sessions_tenant_id", table_name="v2_context_sessions")
    op.drop_index("ix_v2_context_sessions_shop_id", table_name="v2_context_sessions")
    op.drop_index("ix_v2_context_sessions_account_id", table_name="v2_context_sessions")
    op.drop_table("v2_context_sessions")
    op.drop_index("ix_v2_auth_sessions_account_id", table_name="v2_auth_sessions")
    op.drop_table("v2_auth_sessions")
    op.drop_index("ix_v2_shop_accesses_tenant_id", table_name="v2_shop_accesses")
    op.drop_index("ix_v2_shop_accesses_shop_id", table_name="v2_shop_accesses")
    op.drop_table("v2_shop_accesses")
    op.drop_index("ix_v2_tenant_memberships_tenant_id", table_name="v2_tenant_memberships")
    op.drop_index("ix_v2_tenant_memberships_account_id", table_name="v2_tenant_memberships")
    op.drop_table("v2_tenant_memberships")
    op.drop_index("ix_v2_shops_tenant_id", table_name="v2_shops")
    op.drop_table("v2_shops")
    op.drop_table("v2_tenants")
    op.drop_table("v2_accounts")
