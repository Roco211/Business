from dataclasses import dataclass
from datetime import datetime, timezone
UTC = timezone.utc
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.ids import new_prefixed_id
from app.models import Alert, InventoryItem


LOW_STOCK_ALERT_TYPE = "low-stock"


@dataclass(frozen=True)
class AlertListPage:
    items: list[Alert]


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _load_open_alerts(
    db_session: Session,
    *,
    shop_id: str,
    item_id: str,
) -> list[Alert]:
    statement = (
        select(Alert)
        .where(
            Alert.shop_id == shop_id,
            Alert.item_id == item_id,
            Alert.alert_type == LOW_STOCK_ALERT_TYPE,
            Alert.status == "open",
        )
        .order_by(Alert.created_at.desc(), Alert.alert_id.desc())
    )
    return list(db_session.scalars(statement))


def _resolve_alert(alert: Alert, *, now: datetime) -> None:
    alert.status = "resolved"
    alert.resolved_at = now


def refresh_low_stock_alert_for_item(
    db_session: Session,
    *,
    item: InventoryItem,
) -> Alert | None:
    now = _now()
    open_alerts = _load_open_alerts(db_session, shop_id=item.shop_id, item_id=item.item_id)
    primary_alert = open_alerts[0] if open_alerts else None

    for extra in open_alerts[1:]:
        _resolve_alert(extra, now=now)

    threshold = Decimal(item.low_stock_threshold) if item.low_stock_threshold is not None else None
    stock = Decimal(item.current_stock)

    if threshold is None:
        if primary_alert is not None:
            _resolve_alert(primary_alert, now=now)
        db_session.flush()
        return None

    if stock <= threshold:
        if primary_alert is None:
            primary_alert = Alert(
                alert_id=new_prefixed_id("alert"),
                shop_id=item.shop_id,
                alert_type=LOW_STOCK_ALERT_TYPE,
                item_id=item.item_id,
                status="open",
                stock=stock,
                threshold=threshold,
                created_at=now,
                resolved_at=None,
            )
            db_session.add(primary_alert)
        else:
            primary_alert.stock = stock
            primary_alert.threshold = threshold
            primary_alert.status = "open"
            primary_alert.resolved_at = None
        db_session.flush()
        return primary_alert

    if primary_alert is not None:
        _resolve_alert(primary_alert, now=now)
    db_session.flush()
    return None


def list_low_stock_alerts(
    db_session: Session,
    *,
    shop_id: str,
    limit: int,
) -> AlertListPage:
    safe_limit = max(1, min(limit, 50))
    statement = (
        select(Alert)
        .where(
            Alert.shop_id == shop_id,
            Alert.alert_type == LOW_STOCK_ALERT_TYPE,
            Alert.status == "open",
        )
        .order_by(Alert.created_at.desc(), Alert.alert_id.desc())
        .limit(safe_limit)
    )
    return AlertListPage(items=list(db_session.scalars(statement)))
