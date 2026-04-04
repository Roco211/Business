import pytest
from sqlalchemy import select

from app.models import Message, SessionRecord, TaskRun
from app.services.bootstrap import ensure_default_context
from app.services.messages import (
    IdempotencyConflictError,
    SessionNotFoundError,
    create_message,
    list_messages,
)


def test_create_message_persists_message_task_and_last_message_at(db_session) -> None:
    context = ensure_default_context(db_session)

    result = create_message(
        db_session,
        session_id=context.session.session_id,
        actor_type="owner",
        actor_id="owner_default",
        message_type="text",
        text="restock water",
        media_ids=[],
        client_request_id="msg_local_001",
    )

    message = db_session.get(Message, result.message_id)
    task_run = db_session.get(TaskRun, result.task_run_id)
    refreshed_session = db_session.get(SessionRecord, context.session.session_id)

    assert message is not None
    assert task_run is not None
    assert task_run.source_message_id == message.message_id
    assert task_run.task_type == "pending-classification"
    assert task_run.status == "created"
    assert refreshed_session is not None
    assert refreshed_session.last_message_at == message.created_at


def test_create_message_replays_same_ids_for_same_idempotency_key(db_session) -> None:
    context = ensure_default_context(db_session)

    first = create_message(
        db_session,
        session_id=context.session.session_id,
        actor_type="owner",
        actor_id="owner_default",
        message_type="text",
        text="count redbull",
        media_ids=[],
        client_request_id="msg_local_002",
    )
    second = create_message(
        db_session,
        session_id=context.session.session_id,
        actor_type="owner",
        actor_id="owner_default",
        message_type="text",
        text="count redbull",
        media_ids=[],
        client_request_id="msg_local_002",
    )

    assert first.message_id == second.message_id
    assert first.task_run_id == second.task_run_id
    assert len(db_session.scalars(select(Message)).all()) == 1
    assert len(db_session.scalars(select(TaskRun)).all()) == 1


def test_create_message_raises_on_idempotency_conflict(db_session) -> None:
    context = ensure_default_context(db_session)

    create_message(
        db_session,
        session_id=context.session.session_id,
        actor_type="owner",
        actor_id="owner_default",
        message_type="text",
        text="first payload",
        media_ids=[],
        client_request_id="msg_local_003",
    )

    with pytest.raises(IdempotencyConflictError):
        create_message(
            db_session,
            session_id=context.session.session_id,
            actor_type="owner",
            actor_id="owner_default",
            message_type="text",
            text="second payload",
            media_ids=[],
            client_request_id="msg_local_003",
        )


def test_create_message_rejects_missing_session(db_session) -> None:
    with pytest.raises(SessionNotFoundError):
        create_message(
            db_session,
            session_id="sess_missing",
            actor_type="owner",
            actor_id="owner_default",
            message_type="text",
            text="missing session",
            media_ids=[],
            client_request_id="msg_missing",
        )


def test_list_messages_returns_newest_first_with_cursor(db_session) -> None:
    context = ensure_default_context(db_session)

    first = create_message(
        db_session,
        session_id=context.session.session_id,
        actor_type="owner",
        actor_id="owner_default",
        message_type="text",
        text="first",
        media_ids=[],
        client_request_id="msg_page_1",
    )
    second = create_message(
        db_session,
        session_id=context.session.session_id,
        actor_type="owner",
        actor_id="owner_default",
        message_type="text",
        text="second",
        media_ids=[],
        client_request_id="msg_page_2",
    )

    page_one = list_messages(db_session, session_id=context.session.session_id, limit=1, cursor=None)
    page_two = list_messages(
        db_session,
        session_id=context.session.session_id,
        limit=1,
        cursor=page_one.next_cursor,
    )

    assert page_one.items[0].message_id == second.message_id
    assert page_two.items[0].message_id == first.message_id
