from dataclasses import dataclass
from datetime import timedelta
import hashlib
import hmac
import secrets
import uuid

from sqlalchemy import and_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import (
    V2Account,
    V2AuthSession,
    V2ContextSession,
    V2Shop,
    V2ShopAccess,
    V2Tenant,
    V2TenantMembership,
)
from app.services.v2_rbac import permissions_for_role
from app.services.v2_time import utc_now_naive

_PASSWORD_HASH_ITERATIONS = 310_000


@dataclass(frozen=True)
class IssuedV2AuthSession:
    access_token: str
    refresh_token: str
    account_id: str


@dataclass(frozen=True)
class ResolvedV2AuthSession:
    auth_session_id: str
    account_id: str


def hash_v2_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def hash_v2_password(password: str, salt_hex: str) -> str:
    return hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        bytes.fromhex(salt_hex),
        _PASSWORD_HASH_ITERATIONS,
    ).hex()


def verify_v2_password(password: str, password_hash: str, password_salt: str) -> bool:
    candidate_hash = hash_v2_password(password, password_salt)
    return hmac.compare_digest(candidate_hash, password_hash)


def authenticate_v2_account(db_session: Session, email: str, password: str) -> V2Account | None:
    account = db_session.scalar(
        select(V2Account).where(V2Account.email == email, V2Account.status == "active")
    )
    if account is None:
        return None
    if not verify_v2_password(password, account.password_hash, account.password_salt):
        return None
    return account


def issue_v2_auth_session(db_session: Session, *, account_id: str, ttl_minutes: int) -> IssuedV2AuthSession:
    now = utc_now_naive()
    access_token = secrets.token_urlsafe(32)
    refresh_token = secrets.token_urlsafe(32)
    auth_session = V2AuthSession(
        auth_session_id=f"v2auth_{uuid.uuid4().hex}"[:40],
        account_id=account_id,
        access_token_hash=hash_v2_token(access_token),
        refresh_token_hash=hash_v2_token(refresh_token),
        status="active",
        expires_at=now + timedelta(minutes=ttl_minutes),
        revoked_at=None,
        last_seen_at=now,
        created_at=now,
    )
    db_session.add(auth_session)
    db_session.commit()
    return IssuedV2AuthSession(
        access_token=access_token,
        refresh_token=refresh_token,
        account_id=account_id,
    )


def resolve_v2_auth_session(db_session: Session, bearer_token: str) -> ResolvedV2AuthSession | None:
    auth_session = db_session.scalar(
        select(V2AuthSession).where(
            V2AuthSession.access_token_hash == hash_v2_token(bearer_token),
            V2AuthSession.status == "active",
            V2AuthSession.revoked_at.is_(None),
            V2AuthSession.expires_at > utc_now_naive(),
        )
    )
    if auth_session is None:
        return None
    return ResolvedV2AuthSession(
        auth_session_id=auth_session.auth_session_id,
        account_id=auth_session.account_id,
    )


def get_v2_account(db_session: Session, account_id: str) -> V2Account | None:
    return db_session.scalar(
        select(V2Account).where(
            V2Account.account_id == account_id,
            V2Account.status == "active",
        )
    )


def revoke_v2_auth_session(db_session: Session, *, auth_session_id: str) -> bool:
    auth_session = db_session.scalar(
        select(V2AuthSession)
        .where(V2AuthSession.auth_session_id == auth_session_id)
        .execution_options(populate_existing=True)
    )
    if auth_session is None:
        return False
    if auth_session.status != "active":
        return False

    now = utc_now_naive()
    auth_session.status = "revoked"
    auth_session.revoked_at = now
    context_sessions = db_session.scalars(
        select(V2ContextSession).where(
            V2ContextSession.auth_session_id == auth_session_id,
            V2ContextSession.status == "active",
        )
    ).all()
    for context_session in context_sessions:
        context_session.status = "revoked"
    db_session.commit()
    return True


