from dataclasses import dataclass
from decimal import Decimal
import uuid

from sqlalchemy.orm import Session

from app.models import (
    V2AuditLog,
    V2Confirmation,
    V2InventoryItem,
    V2InventoryLedgerEvent,
    V2OutboxEvent,
    V2TaskRun,
)
from app.services.v2_time import utc_now_naive

PENDING_OUTBOX_STATUS = "pending"


@dataclass(frozen=True)
class V2InventoryCommitRecords:
    audit_log: V2AuditLog
    outbox_event: V2OutboxEvent


def _serialize_decimal(value: Decimal | None) -> str | None:
    if value is None:
        return None
    return format(value, "f")


def _build_inventory_commit_action(confirmation_type: str) -> str:
    if confirmation_type == "inventory.stock_in":
        return "inventory.stock_in_committed"
    if confirmation_type == "inventory.stock_out":
        return "inventory.stock_out_committed"
    raise ValueError(f"Unsupported inventory confirmation_type '{confirmation_type}'.")


def _build_inventory_commit_event_type(confirmation_type: str) -> str:
    if confirmation_type == "inventory.stock_in":
        return "inventory.stock_in.committed"
    if confirmation_type == "inventory.stock_out":
        return "inventory.stock_out.committed"
    raise ValueError(f"Unsupported inventory confirmation_type '{confirmation_type}'.")


def append_v2_inventory_commit_records(
    db_session: Session,
    *,
    task_run: V2TaskRun,
    confirmation: V2Confirmation,
    actor_type: str,
    actor_id: str,
    inventory_item: V2InventoryItem,
    ledger_event: V2InventoryLedgerEvent,
) -> V2InventoryCommitRecords:
    now = utc_now_naive()
    audit_log = V2AuditLog(
        audit_log_id=f"vaudit_{uuid.uuid4().hex}"[:40],
        tenant_id=task_run.tenant_id,
        shop_id=task_run.shop_id,
        actor_type=actor_type,
        actor_id=actor_id,
        session_id=task_run.session_id,
        task_run_id=task_run.task_run_id,
        action=_build_inventory_commit_action(confirmation.confirmation_type),
        target_type="inventory_item",
        target_id=inventory_item.inventory_item_id,
        metadata_json={
            "confirmation_id": confirmation.confirmation_id,
            "confirmation_type": confirmation.confirmation_type,
            "intent_type": task_run.intent_type,
            "event_id": ledger_event.event_id,
            "event_type": ledger_event.event_type,
            "inventory_item_id": inventory_item.inventory_item_id,
            "item_name": inventory_item.name,
            "quantity_delta": _serialize_decimal(ledger_event.quantity_delta),
            "quantity_after": _serialize_decimal(ledger_event.quantity_after),
            "unit": ledger_event.unit,
            "price": _serialize_decimal(ledger_event.price),
            "source_type": ledger_event.source_type,
            "source_id": ledger_event.source_id,
            "reason": ledger_event.reason,
        },
        created_at=now,
    )
    outbox_event = V2OutboxEvent(
        outbox_event_id=f"voutbox_{uuid.uuid4().hex}"[:40],
        tenant_id=task_run.tenant_id,
        shop_id=task_run.shop_id,
        aggregate_type="task_run",
        aggregate_id=task_run.task_run_id,
        event_type=_build_inventory_commit_event_type(confirmation.confirmation_type),
        payload_json={
            "confirmation_id": confirmation.confirmation_id,
            "confirmation_type": confirmation.confirmation_type,
            "task_run_id": task_run.task_run_id,
            "session_id": task_run.session_id,
            "inventory_item_id": inventory_item.inventory_item_id,
            "inventory_event_id": ledger_event.event_id,
            "event_type": ledger_event.event_type,
            "quantity_delta": _serialize_decimal(ledger_event.quantity_delta),
            "quantity_after": _serialize_decimal(ledger_event.quantity_after),
            "unit": ledger_event.unit,
            "price": _serialize_decimal(ledger_event.price),
            "reason": ledger_event.reason,
        },
        status=PENDING_OUTBOX_STATUS,
        attempt_count=0,
        available_at=now,
        created_at=now,
    )
    db_session.add(audit_log)
    db_session.add(outbox_event)
    db_session.flush()
    return V2InventoryCommitRecords(audit_log=audit_log, outbox_event=outbox_event)
