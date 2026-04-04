from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.core.ids import new_prefixed_id
from app.models import Message, SessionRecord


def write_runtime_message(
    db_session: Session,
    *,
    session_id: str,
    task_run_id: str,
    text: str,
) -> Message:
    session_record = db_session.get(SessionRecord, session_id)
    if session_record is None:
        raise LookupError(session_id)

    now = datetime.now(UTC).replace(tzinfo=None)
    message = Message(
        message_id=new_prefixed_id("msg"),
        session_id=session_id,
        actor_type="system",
        actor_id="runtime_system",
        message_type="text",
        text=text,
        media_ids=[],
        client_request_id=None,
        task_run_id=task_run_id,
        created_at=now,
    )
    db_session.add(message)
    session_record.last_message_at = now
    db_session.flush()
    return message
