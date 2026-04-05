from datetime import UTC, datetime
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.contracts.session_stream import SessionStreamEventEnvelope
from app.core.ids import new_prefixed_id
from app.models import SessionRecord, SessionStreamEvent


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
