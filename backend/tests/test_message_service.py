from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app.core.ids import new_prefixed_id
from app.models import Message, SessionRecord, SessionStreamEvent, TaskRun
from app.services.bootstrap import ensure_default_context
from app.services.messages import (
    IdempotencyConflictError,
    SessionNotFoundError,
    create_message,
    list_messages,
)
from app.services.task_runs import create_initial_task_run


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
    stream_events = db_session.scalars(
        select(SessionStreamEvent).order_by(SessionStreamEvent.seq.asc())
    ).all()

    assert message is not None
    assert task_run is not None
    assert task_run.source_message_id == message.message_id
    assert task_run.task_type == "pending-classification"
    assert task_run.status == "created"
    assert refreshed_session is not None
    assert refreshed_session.last_message_at == message.created_at
    assert len(stream_events) == 1
    assert stream_events[0].event_type == "message.created"
    assert stream_events[0].message_id == message.message_id
    assert stream_events[0].task_run_id == task_run.task_run_id
    assert stream_events[0].payload["preview_text"] == "restock water"


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


def test_create_message_recovers_from_racing_idempotent_insert(db_session) -> None:
    context = ensure_default_context(db_session)
    competing_session = sessionmaker(
        bind=db_session.bind,
        autoflush=False,
        expire_on_commit=False,
    )()

    original_flush = db_session.flush
    race_inserted = False

    def racing_flush(*args, **kwargs):
        nonlocal race_inserted
        if not race_inserted:
            now = datetime.now(UTC).replace(tzinfo=None)
            competing_message = Message(
                message_id=new_prefixed_id("msg"),
                session_id=context.session.session_id,
                actor_type="owner",
                actor_id="owner_default",
                message_type="text",
                text="race payload",
                media_ids=[],
                client_request_id="msg_race_001",
                task_run_id=None,
                created_at=now,
            )
            competing_session.add(competing_message)
            competing_session.flush()
            competing_task_run = create_initial_task_run(
                competing_session,
                session_id=context.session.session_id,
                source_message_id=competing_message.message_id,
            )
            competing_message.task_run_id = competing_task_run.task_run_id
            competing_record = competing_session.get(SessionRecord, context.session.session_id)
            assert competing_record is not None
            competing_record.last_message_at = competing_message.created_at
            competing_session.commit()
            race_inserted = True

        return original_flush(*args, **kwargs)

    db_session.flush = racing_flush  # type: ignore[method-assign]

    try:
        result = create_message(
            db_session,
            session_id=context.session.session_id,
            actor_type="owner",
            actor_id="owner_default",
            message_type="text",
            text="race payload",
            media_ids=[],
            client_request_id="msg_race_001",
        )
    finally:
        competing_session.close()

    assert result.replayed is True
    assert len(db_session.scalars(select(Message)).all()) == 1
    assert len(db_session.scalars(select(TaskRun)).all()) == 1
