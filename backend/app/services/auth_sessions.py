from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import hashlib
import hmac
import secrets
import uuid

from sqlalchemy import and_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import AuthSession, OwnerAccount, Shop, ShopMembership

_PASSWORD_HASH_ITERATIONS = 310_000


@dataclass(frozen=True)
class IssuedAuthSession:
    access_token: str
    actor_id: str
    shop_id: str
    expires_at: datetime


@dataclass(frozen=True)
class ResolvedAuthSession:
    auth_session_id: str
    actor_id: str
    shop_id: str
    role: str


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def hash_session_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _hash_password(password: str, salt_hex: str) -> str:
    return hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        bytes.fromhex(salt_hex),
        _PASSWORD_HASH_ITERATIONS,
    ).hex()


def verify_password(password: str, password_hash: str, password_salt: str) -> bool:
    candidate_hash = _hash_password(password, password_salt)
    return hmac.compare_digest(candidate_hash, password_hash)


def authenticate_owner(db_session: Session, email: str, password: str) -> OwnerAccount | None:
    owner = db_session.scalar(
        select(OwnerAccount).where(
            OwnerAccount.email == email,
            OwnerAccount.status == "active",
        )
    )
    if owner is None:
        return None

    if not verify_password(password, owner.password_hash, owner.password_salt):
        return None

    return owner


def resolve_owner_membership_and_shop(
    db_session: Session, actor_id: str
) -> tuple[ShopMembership, Shop] | None:
    membership = db_session.scalar(
        select(ShopMembership)
        .where(
            ShopMembership.actor_id == actor_id,
        )
        .order_by(ShopMembership.is_default_shop.desc(), ShopMembership.created_at.asc())
    )
    if membership is None:
        return None

    shop = db_session.get(Shop, membership.shop_id)
    if shop is None:
        return None

    return membership, shop


def issue_auth_session(
    db_session: Session,
    *,
    actor_id: str,
    shop_id: str,
    ttl_minutes: int,
) -> IssuedAuthSession:
    now = _now()
    expires_at = now + timedelta(minutes=ttl_minutes)
    for _ in range(3):
        access_token = secrets.token_urlsafe(32)
        auth_session = AuthSession(
            auth_session_id=f"auth_{uuid.uuid4().hex}"[:40],
            actor_id=actor_id,
            shop_id=shop_id,
            session_token_hash=hash_session_token(access_token),
            status="active",
            expires_at=expires_at,
            revoked_at=None,
            created_at=now,
            updated_at=now,
        )
        db_session.add(auth_session)
        try:
            db_session.commit()
            return IssuedAuthSession(
                access_token=access_token,
                actor_id=actor_id,
                shop_id=shop_id,
                expires_at=expires_at,
            )
        except IntegrityError:
            db_session.rollback()

    raise RuntimeError("Unable to issue unique auth session token")


def resolve_auth_session(db_session: Session, bearer_token: str) -> ResolvedAuthSession | None:
    token_hash = hash_session_token(bearer_token)
    now = _now()

    row = db_session.execute(
        select(AuthSession, ShopMembership, OwnerAccount)
        .join(
            ShopMembership,
            and_(
                ShopMembership.shop_id == AuthSession.shop_id,
                ShopMembership.actor_id == AuthSession.actor_id,
            ),
        )
        .join(OwnerAccount, OwnerAccount.actor_id == AuthSession.actor_id)
        .where(
            AuthSession.session_token_hash == token_hash,
            AuthSession.status == "active",
            AuthSession.revoked_at.is_(None),
            AuthSession.expires_at > now,
            OwnerAccount.status == "active",
        )
    ).first()
    if row is None:
        return None

    auth_session, membership, _ = row
    return ResolvedAuthSession(
        auth_session_id=auth_session.auth_session_id,
        actor_id=auth_session.actor_id,
        shop_id=auth_session.shop_id,
        role=membership.role,
    )