def rotate_v2_auth_session(
    db_session: Session,
    *,
    refresh_token: str,
    ttl_minutes: int,
) -> IssuedV2AuthSession | None:
    auth_session = db_session.scalar(
        select(V2AuthSession)
        .where(
            V2AuthSession.refresh_token_hash == hash_v2_token(refresh_token),
            V2AuthSession.status == "active",
            V2AuthSession.revoked_at.is_(None),
            V2AuthSession.expires_at > utc_now_naive(),
        )
        .execution_options(populate_existing=True)
    )
    if auth_session is None:
        return None

    account_id = auth_session.account_id
    try:
        revoke_v2_auth_session(db_session, auth_session_id=auth_session.auth_session_id)
        return issue_v2_auth_session(db_session, account_id=account_id, ttl_minutes=ttl_minutes)
    except IntegrityError:
        db_session.rollback()
        return None


def list_v2_tenants_for_account(db_session: Session, account_id: str) -> list[tuple[V2Tenant, V2TenantMembership]]:
    return list(
        db_session.execute(
            select(V2Tenant, V2TenantMembership)
            .join(V2TenantMembership, V2TenantMembership.tenant_id == V2Tenant.tenant_id)
            .where(
                V2TenantMembership.account_id == account_id,
                V2TenantMembership.status == "active",
                V2Tenant.status == "active",
            )
            .order_by(V2Tenant.created_at.asc(), V2Tenant.tenant_id.asc())
        ).all()
    )


def list_v2_accessible_shops(
    db_session: Session,
    *,
    account_id: str,
    tenant_id: str,
) -> list[tuple[V2Shop, V2ShopAccess, V2TenantMembership]]:
    return list(
        db_session.execute(
            select(V2Shop, V2ShopAccess, V2TenantMembership)
            .join(V2ShopAccess, V2ShopAccess.shop_id == V2Shop.shop_id)
            .join(V2TenantMembership, V2TenantMembership.membership_id == V2ShopAccess.membership_id)
            .where(
                V2Shop.tenant_id == tenant_id,
                V2ShopAccess.tenant_id == tenant_id,
                V2TenantMembership.tenant_id == tenant_id,
                V2TenantMembership.account_id == account_id,
                V2Shop.status == "active",
                V2ShopAccess.status == "active",
                V2TenantMembership.status == "active",
            )
            .order_by(V2Shop.code.asc(), V2Shop.shop_id.asc())
        ).all()
    )


def select_v2_context(
    db_session: Session,
    *,
    auth_session_id: str,
    account_id: str,
    tenant_id: str,
    shop_id: str,
    ttl_minutes: int,
) -> V2ContextSession | None:
    row = db_session.execute(
        select(V2TenantMembership, V2ShopAccess)
        .join(V2ShopAccess, V2ShopAccess.membership_id == V2TenantMembership.membership_id)
        .join(
            V2Shop,
            and_(
                V2Shop.shop_id == V2ShopAccess.shop_id,
                V2Shop.tenant_id == V2ShopAccess.tenant_id,
            ),
        )
        .where(
            V2TenantMembership.account_id == account_id,
            V2TenantMembership.tenant_id == tenant_id,
            V2TenantMembership.status == "active",
            V2ShopAccess.tenant_id == tenant_id,
            V2ShopAccess.shop_id == shop_id,
            V2ShopAccess.status == "active",
            V2Shop.status == "active",
        )
    ).first()
    if row is None:
        return None

    membership, _ = row
    now = utc_now_naive()
    context_session = V2ContextSession(
        context_session_id=f"ctx_{uuid.uuid4().hex}"[:40],
        auth_session_id=auth_session_id,
        account_id=account_id,
        tenant_id=tenant_id,
        shop_id=shop_id,
        membership_id=membership.membership_id,
        permission_snapshot={
            "role_key": membership.role_key,
            "permissions": permissions_for_role(membership.role_key),
        },
        status="active",
        expires_at=now + timedelta(minutes=ttl_minutes),
        created_at=now,
    )
    db_session.add(context_session)
    db_session.commit()
    return context_session
