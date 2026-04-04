from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import SessionRecord, Shop


@dataclass(frozen=True)
class BootstrapContext:
    shop: Shop
    session: SessionRecord


def ensure_default_context(db_session: Session) -> BootstrapContext:
    settings = get_settings()
    now = datetime.now(UTC).replace(tzinfo=None)

    shop = db_session.get(Shop, settings.default_shop_id)
    if shop is None:
        shop = Shop(
            shop_id=settings.default_shop_id,
            name="演示店铺",
            owner_name="默认老板",
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
        db_session.add(shop)
        db_session.flush()

    session_record = db_session.get(SessionRecord, settings.default_session_id)
    if session_record is None:
        session_record = SessionRecord(
            session_id=settings.default_session_id,
            shop_id=shop.shop_id,
            session_type="workgroup",
            title="数字员工工作群",
            participants=["xiaoya", "laoli"],
            last_event_seq=0,
            last_message_at=None,
            created_at=now,
            updated_at=now,
        )
        db_session.add(session_record)
        db_session.flush()

    db_session.commit()
    return BootstrapContext(shop=shop, session=session_record)
