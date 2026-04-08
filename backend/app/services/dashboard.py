from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Alert, Confirmation, InventoryEvent, SessionRecord, Shop, TaskRun
from app.services.alerts import LOW_STOCK_ALERT_TYPE


@dataclass(frozen=True)
class DashboardSummary:
    shop_id: str
    today_stock_in_count: int
    today_task_completed_count: int
    pending_confirmations_count: int
    open_low_stock_alert_count: int
    last_inventory_event_at: datetime | None


def _today_bounds_for_shop(shop: Shop) -> tuple[datetime, datetime]:
    now_utc = datetime.now(UTC)
    local_now = now_utc.astimezone(ZoneInfo(shop.timezone))
    local_day_start = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
    local_day_end = local_day_start + timedelta(days=1)
    return (
        local_day_start.astimezone(UTC).replace(tzinfo=None),
        local_day_end.astimezone(UTC).replace(tzinfo=None),
    )


def get_dashboard_summary(
    db_session: Session,
    *,
    shop: Shop,
) -> DashboardSummary:
    day_start, day_end = _today_bounds_for_shop(shop)

    today_stock_in_count = db_session.scalar(
        select(func.count())
        .select_from(InventoryEvent)
        .where(
            InventoryEvent.shop_id == shop.shop_id,
            InventoryEvent.event_type == "stock-in",
            InventoryEvent.created_at >= day_start,
            InventoryEvent.created_at < day_end,
        )
    )
    today_task_completed_count = db_session.scalar(
        select(func.count())
        .select_from(TaskRun)
        .join(SessionRecord, SessionRecord.session_id == TaskRun.session_id)
        .where(
            SessionRecord.shop_id == shop.shop_id,
            TaskRun.status == "completed",
            TaskRun.completed_at.is_not(None),
            TaskRun.completed_at >= day_start,
            TaskRun.completed_at < day_end,
        )
    )
    pending_confirmations_count = db_session.scalar(
        select(func.count())
        .select_from(Confirmation)
        .join(TaskRun, TaskRun.task_run_id == Confirmation.task_run_id)
        .join(SessionRecord, SessionRecord.session_id == TaskRun.session_id)
        .where(
            SessionRecord.shop_id == shop.shop_id,
            Confirmation.status == "pending",
        )
    )
    open_low_stock_alert_count = db_session.scalar(
        select(func.count())
        .select_from(Alert)
        .where(
            Alert.shop_id == shop.shop_id,
            Alert.alert_type == LOW_STOCK_ALERT_TYPE,
            Alert.status == "open",
        )
    )
    last_inventory_event_at = db_session.scalar(
        select(func.max(InventoryEvent.created_at)).where(InventoryEvent.shop_id == shop.shop_id)
    )

    return DashboardSummary(
        shop_id=shop.shop_id,
        today_stock_in_count=int(today_stock_in_count or 0),
        today_task_completed_count=int(today_task_completed_count or 0),
        pending_confirmations_count=int(pending_confirmations_count or 0),
        open_low_stock_alert_count=int(open_low_stock_alert_count or 0),
        last_inventory_event_at=last_inventory_event_at,
    )
