from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Alert, AuditLog, Confirmation, InventoryEvent, InventoryItem, SessionRecord, Shop, TaskRun
from app.services.alerts import refresh_low_stock_alert_for_item
from app.services.audit_logs import append_inventory_stock_out_audit_log
from app.services.confirmations import approve_confirmation
from app.services.inventory_events import append_stock_out_event
from app.services.inventory_items import (
    ApprovedFieldsValidationError,
    InventoryItemAmbiguousError,
    InventoryItemInactiveError,
    InventoryItemNotFoundError,
)
from app.services.runtime_messages import write_runtime_message
from app.services.session_stream import append_alert_updated_event, append_inventory_updated_event
from app.services.task_runs import resolve_awaiting_confirmation_task_run


@dataclass(frozen=True)
class ApprovedStockOutFields:
    item_id: str | None
    item_name: str | None
    stock_out_quantity: Decimal
    reason: str


@dataclass(frozen=True)
class ApprovedStockOutCommitResult:
    confirmation: Confirmation
    task_run: TaskRun
    inventory_item: InventoryItem
    inventory_event: InventoryEvent
    audit_log: AuditLog
    alert: Alert | None


def _format_decimal(value: Decimal) -> str:
    text = format(value.normalize(), "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


def _require_context(
    db_session: Session,
    *,
    confirmation: Confirmation,
) -> tuple[TaskRun, SessionRecord, Shop]:
    task_run = db_session.get(TaskRun, confirmation.task_run_id)
    if task_run is None:
        raise LookupError(confirmation.task_run_id)

    session_record = db_session.get(SessionRecord, task_run.session_id)
    if session_record is None:
        raise LookupError(task_run.session_id)

    shop = db_session.get(Shop, session_record.shop_id)
    if shop is None:
        raise LookupError(session_record.shop_id)

    return task_run, session_record, shop


def _parse_approved_stock_out_fields(payload: dict[str, object]) -> ApprovedStockOutFields:
    raw_item_id = payload.get("item_id")
    item_id = str(raw_item_id).strip() or None if raw_item_id is not None else None
    raw_item_name = payload.get("item_name")
    item_name = raw_item_name.strip() if isinstance(raw_item_name, str) and raw_item_name.strip() else None
    raw_reason = payload.get("reason")
    reason = raw_reason.strip() if isinstance(raw_reason, str) and raw_reason.strip() else None

    if item_id is None and item_name is None:
        raise ApprovedFieldsValidationError("item_name is required when item_id is absent")
    if reason is None:
        raise ApprovedFieldsValidationError("reason is required")

    try:
        stock_out_quantity = Decimal(str(payload.get("stock_out_quantity")))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ApprovedFieldsValidationError("stock_out_quantity must be numeric") from exc

    if stock_out_quantity <= 0:
        raise ApprovedFieldsValidationError("stock_out_quantity must be > 0")

    return ApprovedStockOutFields(
        item_id=item_id,
        item_name=item_name,
        stock_out_quantity=stock_out_quantity,
        reason=reason,
    )


def _resolve_inventory_item_for_stock_out(
    db_session: Session,
    *,
    shop: Shop,
    fields: ApprovedStockOutFields,
) -> InventoryItem:
    if fields.item_id is not None:
        item = db_session.get(InventoryItem, fields.item_id)
        if item is None or item.shop_id != shop.shop_id:
            raise InventoryItemNotFoundError(fields.item_id)
        if not item.is_active:
            raise InventoryItemInactiveError(fields.item_id)
        return item

    matches = list(
        db_session.scalars(
            select(InventoryItem).where(
                InventoryItem.shop_id == shop.shop_id,
                InventoryItem.name == (fields.item_name or ""),
            )
        )
    )
    active_matches = [item for item in matches if item.is_active]
    if len(active_matches) > 1:
        raise InventoryItemAmbiguousError(fields.item_name or "")
    if len(active_matches) == 1:
        return active_matches[0]
    if matches:
        raise InventoryItemInactiveError(fields.item_name or "")
    raise InventoryItemNotFoundError(fields.item_name or "")


def commit_approved_stock_out_confirmation(
    db_session: Session,
    *,
    confirmation_id: str,
    payload_fields: dict[str, object],
    approved_by_actor_id: str,
) -> ApprovedStockOutCommitResult:
    try:
        confirmation = db_session.get(Confirmation, confirmation_id)
        if confirmation is None:
            raise LookupError(confirmation_id)

        task_run, session_record, shop = _require_context(db_session, confirmation=confirmation)
        approved_fields = _parse_approved_stock_out_fields(payload_fields)

        confirmation = approve_confirmation(
            db_session,
            confirmation_id=confirmation_id,
            resolution_payload={"fields": payload_fields},
            approved_by_actor_id=approved_by_actor_id,
        )
        inventory_item = _resolve_inventory_item_for_stock_out(
            db_session,
            shop=shop,
            fields=approved_fields,
        )
        previous_quantity = Decimal(inventory_item.current_stock)
        if approved_fields.stock_out_quantity > previous_quantity:
            raise ApprovedFieldsValidationError("stock_out_quantity exceeds current stock")

        inventory_event = append_stock_out_event(
            db_session,
            item=inventory_item,
            stock_out_quantity=approved_fields.stock_out_quantity,
            actor_id=approved_by_actor_id,
            reason=approved_fields.reason,
            task_run_id=task_run.task_run_id,
            source="runtime-stock-out-confirmed",
        )
        alert = refresh_low_stock_alert_for_item(
            db_session,
            item=inventory_item,
        )
        append_inventory_updated_event(
            db_session,
            session_id=session_record.session_id,
            item=inventory_item,
            inventory_event=inventory_event,
        )
        append_alert_updated_event(
            db_session,
            session_id=session_record.session_id,
            item=inventory_item,
            alert=alert,
            occurred_at=inventory_event.created_at,
        )
        audit_log = append_inventory_stock_out_audit_log(
            db_session,
            item=inventory_item,
            inventory_event=inventory_event,
            previous_quantity=float(previous_quantity),
            actor_id=approved_by_actor_id,
            reason=approved_fields.reason,
            task_run_id=task_run.task_run_id,
            confirmation_id=confirmation.confirmation_id,
        )
        task_run = resolve_awaiting_confirmation_task_run(
            db_session,
            task_run_id=task_run.task_run_id,
            result_summary=(
                f"Owner approved stock-out for {inventory_item.name} "
                f"(-{_format_decimal(approved_fields.stock_out_quantity)} {inventory_item.default_unit}). "
                f"Current stock: {_format_decimal(Decimal(inventory_item.current_stock))} {inventory_item.default_unit}."
            ),
        )
        write_runtime_message(
            db_session,
            session_id=session_record.session_id,
            task_run_id=task_run.task_run_id,
            text=(
                f"Mock runtime: stock-out committed for {inventory_item.name} "
                f"(-{_format_decimal(approved_fields.stock_out_quantity)} {inventory_item.default_unit}). "
                f"Current stock: {_format_decimal(Decimal(inventory_item.current_stock))} {inventory_item.default_unit}."
            ),
        )
        db_session.commit()
        return ApprovedStockOutCommitResult(
            confirmation=confirmation,
            task_run=task_run,
            inventory_item=inventory_item,
            inventory_event=inventory_event,
            audit_log=audit_log,
            alert=alert,
        )
    except Exception:
        db_session.rollback()
        raise
