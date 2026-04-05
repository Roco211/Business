from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.models import Alert, AuditLog, Confirmation, InventoryEvent, InventoryItem, OcrDocument, SessionRecord, Shop, TaskRun
from app.services.alerts import refresh_low_stock_alert_for_item
from app.services.audit_logs import append_inventory_receipt_stock_in_audit_log
from app.services.confirmations import approve_confirmation
from app.services.inventory_events import append_stock_in_event
from app.services.inventory_items import (
    ApprovedFieldsValidationError,
    ApprovedStockInFields,
    parse_approved_stock_in_fields,
    resolve_inventory_item_for_stock_in,
)
from app.services.runtime_messages import write_runtime_message
from app.services.session_stream import append_alert_updated_event, append_inventory_updated_event
from app.services.task_runs import resolve_awaiting_confirmation_task_run


@dataclass(frozen=True)
class ApprovedReceiptLine:
    line_id: str
    fields: ApprovedStockInFields


@dataclass(frozen=True)
class ApprovedReceiptLineCommitResult:
    line_id: str
    inventory_item: InventoryItem
    inventory_event: InventoryEvent
    audit_log: AuditLog
    alert: Alert | None


@dataclass(frozen=True)
class ApprovedReceiptStockInCommitResult:
    confirmation: Confirmation
    task_run: TaskRun
    ocr_document: OcrDocument
    line_results: list[ApprovedReceiptLineCommitResult]


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


def _parse_receipt_items(payload_fields: dict[str, Any]) -> list[ApprovedReceiptLine]:
    raw_items = payload_fields.get("items")
    if not isinstance(raw_items, list) or len(raw_items) == 0:
        raise ApprovedFieldsValidationError("items must be a non-empty list")

    parsed: list[ApprovedReceiptLine] = []
    for index, raw_item in enumerate(raw_items, start=1):
        if not isinstance(raw_item, dict):
            raise ApprovedFieldsValidationError("items entries must be objects")
        raw_line_id = raw_item.get("line_id")
        line_id = str(raw_line_id).strip() if raw_line_id is not None else f"line_{index}"
        if not line_id:
            raise ApprovedFieldsValidationError("line_id must be a non-empty string when provided")
        parsed.append(
            ApprovedReceiptLine(
                line_id=line_id,
                fields=parse_approved_stock_in_fields(raw_item),
            )
        )
    return parsed


def _require_ocr_document(
    db_session: Session,
    *,
    confirmation: Confirmation,
) -> OcrDocument:
    raw_ocr_document_id = confirmation.fields.get("ocr_document_id")
    ocr_document_id = raw_ocr_document_id.strip() if isinstance(raw_ocr_document_id, str) else ""
    if not ocr_document_id:
        raise ApprovedFieldsValidationError("ocr_document_id is required for receipt confirmation")
    ocr_document = db_session.get(OcrDocument, ocr_document_id)
    if ocr_document is None:
        raise LookupError(ocr_document_id)
    return ocr_document


def commit_approved_receipt_stock_in_confirmation(
    db_session: Session,
    *,
    confirmation_id: str,
    payload_fields: dict[str, Any],
    approved_by_actor_id: str,
) -> ApprovedReceiptStockInCommitResult:
    try:
        confirmation = db_session.get(Confirmation, confirmation_id)
        if confirmation is None:
            raise LookupError(confirmation_id)

        task_run, session_record, shop = _require_context(db_session, confirmation=confirmation)
        ocr_document = _require_ocr_document(db_session, confirmation=confirmation)
        approved_lines = _parse_receipt_items(payload_fields)

        confirmation = approve_confirmation(
            db_session,
            confirmation_id=confirmation_id,
            resolution_payload={"fields": payload_fields},
            approved_by_actor_id=approved_by_actor_id,
        )

        line_results: list[ApprovedReceiptLineCommitResult] = []
        for approved_line in approved_lines:
            inventory_item = resolve_inventory_item_for_stock_in(
                db_session,
                shop=shop,
                fields=approved_line.fields,
            )
            inventory_event = append_stock_in_event(
                db_session,
                item=inventory_item,
                quantity=approved_line.fields.quantity,
                price=approved_line.fields.price,
                task_run_id=task_run.task_run_id,
                created_by=approved_by_actor_id,
                source="receipt-confirmed",
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
            audit_log = append_inventory_receipt_stock_in_audit_log(
                db_session,
                shop_id=shop.shop_id,
                task_run_id=task_run.task_run_id,
                actor_id=approved_by_actor_id,
                confirmation_id=confirmation.confirmation_id,
                ocr_document_id=ocr_document.ocr_document_id,
                line_id=approved_line.line_id,
                item=inventory_item,
                inventory_event=inventory_event,
            )
            line_results.append(
                ApprovedReceiptLineCommitResult(
                    line_id=approved_line.line_id,
                    inventory_item=inventory_item,
                    inventory_event=inventory_event,
                    audit_log=audit_log,
                    alert=alert,
                )
            )

        item_names = ", ".join(line.inventory_item.name for line in line_results[:3])
        if len(line_results) > 3:
            item_names = f"{item_names}, and more"
        task_run = resolve_awaiting_confirmation_task_run(
            db_session,
            task_run_id=task_run.task_run_id,
            result_summary=(
                f"Owner approved receipt stock-in for {len(line_results)} line items. "
                f"Committed: {item_names}."
            ),
        )
        write_runtime_message(
            db_session,
            session_id=session_record.session_id,
            task_run_id=task_run.task_run_id,
            text=(
                f"Mock runtime: receipt stock-in committed for {len(line_results)} line items. "
                f"Items: {item_names}."
            ),
        )
        db_session.commit()
        return ApprovedReceiptStockInCommitResult(
            confirmation=confirmation,
            task_run=task_run,
            ocr_document=ocr_document,
            line_results=line_results,
        )
    except Exception:
        db_session.rollback()
        raise
