from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
import hashlib
import os

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.models import OwnerAccount, SessionRecord, Shop, ShopMembership


@dataclass(frozen=True)
class BootstrapContext:
    shop: Shop
    session: SessionRecord


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _build_default_shop(settings: Settings, now: datetime) -> Shop:
    return Shop(
        shop_id=settings.default_shop_id,
        name="\u6f14\u793a\u5e97\u94fa",
        owner_name="\u9ed8\u8ba4\u8001\u677f",
        industry="retail",
        locale="zh-CN",
        timezone="Asia/Shanghai",
        require_price_confirmation=True,
        require_new_item_confirmation=True,
        low_confidence_threshold=Decimal("0.8500"),
        default_low_stock_threshold=None,
        created_at=now,
        updated_at=now,
    )


def _build_default_session(settings: Settings, shop_id: str, now: datetime) -> SessionRecord:
    return SessionRecord(
        session_id=settings.default_session_id,
        shop_id=shop_id,
        session_type="workgroup",
        title="\u6570\u5b57\u5458\u5de5\u5de5\u4f5c\u7fa4",
        participants=["xiaoya", "laoli"],
        last_event_seq=0,
        last_message_at=None,
        created_at=now,
        updated_at=now,
    )


def _hash_password(password: str) -> tuple[str, str]:
    salt = os.urandom(16)
    password_hash = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 310_000)
    return password_hash.hex(), salt.hex()


def _build_default_owner(settings: Settings, now: datetime) -> OwnerAccount:
    password_hash, password_salt = _hash_password(settings.seed_owner_password)
    return OwnerAccount(
        actor_id=settings.default_owner_actor_id,
        email=settings.seed_owner_email,
        display_name=settings.seed_owner_display_name,
        password_hash=password_hash,
        password_salt=password_salt,
        status="active",
        created_at=now,
        updated_at=now,
    )


def _build_default_membership(settings: Settings, shop_id: str, now: datetime) -> ShopMembership:
    membership_id = f"mship_{shop_id}_{settings.default_owner_actor_id}"[:40]
    return ShopMembership(
        membership_id=membership_id,
        shop_id=shop_id,
        actor_id=settings.default_owner_actor_id,
        role="owner",
        is_default_shop=True,
        created_at=now,
        updated_at=now,
    )


def ensure_default_shop(db_session: Session) -> Shop:
    settings = get_settings()
    shop = db_session.get(Shop, settings.default_shop_id)
    if shop is not None:
        return shop

    shop = _build_default_shop(settings, _now())
    db_session.add(shop)

    try:
        db_session.commit()
    except IntegrityError:
        db_session.rollback()
        shop = db_session.get(Shop, settings.default_shop_id)
        if shop is None:
            raise
        return shop

    return shop


def ensure_default_session(db_session: Session, shop: Shop) -> SessionRecord:
    settings = get_settings()
    session_record = db_session.get(SessionRecord, settings.default_session_id)
    if session_record is not None:
        return session_record

    session_record = _build_default_session(settings, shop.shop_id, _now())
    db_session.add(session_record)

    try:
        db_session.commit()
    except IntegrityError:
        db_session.rollback()
        session_record = db_session.get(SessionRecord, settings.default_session_id)
        if session_record is None:
            raise
        return session_record

    return session_record


def ensure_default_owner_membership(db_session: Session, shop: Shop) -> OwnerAccount:
    settings = get_settings()
    owner = db_session.get(OwnerAccount, settings.default_owner_actor_id)
    if owner is None:
        owner = _build_default_owner(settings, _now())
        db_session.add(owner)

        try:
            db_session.commit()
        except IntegrityError:
            db_session.rollback()
            owner = db_session.get(OwnerAccount, settings.default_owner_actor_id)
            if owner is None:
                raise

    membership = db_session.scalar(
        select(ShopMembership).where(
            ShopMembership.shop_id == shop.shop_id,
            ShopMembership.actor_id == settings.default_owner_actor_id,
        )
    )
    if membership is not None:
        return owner

    membership = _build_default_membership(settings, shop.shop_id, _now())
    db_session.add(membership)

    try:
        db_session.commit()
    except IntegrityError:
        db_session.rollback()
        membership = db_session.scalar(
            select(ShopMembership).where(
                ShopMembership.shop_id == shop.shop_id,
                ShopMembership.actor_id == settings.default_owner_actor_id,
            )
        )
        if membership is None:
            raise

    return owner


def ensure_default_context(db_session: Session) -> BootstrapContext:
    shop = ensure_default_shop(db_session)
    ensure_default_owner_membership(db_session, shop)
    session_record = ensure_default_session(db_session, shop)
    return BootstrapContext(shop=shop, session=session_record)
