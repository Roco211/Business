from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.services.v2_time import utc_now_naive


class V2Account(Base):
    __tablename__ = "v2_accounts"

    account_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    email: Mapped[str] = mapped_column(String(160), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(80), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(256), nullable=False)
    password_salt: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False, default=utc_now_naive)
    updated_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False, default=utc_now_naive)


class V2Tenant(Base):
    __tablename__ = "v2_tenants"

    tenant_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    slug: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    plan_code: Mapped[str] = mapped_column(String(40), nullable=False, default="trial")
    owner_account_id: Mapped[str] = mapped_column(ForeignKey("v2_accounts.account_id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False, default=utc_now_naive)
    updated_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False, default=utc_now_naive)


class V2Shop(Base):
    __tablename__ = "v2_shops"
    __table_args__ = (UniqueConstraint("tenant_id", "code", name="uq_v2_shops_tenant_code"),)

    shop_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("v2_tenants.tenant_id"), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(40), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    locale: Mapped[str] = mapped_column(String(16), nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False, default=utc_now_naive)
    updated_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False, default=utc_now_naive)


class V2TenantMembership(Base):
    __tablename__ = "v2_tenant_memberships"
    __table_args__ = (
        UniqueConstraint("tenant_id", "account_id", name="uq_v2_tenant_memberships_tenant_account"),
    )

    membership_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("v2_tenants.tenant_id"), nullable=False, index=True)
    account_id: Mapped[str] = mapped_column(ForeignKey("v2_accounts.account_id"), nullable=False, index=True)
    role_key: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    joined_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False, default=utc_now_naive)
    updated_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False, default=utc_now_naive)


class V2ShopAccess(Base):
    __tablename__ = "v2_shop_accesses"
    __table_args__ = (
        UniqueConstraint("shop_id", "membership_id", name="uq_v2_shop_accesses_shop_membership"),
    )

    shop_access_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("v2_tenants.tenant_id"), nullable=False, index=True)
    shop_id: Mapped[str] = mapped_column(ForeignKey("v2_shops.shop_id"), nullable=False, index=True)
    membership_id: Mapped[str] = mapped_column(
        ForeignKey("v2_tenant_memberships.membership_id"), nullable=False
    )
    access_level: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False, default=utc_now_naive)


class V2AuthSession(Base):
    __tablename__ = "v2_auth_sessions"

    auth_session_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    account_id: Mapped[str] = mapped_column(ForeignKey("v2_accounts.account_id"), nullable=False, index=True)
    access_token_hash: Mapped[str] = mapped_column(String(256), unique=True, nullable=False)
    refresh_token_hash: Mapped[str | None] = mapped_column(String(256), unique=True, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    expires_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False, default=utc_now_naive)


class V2ContextSession(Base):
    __tablename__ = "v2_context_sessions"

    context_session_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    auth_session_id: Mapped[str] = mapped_column(ForeignKey("v2_auth_sessions.auth_session_id"), nullable=False)
    account_id: Mapped[str] = mapped_column(ForeignKey("v2_accounts.account_id"), nullable=False, index=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("v2_tenants.tenant_id"), nullable=False, index=True)
    shop_id: Mapped[str] = mapped_column(ForeignKey("v2_shops.shop_id"), nullable=False, index=True)
    membership_id: Mapped[str] = mapped_column(
        ForeignKey("v2_tenant_memberships.membership_id"), nullable=False
    )
    permission_snapshot: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    expires_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False, default=utc_now_naive)
