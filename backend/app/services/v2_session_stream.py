import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.contracts.v2.conversation import V2SessionStreamEventData
from app.models import V2ConversationSession, V2SessionStreamEvent
from app.services.v2_time import utc_now_naive


def _load_v2_session_for_update(
    db_session: Session,
    *,
    tenant_id: str,
    shop_id: str,
    session_id: str,
) -> V2ConversationSession:
    session = db_session.scalar(
        select(V2ConversationSession)
        .where(
            V2ConversationSession.tenant_id == tenant_id,
            V2ConversationSession.shop_id == shop_id,
            V2ConversationSession.session_id == session_id,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if session is None:
        raise LookupError(session_id)
    return session


def append_v2_session_event(
    db_session: Session,
    *,
    tenant_id: str,
    shop_id: str,
    session_id: str,
    event_type: str,
    task_run_id: str | None,
    message_id: str | None,
    data: dict[str, object],
    occurred_at=None,
) -> V2SessionStreamEventData:
    db_session.flush()
    session = _load_v2_session_for_update(
        db_session,
        tenant_id=tenant_id,
        shop_id=shop_id,
        session_id=session_id,
    )
    event_occurred_at = occurred_at or utc_now_naive()
    next_seq = int(session.last_event_seq) + 1
    session.last_event_seq = next_seq

    event = V2SessionStreamEvent(
        event_id=f"vsevt_{uuid.uuid4().hex}"[:40],
        tenant_id=tenant_id,
        shop_id=shop_id,
        session_id=session_id,
        seq=next_seq,
        event_type=event_type,
        task_run_id=task_run_id,
        message_id=message_id,
        payload_json=dict(data),
        occurred_at=event_occurred_at,
    )
    db_session.add(event)
    db_session.flush()
    return V2SessionStreamEventData(
        event_id=event.event_id,
        seq=event.seq,
        event_type=event.event_type,
        session_id=event.session_id,
        task_run_id=event.task_run_id,
        message_id=event.message_id,
        occurred_at=event.occurred_at,
        data=dict(event.payload_json),
    )


def list_v2_session_events_after(
    db_session: Session,
    *,
    tenant_id: str,
    shop_id: str,
    session_id: str,
    after_seq: int,
    limit: int = 50,
) -> list[V2SessionStreamEventData]:
    safe_limit = max(1, min(limit, 200))
    records = db_session.scalars(
        select(V2SessionStreamEvent)
        .where(
            V2SessionStreamEvent.tenant_id == tenant_id,
            V2SessionStreamEvent.shop_id == shop_id,
            V2SessionStreamEvent.session_id == session_id,
            V2SessionStreamEvent.seq > after_seq,
        )
        .order_by(V2SessionStreamEvent.seq.asc())
        .limit(safe_limit)
    ).all()
    return [
        V2SessionStreamEventData(
            event_id=record.event_id,
            seq=record.seq,
            event_type=record.event_type,
            session_id=record.session_id,
            task_run_id=record.task_run_id,
            message_id=record.message_id,
            occurred_at=record.occurred_at,
            data=dict(record.payload_json),
        )
        for record in records
    ]
