from base64 import urlsafe_b64decode, urlsafe_b64encode
from dataclasses import dataclass
from datetime import datetime, timezone
UTC = timezone.utc
import json

from sqlalchemy import and_, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.ids import new_prefixed_id
from app.models import Message, SessionRecord
from app.services.media_uploads import ensure_media_uploads_ready
from app.services.session_stream import append_message_created_event
from app.services.task_runs import create_initial_task_run


class SessionNotFoundError(Exception):
    pass


class IdempotencyConflictError(Exception):
    pass


class MessageValidationError(Exception):
    pass


@dataclass(frozen=True)
class MessageWriteResult:
    message_id: str
    task_run_id: str
    replayed: bool


@dataclass(frozen=True)
class MessageListItem:
    message_id: str
    session_id: str
    actor_type: str
    actor_id: str
    message_type: str
    text: str | None
    media_ids: list[str]
    task_run_id: str | None
    created_at: datetime


@dataclass(frozen=True)
class MessageListPage:
    items: list[MessageListItem]
    next_cursor: str | None


def _load_session(db_session: Session, session_id: str) -> SessionRecord:
    session = db_session.get(SessionRecord, session_id)
    if session is None:
        raise SessionNotFoundError(session_id)
    return session


def _normalize_payload(
    *,
    message_type: str,
    text: str | None,
    media_ids: list[str],
) -> tuple[str, str | None, list[str]]:
    trimmed = text.strip() if text is not None else None
    return message_type, trimmed, list(media_ids)


def _validate_message_payload(
    *,
    message_type: str,
    text: str | None,
    media_ids: list[str],
    client_request_id: str,
) -> tuple[str | None, list[str]]:
    supported_types = {"text", "voice", "image", "receipt-image"}
    if message_type not in supported_types:
        raise MessageValidationError("Unsupported message_type")
    if not client_request_id.strip():
        raise MessageValidationError("client_request_id is required")

    normalized_text = text.strip() if text is not None else None
    normalized_media_ids = list(media_ids)
    if not normalized_text and not normalized_media_ids:
        raise MessageValidationError("text or media_ids is required")
    return normalized_text, normalized_media_ids


def _get_existing_message(
    db_session: Session,
    *,
    session_id: str,
    actor_type: str,
    actor_id: str,
    client_request_id: str,
) -> Message | None:
    query = select(Message).where(
        Message.session_id == session_id,
        Message.actor_type == actor_type,
        Message.actor_id == actor_id,
        Message.client_request_id == client_request_id,
    )
    return db_session.scalar(query)


def _encode_cursor(created_at: datetime, message_id: str) -> str:
    payload = json.dumps({"created_at": created_at.isoformat(), "message_id": message_id})
    return urlsafe_b64encode(payload.encode("utf-8")).decode("ascii")


def _decode_cursor(cursor: str) -> tuple[datetime, str]:
    payload = json.loads(urlsafe_b64decode(cursor.encode("ascii")).decode("utf-8"))
    return datetime.fromisoformat(payload["created_at"]), payload["message_id"]


def create_message(
    db_session: Session,
    *,
    session_id: str,
    actor_type: str,
    actor_id: str,
    message_type: str,
    text: str | None,
    media_ids: list[str],
    client_request_id: str,
) -> MessageWriteResult:
    session = _load_session(db_session, session_id)
    normalized_text, normalized_media_ids = _validate_message_payload(
        message_type=message_type,
        text=text,
        media_ids=media_ids,
        client_request_id=client_request_id,
    )
    normalized_payload = _normalize_payload(
        message_type=message_type,
        text=normalized_text,
        media_ids=normalized_media_ids,
    )

    existing = _get_existing_message(
        db_session,
        session_id=session_id,
        actor_type=actor_type,
        actor_id=actor_id,
        client_request_id=client_request_id,
    )
    if existing is not None:
        if _normalize_payload(
            message_type=existing.message_type,
            text=existing.text,
            media_ids=existing.media_ids,
        ) != normalized_payload:
            raise IdempotencyConflictError(client_request_id)
        return MessageWriteResult(
            message_id=existing.message_id,
            task_run_id=existing.task_run_id or "",
            replayed=True,
        )

    ensure_media_uploads_ready(
        db_session,
        shop_id=session.shop_id,
        media_ids=normalized_media_ids,
    )

    now = datetime.now(UTC).replace(tzinfo=None)
    message = Message(
        message_id=new_prefixed_id("msg"),
        session_id=session_id,
        actor_type=actor_type,
        actor_id=actor_id,
        message_type=message_type,
        text=normalized_text,
        media_ids=normalized_media_ids,
        client_request_id=client_request_id,
        task_run_id=None,
        created_at=now,
    )
    try:
        db_session.add(message)
        db_session.flush()

        task_run = create_initial_task_run(
            db_session,
            session_id=session.session_id,
            source_message_id=message.message_id,
        )
        message.task_run_id = task_run.task_run_id
        session.last_message_at = message.created_at
        append_message_created_event(db_session, message=message)
        db_session.commit()
    except IntegrityError:
        db_session.rollback()
        existing = _get_existing_message(
            db_session,
            session_id=session_id,
            actor_type=actor_type,
            actor_id=actor_id,
            client_request_id=client_request_id,
        )
        if existing is None:
            raise
        if _normalize_payload(
            message_type=existing.message_type,
            text=existing.text,
            media_ids=existing.media_ids,
        ) != normalized_payload:
            raise IdempotencyConflictError(client_request_id)
        return MessageWriteResult(
            message_id=existing.message_id,
            task_run_id=existing.task_run_id or "",
            replayed=True,
        )

    return MessageWriteResult(
        message_id=message.message_id,
        task_run_id=task_run.task_run_id,
        replayed=False,
    )


def list_messages(
    db_session: Session,
    *,
    session_id: str,
    limit: int,
    cursor: str | None,
) -> MessageListPage:
    _load_session(db_session, session_id)

    safe_limit = max(1, min(limit, 50))
    query = select(Message).where(Message.session_id == session_id)
    if cursor is not None:
        cursor_created_at, cursor_message_id = _decode_cursor(cursor)
        query = query.where(
            or_(
                Message.created_at < cursor_created_at,
                and_(
                    Message.created_at == cursor_created_at,
                    Message.message_id < cursor_message_id,
                ),
            )
        )

    query = query.order_by(Message.created_at.desc(), Message.message_id.desc()).limit(safe_limit + 1)
    records = list(db_session.scalars(query))
    has_more = len(records) > safe_limit
    page_records = records[:safe_limit]
    next_cursor = None
    if has_more and page_records:
        last = page_records[-1]
        next_cursor = _encode_cursor(last.created_at, last.message_id)

    return MessageListPage(
        items=[
            MessageListItem(
                message_id=record.message_id,
                session_id=record.session_id,
                actor_type=record.actor_type,
                actor_id=record.actor_id,
                message_type=record.message_type,
                text=record.text,
                media_ids=record.media_ids,
                task_run_id=record.task_run_id,
                created_at=record.created_at,
            )
            for record in page_records
        ],
        next_cursor=next_cursor,
    )
