from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models import Alert, AuditLog, Confirmation, InventoryEvent, InventoryItem, SessionRecord, Shop, TaskRun
from app.services.alerts import refresh_low_stock_alert_for_item
from app.services.audit_logs import append_inventory_stock_in_audit_log
from app.services.confirmations import approve_confirmation
from app.services.inventory_events import append_stock_in_event
from app.services.inventory_items import (
    ApprovedStockInFields,
    parse_approved_stock_in_fields,
    resolve_inventory_item_for_stock_in,
)
from app.services.runtime_messages import write_runtime_message
from app.services.session_stream import append_alert_updated_event, append_inventory_updated_event
from app.services.task_runs import resolve_awaiting_confirmation_task_run


@dataclass(frozen=True)
class ApprovedStockInCommitResult:
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


def commit_approved_stock_in_confirmation(
    db_session: Session,
    *,
    confirmation_id: str,
    payload_fields: dict[str, object],
    approved_by_actor_id: str,
) -> ApprovedStockInCommitResult:
    try:
        confirmation = db_session.get(Confirmation, confirmation_id)
        if confirmation is None:
            raise LookupError(confirmation_id)

        task_run, session_record, shop = _require_context(db_session, confirmation=confirmation)
        approved_fields: ApprovedStockInFields = parse_approved_stock_in_fields(payload_fields)

        confirmation = approve_confirmation(
            db_session,
            confirmation_id=confirmation_id,
            resolution_payload={"fields": payload_fields},
            approved_by_actor_id=approved_by_actor_id,
        )
        inventory_item = resolve_inventory_item_for_stock_in(
            db_session,
            shop=shop,
            fields=approved_fields,
        )
        inventory_event = append_stock_in_event(
            db_session,
            item=inventory_item,
            quantity=approved_fields.quantity,
            price=approved_fields.price,
            task_run_id=task_run.task_run_id,
            created_by=approved_by_actor_id,
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
        audit_log = append_inventory_stock_in_audit_log(
            db_session,
            shop_id=shop.shop_id,
            task_run_id=task_run.task_run_id,
            actor_id=approved_by_actor_id,
            confirmation_id=confirmation.confirmation_id,
            item=inventory_item,
            inventory_event=inventory_event,
        )
        task_run = resolve_awaiting_confirmation_task_run(
            db_session,
            task_run_id=task_run.task_run_id,
            result_summary=(
                f"Owner approved stock-in for {inventory_item.name} "
                f"(+{_format_decimal(approved_fields.quantity)} {inventory_item.default_unit}). "
                f"Current stock: {_format_decimal(inventory_item.current_stock)} {inventory_item.default_unit}."
            ),
        )
        write_runtime_message(
            db_session,
            session_id=session_record.session_id,
            task_run_id=task_run.task_run_id,
            text=(
                f"Mock runtime: stock-in committed for {inventory_item.name} "
                f"(+{_format_decimal(approved_fields.quantity)} {inventory_item.default_unit}). "
                f"Current stock: {_format_decimal(inventory_item.current_stock)} {inventory_item.default_unit}."
            ),
        )
        db_session.commit()
        return ApprovedStockInCommitResult(
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
