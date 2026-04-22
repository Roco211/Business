from datetime import datetime, timezone
UTC = timezone.utc
from decimal import Decimal
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.contracts.session_stream import SessionStreamEventEnvelope
from app.core.ids import new_prefixed_id
from app.models import (
    Alert,
    Confirmation,
    InventoryEvent,
    InventoryItem,
    Message,
    SessionRecord,
    SessionStreamEvent,
    TaskRun,
)


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _load_session_for_update(db_session: Session, *, session_id: str) -> SessionRecord:
    session = db_session.scalar(
        select(SessionRecord)
        .where(SessionRecord.session_id == session_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if session is None:
        raise LookupError(session_id)
    return session


def append_session_event(
    db_session: Session,
    *,
    session_id: str,
    event_type: str,
    task_run_id: str | None,
    message_id: str | None,
    data: dict[str, object],
    occurred_at: datetime | None = None,
) -> SessionStreamEventEnvelope:
    db_session.flush()
    session = _load_session_for_update(db_session, session_id=session_id)
    event_occurred_at = occurred_at or _now()
    next_seq = int(session.last_event_seq) + 1
    session.last_event_seq = next_seq

    event = SessionStreamEvent(
        event_id=new_prefixed_id("evt"),
        session_id=session.session_id,
        seq=next_seq,
        event_type=event_type,
        task_run_id=task_run_id,
        message_id=message_id,
        payload=dict(data),
        occurred_at=event_occurred_at,
    )
    db_session.add(event)
    db_session.flush()
    return SessionStreamEventEnvelope(
        event_id=event.event_id,
        seq=event.seq,
        event_type=event.event_type,
        session_id=event.session_id,
        task_run_id=event.task_run_id,
        message_id=event.message_id,
        occurred_at=event.occurred_at,
        data=dict(event.payload),
    )


def list_session_events_after(
    db_session: Session,
    *,
    session_id: str,
    after_seq: int,
    limit: int = 50,
) -> list[SessionStreamEventEnvelope]:
    safe_limit = max(1, min(limit, 200))
    records = db_session.scalars(
        select(SessionStreamEvent)
        .where(
            SessionStreamEvent.session_id == session_id,
            SessionStreamEvent.seq > after_seq,
        )
        .order_by(SessionStreamEvent.seq.asc())
        .limit(safe_limit)
    ).all()
    return [
        SessionStreamEventEnvelope(
            event_id=record.event_id,
            seq=record.seq,
            event_type=record.event_type,
            session_id=record.session_id,
            task_run_id=record.task_run_id,
            message_id=record.message_id,
            occurred_at=record.occurred_at,
            data=dict(record.payload),
        )
        for record in records
    ]


def find_shop_session_id(db_session: Session, *, shop_id: str) -> str:
    session_id = db_session.scalar(
        select(SessionRecord.session_id)
        .where(SessionRecord.shop_id == shop_id)
        .order_by(SessionRecord.created_at.asc(), SessionRecord.session_id.asc())
    )
    if session_id is None:
        raise LookupError(shop_id)
    return session_id


def _decimal_to_jsonable(value: Decimal | str | None) -> float | None:
    if value is None:
        return None
    return float(Decimal(value))


def _message_preview_text(message: Message) -> str:
    text = (message.text or "").strip()
    if text:
        return text
    if message.media_ids:
        return f"{message.message_type} attachment"
    return message.message_type


def append_message_created_event(
    db_session: Session,
    *,
    message: Message,
) -> SessionStreamEventEnvelope:
    return append_session_event(
        db_session,
        session_id=message.session_id,
        event_type="message.created",
        task_run_id=message.task_run_id,
        message_id=message.message_id,
        data={
            "message_type": message.message_type,
            "actor_type": message.actor_type,
            "actor_id": message.actor_id,
            "preview_text": _message_preview_text(message),
        },
        occurred_at=message.created_at,
    )


def append_task_updated_event(
    db_session: Session,
    *,
    task_run: TaskRun,
) -> SessionStreamEventEnvelope:
    return append_session_event(
        db_session,
        session_id=task_run.session_id,
        event_type="task.updated",
        task_run_id=task_run.task_run_id,
        message_id=task_run.source_message_id,
        data={
            "status": task_run.status,
            "task_type": task_run.task_type,
            "error_code": task_run.error_code,
        },
        occurred_at=task_run.updated_at,
    )


def append_confirmation_created_event(
    db_session: Session,
    *,
    session_id: str,
    confirmation: Confirmation,
) -> SessionStreamEventEnvelope:
    return append_session_event(
        db_session,
        session_id=session_id,
        event_type="confirmation.created",
        task_run_id=confirmation.task_run_id,
        message_id=None,
        data={
            "confirmation_id": confirmation.confirmation_id,
            "confirmation_type": confirmation.confirmation_type,
            "status": confirmation.status,
            "summary": confirmation.fields.get("summary"),
        },
        occurred_at=confirmation.created_at,
    )


def append_confirmation_resolved_event(
    db_session: Session,
    *,
    session_id: str,
    confirmation: Confirmation,
) -> SessionStreamEventEnvelope:
    return append_session_event(
        db_session,
        session_id=session_id,
        event_type="confirmation.resolved",
        task_run_id=confirmation.task_run_id,
        message_id=None,
        data={
            "confirmation_id": confirmation.confirmation_id,
            "confirmation_type": confirmation.confirmation_type,
            "status": confirmation.status,
        },
        occurred_at=confirmation.resolved_at or _now(),
    )


def append_inventory_updated_event(
    db_session: Session,
    *,
    session_id: str,
    item: InventoryItem,
    inventory_event: InventoryEvent,
) -> SessionStreamEventEnvelope:
    return append_session_event(
        db_session,
        session_id=session_id,
        event_type="inventory.updated",
        task_run_id=inventory_event.task_run_id,
        message_id=None,
        data={
            "item_id": item.item_id,
            "inventory_event_id": inventory_event.inventory_event_id,
            "event_type": inventory_event.event_type,
            "current_stock": _decimal_to_jsonable(item.current_stock),
            "unit": item.default_unit,
        },
        occurred_at=inventory_event.created_at,
    )


def append_alert_updated_event(
    db_session: Session,
    *,
    session_id: str,
    item: InventoryItem,
    alert: Alert | None,
    occurred_at: datetime | None = None,
) -> SessionStreamEventEnvelope:
    return append_session_event(
        db_session,
        session_id=session_id,
        event_type="alert.updated",
        task_run_id=None,
        message_id=None,
        data={
            "alert_type": "low-stock",
            "alert_id": alert.alert_id if alert is not None else None,
            "item_id": item.item_id,
            "status": alert.status if alert is not None else "resolved",
            "stock": _decimal_to_jsonable(alert.stock if alert is not None else item.current_stock),
            "threshold": _decimal_to_jsonable(alert.threshold if alert is not None else item.low_stock_threshold),
        },
        occurred_at=occurred_at or _now(),
    )
