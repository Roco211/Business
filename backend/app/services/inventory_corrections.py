from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models import Alert, AuditLog, InventoryEvent, InventoryItem
from app.services.alerts import refresh_low_stock_alert_for_item
from app.services.audit_logs import append_inventory_correction_audit_log
from app.services.inventory_events import append_correction_event
from app.services.session_stream import (
    append_alert_updated_event,
    append_inventory_updated_event,
    find_shop_session_id,
)


class InventoryCorrectionValidationError(ValueError):
    pass


class InventoryCorrectionConflictError(ValueError):
    pass


class InventoryCorrectionItemNotFoundError(LookupError):
    pass


@dataclass(frozen=True)
class InventoryCorrectionResult:
    inventory_item: InventoryItem
    inventory_event: InventoryEvent
    audit_log: AuditLog
    alert: Alert | None


def _normalize_reason(reason: str) -> str:
    normalized = reason.strip()
    if not normalized:
        raise InventoryCorrectionValidationError("reason is required")
    return normalized


def _normalize_quantity(corrected_quantity: Decimal) -> Decimal:
    if corrected_quantity < 0:
        raise InventoryCorrectionValidationError("corrected_quantity must be >= 0")
    return corrected_quantity


def submit_inventory_correction(
    db_session: Session,
    *,
    shop_id: str,
    item_id: str,
    expected_quantity: Decimal,
    corrected_quantity: Decimal,
    reason: str,
    actor_id: str,
) -> InventoryCorrectionResult:
    try:
        item = db_session.get(InventoryItem, item_id)
        if item is None or item.shop_id != shop_id:
            raise InventoryCorrectionItemNotFoundError(item_id)
        if not item.is_active:
            raise InventoryCorrectionConflictError("inactive item cannot be corrected")

        normalized_expected_quantity = Decimal(expected_quantity)
        normalized_quantity = _normalize_quantity(Decimal(corrected_quantity))
        normalized_reason = _normalize_reason(reason)
        current_quantity = Decimal(item.current_stock)
        if current_quantity != normalized_expected_quantity:
            raise InventoryCorrectionConflictError("inventory changed since the ledger was loaded")

        previous_quantity = float(current_quantity)

        event = append_correction_event(
            db_session,
            item=item,
            corrected_quantity=normalized_quantity,
            actor_id=actor_id,
            reason=normalized_reason,
        )
        alert = refresh_low_stock_alert_for_item(
            db_session,
            item=item,
        )
        session_id = find_shop_session_id(db_session, shop_id=shop_id)
        append_inventory_updated_event(
            db_session,
            session_id=session_id,
            item=item,
            inventory_event=event,
        )
        append_alert_updated_event(
            db_session,
            session_id=session_id,
            item=item,
            alert=alert,
            occurred_at=event.created_at,
        )
        audit_log = append_inventory_correction_audit_log(
            db_session,
            item=item,
            inventory_event=event,
            previous_quantity=previous_quantity,
            actor_id=actor_id,
            reason=normalized_reason,
        )
        db_session.commit()
        return InventoryCorrectionResult(
            inventory_item=item,
            inventory_event=event,
            audit_log=audit_log,
            alert=alert,
        )
    except Exception:
        db_session.rollback()
        raise
