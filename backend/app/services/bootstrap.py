from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.models import SessionRecord, Shop


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


def ensure_default_context(db_session: Session) -> BootstrapContext:
    shop = ensure_default_shop(db_session)
    session_record = ensure_default_session(db_session, shop)
    return BootstrapContext(shop=shop, session=session_record)
