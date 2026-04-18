from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

from app.models import V2OutboxEvent
from app.services.v2_inventory import V2InventoryItemNotFoundError
from app.services.v2_inventory_projections import replay_v2_inventory_stock_projection
from app.services.v2_outbox import (
    claim_v2_outbox_events,
    complete_v2_outbox_event,
    fail_v2_outbox_event,
)
from app.services.v2_session_stream import append_v2_session_event
from app.services.v2_time import utc_now_naive

SUPPORTED_DISPATCH_EVENT_TYPES = frozenset(
    {
        "inventory.stock_in.committed",
        "inventory.stock_out.committed",
    }
)
UNSUPPORTED_OUTBOX_EVENT_ERROR_CODE = "unsupported_outbox_event"
INVALID_OUTBOX_PAYLOAD_ERROR_CODE = "invalid_outbox_payload"
DISPATCH_FAILED_ERROR_CODE = "dispatch_failed"
INVENTORY_ITEM_NOT_FOUND_ERROR_CODE = "inventory_item_not_found"


class _UnsupportedOutboxEventError(ValueError):
    pass


class _InvalidOutboxPayloadError(ValueError):
    pass


@dataclass(frozen=True)
class V2OutboxDispatchResult:
    tenant_id: str
    shop_id: str
    claimed_count: int
    completed_count: int
    retried_count: int
    failed_count: int
    dispatched_at: datetime


def _normalize_error_message(exc: Exception) -> str:
    message = str(exc).strip()
    if message:
        return message
    return exc.__class__.__name__


def _require_payload_inventory_item_id(outbox_event: V2OutboxEvent) -> str:
    raw_inventory_item_id = outbox_event.payload_json.get("inventory_item_id")
    if not isinstance(raw_inventory_item_id, str) or not raw_inventory_item_id.strip():
        raise _InvalidOutboxPayloadError("inventory_item_id is required")
    return raw_inventory_item_id.strip()


def _append_inventory_updated_stream_event(
    db_session: Session,
    *,
    outbox_event: V2OutboxEvent,
    dispatch_now: datetime,
    inventory_item_id: str,
) -> None:
    raw_session_id = outbox_event.payload_json.get("session_id")
    if not isinstance(raw_session_id, str) or not raw_session_id.strip():
        return

    raw_task_run_id = outbox_event.payload_json.get("task_run_id")
    task_run_id = raw_task_run_id.strip() if isinstance(raw_task_run_id, str) and raw_task_run_id.strip() else None
    raw_inventory_event_id = outbox_event.payload_json.get("inventory_event_id")
    inventory_event_id = (
        raw_inventory_event_id.strip()
        if isinstance(raw_inventory_event_id, str) and raw_inventory_event_id.strip()
        else None
    )
    raw_event_type = outbox_event.payload_json.get("event_type")
    inventory_event_type = raw_event_type.strip() if isinstance(raw_event_type, str) and raw_event_type.strip() else None
    raw_unit = outbox_event.payload_json.get("unit")
    unit = raw_unit.strip() if isinstance(raw_unit, str) and raw_unit.strip() else None

    try:
        append_v2_session_event(
            db_session,
            tenant_id=outbox_event.tenant_id,
            shop_id=outbox_event.shop_id,
            session_id=raw_session_id.strip(),
            event_type="inventory.updated",
            task_run_id=task_run_id,
            message_id=None,
            data={
                "inventory_item_id": inventory_item_id,
                "inventory_event_id": inventory_event_id,
                "event_type": inventory_event_type,
                "quantity_after": outbox_event.payload_json.get("quantity_after"),
                "unit": unit,
            },
            occurred_at=dispatch_now,
        )
    except LookupError:
        return


def _dispatch_single_v2_outbox_event(
    db_session: Session,
    *,
    outbox_event: V2OutboxEvent,
    dispatch_now: datetime,
) -> None:
    if outbox_event.event_type not in SUPPORTED_DISPATCH_EVENT_TYPES:
        raise _UnsupportedOutboxEventError(
            f"Unsupported outbox event_type '{outbox_event.event_type}'."
        )

    inventory_item_id = _require_payload_inventory_item_id(outbox_event)
    replay_v2_inventory_stock_projection(
        db_session,
        tenant_id=outbox_event.tenant_id,
        shop_id=outbox_event.shop_id,
        inventory_item_id=inventory_item_id,
        replayed_at=dispatch_now,
    )
    _append_inventory_updated_stream_event(
        db_session,
        outbox_event=outbox_event,
        dispatch_now=dispatch_now,
        inventory_item_id=inventory_item_id,
    )


def dispatch_v2_outbox_events(
    db_session: Session,
    *,
    tenant_id: str,
    shop_id: str,
    limit: int,
    retry_after_seconds: int | None = 60,
    now: datetime | None = None,
) -> V2OutboxDispatchResult:
    if retry_after_seconds is not None and retry_after_seconds < 0:
        raise ValueError("retry_after_seconds must be >= 0")

    dispatch_now = now or utc_now_naive()
    claimed_events = claim_v2_outbox_events(
        db_session,
        tenant_id=tenant_id,
        shop_id=shop_id,
        limit=limit,
        now=dispatch_now,
    )
    completed_count = 0
    retried_count = 0
    failed_count = 0

    for outbox_event in claimed_events:
        try:
            _dispatch_single_v2_outbox_event(
                db_session,
                outbox_event=outbox_event,
                dispatch_now=dispatch_now,
            )
            complete_v2_outbox_event(
                db_session,
                tenant_id=tenant_id,
                shop_id=shop_id,
                outbox_event_id=outbox_event.outbox_event_id,
                now=dispatch_now,
            )
            completed_count += 1
        except _UnsupportedOutboxEventError as exc:
            fail_v2_outbox_event(
                db_session,
                tenant_id=tenant_id,
                shop_id=shop_id,
                outbox_event_id=outbox_event.outbox_event_id,
                error_code=UNSUPPORTED_OUTBOX_EVENT_ERROR_CODE,
                error_message=str(exc),
                now=dispatch_now,
            )
            failed_count += 1
        except _InvalidOutboxPayloadError as exc:
            fail_v2_outbox_event(
                db_session,
                tenant_id=tenant_id,
                shop_id=shop_id,
                outbox_event_id=outbox_event.outbox_event_id,
                error_code=INVALID_OUTBOX_PAYLOAD_ERROR_CODE,
                error_message=str(exc),
                now=dispatch_now,
            )
            failed_count += 1
        except V2InventoryItemNotFoundError as exc:
            fail_v2_outbox_event(
                db_session,
                tenant_id=tenant_id,
                shop_id=shop_id,
                outbox_event_id=outbox_event.outbox_event_id,
                error_code=INVENTORY_ITEM_NOT_FOUND_ERROR_CODE,
                error_message=f"Inventory item '{exc.args[0]}' not found",
                now=dispatch_now,
            )
            failed_count += 1
        except Exception as exc:
            fail_v2_outbox_event(
                db_session,
                tenant_id=tenant_id,
                shop_id=shop_id,
                outbox_event_id=outbox_event.outbox_event_id,
                error_code=DISPATCH_FAILED_ERROR_CODE,
                error_message=_normalize_error_message(exc),
                retry_after_seconds=retry_after_seconds,
                now=dispatch_now,
            )
            retried_count += 1

    return V2OutboxDispatchResult(
        tenant_id=tenant_id,
        shop_id=shop_id,
        claimed_count=len(claimed_events),
        completed_count=completed_count,
        retried_count=retried_count,
        failed_count=failed_count,
        dispatched_at=dispatch_now,
    )
