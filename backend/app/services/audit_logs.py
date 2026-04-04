from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.ids import new_prefixed_id
from app.models import AuditLog, InventoryEvent, InventoryItem


class UnsupportedAuditScopeError(ValueError):
    pass


@dataclass(frozen=True)
class AuditLogListPage:
    items: list[AuditLog]


def list_audit_logs(
    db_session: Session,
    *,
    shop_id: str,
    scope: str,
    limit: int,
) -> AuditLogListPage:
    if scope != "inventory":
        raise UnsupportedAuditScopeError(scope)

    safe_limit = max(1, min(limit, 50))
    statement = (
        select(AuditLog)
        .where(
            AuditLog.shop_id == shop_id,
            AuditLog.scope == scope,
        )
        .order_by(AuditLog.created_at.desc(), AuditLog.audit_log_id.desc())
        .limit(safe_limit)
    )
    return AuditLogListPage(items=list(db_session.scalars(statement)))


def append_inventory_stock_in_audit_log(
    db_session: Session,
    *,
    shop_id: str,
    task_run_id: str,
    actor_id: str,
    confirmation_id: str,
    item: InventoryItem,
    inventory_event: InventoryEvent,
) -> AuditLog:
    log = AuditLog(
        audit_log_id=new_prefixed_id("audit"),
        shop_id=shop_id,
        scope="inventory",
        action="inventory.stock_in_confirmed",
        actor_type="owner",
        actor_id=actor_id,
        task_run_id=task_run_id,
        target_type="inventory_item",
        target_id=item.item_id,
        metadata_json={
            "confirmation_id": confirmation_id,
            "inventory_event_id": inventory_event.inventory_event_id,
            "event_type": inventory_event.event_type,
            "item_id": item.item_id,
            "item_name": item.name,
            "quantity_delta": float(inventory_event.quantity_delta),
            "quantity_after": float(inventory_event.quantity_after),
            "unit": item.default_unit,
            "price": float(inventory_event.price or 0),
            "source": inventory_event.source,
        },
        created_at=datetime.now(UTC).replace(tzinfo=None),
    )
    db_session.add(log)
    db_session.flush()
    return log
