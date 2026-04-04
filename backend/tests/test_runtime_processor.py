from datetime import datetime

import pytest
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app.models import Message, SessionRecord, TaskRun
from app.runtime.context import build_runtime_turn_context
from app.runtime import processor as runtime_processor
from app.runtime.processor import process_task_run
from app.services.bootstrap import ensure_default_context
from app.services.messages import create_message
from app.services.task_runs import (
    TaskRunTransitionError,
    claim_task_run_for_runtime,
    complete_task_run,
    fail_task_run,
)


def _create_owner_message(
    db_session,
    *,
    message_type: str,
    text: str | None,
    media_ids: list[str],
    client_request_id: str,
) -> tuple[str, str]:
    context = ensure_default_context(db_session)
    result = create_message(
        db_session,
        session_id=context.session.session_id,
        actor_type="owner",
        actor_id="owner_default",
        message_type=message_type,
        text=text,
        media_ids=media_ids,
        client_request_id=client_request_id,
    )
    return context.session.session_id, result.task_run_id


def test_text_owner_message_completes_and_writes_runtime_message(db_session) -> None:
    session_id, task_run_id = _create_owner_message(
        db_session,
        message_type="text",
        text="check stock left for cola",
        media_ids=[],
        client_request_id="runtime_text_001",
    )

    result = process_task_run(db_session, task_run_id)
    task_run = db_session.get(TaskRun, task_run_id)
    runtime_messages = db_session.scalars(
        select(Message)
        .where(Message.task_run_id == task_run_id, Message.actor_type == "system")
        .order_by(Message.created_at.asc(), Message.message_id.asc())
    ).all()
    session_record = db_session.get(SessionRecord, session_id)

    assert result.status == "completed"
    assert result.task_run_id == task_run_id
    assert result.task_type == "voice-stock-query"
    assert result.error_code is None
    assert task_run is not None
    assert task_run.status == "completed"
    assert task_run.task_type == "voice-stock-query"
    assert task_run.assigned_employee_id == "xiaoya"
    assert task_run.result_summary == "Mock runtime query processed: check stock left for cola"
    assert task_run.error_code is None
    assert task_run.error_message is None
    assert task_run.completed_at is not None
    assert len(runtime_messages) == 1
    assert runtime_messages[0].actor_type == "system"
    assert runtime_messages[0].actor_id == "runtime_system"
    assert runtime_messages[0].message_type == "text"
    assert runtime_messages[0].media_ids == []
    assert runtime_messages[0].client_request_id is None
    assert runtime_messages[0].task_run_id == task_run_id
    assert "stock query accepted" in (runtime_messages[0].text or "").lower()
    assert session_record is not None
    assert session_record.last_message_at == runtime_messages[0].created_at


def test_voice_owner_message_completes_and_writes_runtime_message(db_session) -> None:
    session_id, task_run_id = _create_owner_message(
        db_session,
        message_type="voice",
        text=None,
        media_ids=["voice_query_demo"],
        client_request_id="runtime_voice_001",
    )

    result = process_task_run(db_session, task_run_id)
    task_run = db_session.get(TaskRun, task_run_id)
    runtime_messages = db_session.scalars(
        select(Message)
        .where(Message.task_run_id == task_run_id, Message.actor_type == "system")
        .order_by(Message.created_at.asc(), Message.message_id.asc())
    ).all()
    session_record = db_session.get(SessionRecord, session_id)

    assert result.status == "completed"
    assert result.task_run_id == task_run_id
    assert result.task_type == "voice-stock-query"
    assert result.error_code is None
    assert task_run is not None
    assert task_run.status == "completed"
    assert task_run.task_type == "voice-stock-query"
    assert task_run.assigned_employee_id == "xiaoya"
    assert task_run.result_summary == "Mock runtime query processed: check stock left for cola"
    assert len(runtime_messages) == 1
    assert runtime_messages[0].actor_type == "system"
    assert runtime_messages[0].actor_id == "runtime_system"
    assert runtime_messages[0].message_type == "text"
    assert runtime_messages[0].task_run_id == task_run_id
    assert "stock query accepted" in (runtime_messages[0].text or "").lower()
    assert session_record is not None
    assert session_record.last_message_at == runtime_messages[0].created_at


def test_unsupported_image_owner_message_fails_and_writes_runtime_message(db_session) -> None:
    session_id, task_run_id = _create_owner_message(
        db_session,
        message_type="image",
        text=None,
        media_ids=["image_demo"],
        client_request_id="runtime_image_001",
    )

    result = process_task_run(db_session, task_run_id)
    task_run = db_session.get(TaskRun, task_run_id)
    runtime_messages = db_session.scalars(
        select(Message)
        .where(Message.task_run_id == task_run_id, Message.actor_type == "system")
        .order_by(Message.created_at.asc(), Message.message_id.asc())
    ).all()
    session_record = db_session.get(SessionRecord, session_id)

    assert result.status == "failed"
    assert result.task_run_id == task_run_id
    assert result.task_type is None
    assert result.error_code == "runtime_input_not_supported"
    assert task_run is not None
    assert task_run.status == "failed"
    assert task_run.task_type == "pending-classification"
    assert task_run.assigned_employee_id is None
    assert task_run.result_summary == "Runtime failed with runtime_input_not_supported"
    assert task_run.error_code == "runtime_input_not_supported"
    assert task_run.error_message == "image inputs are not supported yet"
    assert task_run.completed_at is not None
    assert len(runtime_messages) == 1
    assert runtime_messages[0].actor_type == "system"
    assert runtime_messages[0].actor_id == "runtime_system"
    assert runtime_messages[0].message_type == "text"
    assert runtime_messages[0].task_run_id == task_run_id
    assert "could not process" in (runtime_messages[0].text or "").lower()
    assert session_record is not None
    assert session_record.last_message_at == runtime_messages[0].created_at


def test_build_runtime_turn_context_scopes_recent_messages_to_source_turn(db_session) -> None:
    _, first_task_run_id = _create_owner_message(
        db_session,
        message_type="text",
        text="first turn",
        media_ids=[],
        client_request_id="runtime_context_first",
    )
    _, second_task_run_id = _create_owner_message(
        db_session,
        message_type="text",
        text="second turn",
        media_ids=[],
        client_request_id="runtime_context_second",
    )

    first_task_run = db_session.get(TaskRun, first_task_run_id)
    second_task_run = db_session.get(TaskRun, second_task_run_id)
    assert first_task_run is not None
    assert second_task_run is not None

    context = build_runtime_turn_context(db_session, task_run_id=first_task_run_id)
    recent_message_ids = [message["message_id"] for message in context.recent_messages]

    assert recent_message_ids == [first_task_run.source_message_id]
    assert second_task_run.source_message_id not in recent_message_ids


def test_build_runtime_turn_context_excludes_later_same_timestamp_messages(db_session) -> None:
    _, first_task_run_id = _create_owner_message(
        db_session,
        message_type="text",
        text="first turn",
        media_ids=[],
        client_request_id="runtime_context_same_timestamp_first",
    )
    _, source_task_run_id = _create_owner_message(
        db_session,
        message_type="text",
        text="source turn",
        media_ids=[],
        client_request_id="runtime_context_same_timestamp_second",
    )
    _, third_task_run_id = _create_owner_message(
        db_session,
        message_type="text",
        text="third turn",
        media_ids=[],
        client_request_id="runtime_context_same_timestamp_third",
    )

    first_task_run = db_session.get(TaskRun, first_task_run_id)
    source_task_run = db_session.get(TaskRun, source_task_run_id)
    third_task_run = db_session.get(TaskRun, third_task_run_id)
    assert first_task_run is not None
    assert source_task_run is not None
    assert third_task_run is not None

    first_message = db_session.get(Message, first_task_run.source_message_id)
    source_message = db_session.get(Message, source_task_run.source_message_id)
    third_message = db_session.get(Message, third_task_run.source_message_id)
    assert first_message is not None
    assert source_message is not None
    assert third_message is not None

    shared_message_created_at = datetime(2026, 4, 4, 12, 0, 0)
    first_task_run.created_at = datetime(2026, 4, 4, 12, 0, 1)
    source_task_run.created_at = datetime(2026, 4, 4, 12, 0, 2)
    third_task_run.created_at = datetime(2026, 4, 4, 12, 0, 3)
    first_message.created_at = shared_message_created_at
    source_message.created_at = shared_message_created_at
    third_message.created_at = shared_message_created_at
    db_session.commit()

    context = build_runtime_turn_context(db_session, task_run_id=source_task_run_id)
    recent_message_ids = [message["message_id"] for message in context.recent_messages]

    assert recent_message_ids == [
        source_task_run.source_message_id,
        first_task_run.source_message_id,
    ]
    assert third_task_run.source_message_id not in recent_message_ids


def test_build_runtime_turn_context_uses_message_id_as_final_stable_ordering_tiebreaker(db_session) -> None:
    earlier_task_run_ids: list[str] = []
    for index in range(11):
        _, task_run_id = _create_owner_message(
            db_session,
            message_type="text",
            text=f"earlier turn {index}",
            media_ids=[],
            client_request_id=f"runtime_context_stable_order_{index}",
        )
        earlier_task_run_ids.append(task_run_id)

    _, source_task_run_id = _create_owner_message(
        db_session,
        message_type="text",
        text="source turn",
        media_ids=[],
        client_request_id="runtime_context_stable_order_source",
    )

    shared_earlier_created_at = datetime(2026, 4, 4, 11, 0, 0)
    source_created_at = datetime(2026, 4, 4, 12, 0, 0)
    earlier_message_ids: list[str] = []

    for task_run_id in earlier_task_run_ids:
        task_run = db_session.get(TaskRun, task_run_id)
        assert task_run is not None
        message = db_session.get(Message, task_run.source_message_id)
        assert message is not None
        task_run.created_at = shared_earlier_created_at
        message.created_at = shared_earlier_created_at
        earlier_message_ids.append(message.message_id)

    source_task_run = db_session.get(TaskRun, source_task_run_id)
    assert source_task_run is not None
    source_message = db_session.get(Message, source_task_run.source_message_id)
    assert source_message is not None
    source_task_run.created_at = source_created_at
    source_message.created_at = source_created_at
    db_session.commit()

    context = build_runtime_turn_context(db_session, task_run_id=source_task_run_id)
    recent_message_ids = [message["message_id"] for message in context.recent_messages]

    assert recent_message_ids == [
        source_task_run.source_message_id,
        *sorted(earlier_message_ids, reverse=True)[:9],
    ]


def test_process_task_run_skips_already_advanced_tasks_without_runtime_message(db_session) -> None:
    _, processing_task_run_id = _create_owner_message(
        db_session,
        message_type="text",
        text="restock cola",
        media_ids=[],
        client_request_id="runtime_skip_processing",
    )
    processing_task_run = db_session.get(TaskRun, processing_task_run_id)
    assert processing_task_run is not None
    processing_task_run.status = "processing"
    db_session.commit()

    processing_result = process_task_run(db_session, processing_task_run_id)
    processing_runtime_messages = db_session.scalars(
        select(Message).where(Message.task_run_id == processing_task_run_id, Message.actor_type == "system")
    ).all()

    assert processing_result.status == "skipped"
    assert processing_result.task_run_id == processing_task_run_id
    assert processing_result.task_type == "pending-classification"
    assert processing_result.error_code is None
    assert processing_runtime_messages == []

    _, classified_task_run_id = _create_owner_message(
        db_session,
        message_type="text",
        text="restock oranges",
        media_ids=[],
        client_request_id="runtime_skip_classified",
    )
    classified_task_run = db_session.get(TaskRun, classified_task_run_id)
    assert classified_task_run is not None
    classified_task_run.task_type = "voice-stock-in"
    db_session.commit()

    classified_result = process_task_run(db_session, classified_task_run_id)
    classified_runtime_messages = db_session.scalars(
        select(Message).where(Message.task_run_id == classified_task_run_id, Message.actor_type == "system")
    ).all()

    assert classified_result.status == "skipped"
    assert classified_result.task_run_id == classified_task_run_id
    assert classified_result.task_type == "voice-stock-in"
    assert classified_result.error_code is None
    assert classified_runtime_messages == []


def test_process_task_run_fails_unexpected_runtime_errors_with_runtime_message(db_session, monkeypatch) -> None:
    session_id, task_run_id = _create_owner_message(
        db_session,
        message_type="text",
        text="check stock left for cola",
        media_ids=[],
        client_request_id="runtime_unexpected_error",
    )

    def raise_unexpected_error(_context):
        raise RuntimeError("boom")

    monkeypatch.setattr(runtime_processor, "route_runtime_input", raise_unexpected_error)

    result = process_task_run(db_session, task_run_id)
    task_run = db_session.get(TaskRun, task_run_id)
    runtime_messages = db_session.scalars(
        select(Message)
        .where(Message.task_run_id == task_run_id, Message.actor_type == "system")
        .order_by(Message.created_at.asc(), Message.message_id.asc())
    ).all()
    session_record = db_session.get(SessionRecord, session_id)

    assert result.status == "failed"
    assert result.task_run_id == task_run_id
    assert result.task_type is None
    assert result.error_code == "runtime_processing_error"
    assert task_run is not None
    assert task_run.status == "failed"
    assert task_run.task_type == "pending-classification"
    assert task_run.error_code == "runtime_processing_error"
    assert task_run.error_message == "Runtime processing failed: boom"
    assert task_run.completed_at is not None
    assert len(runtime_messages) == 1
    assert runtime_messages[0].actor_type == "system"
    assert runtime_messages[0].actor_id == "runtime_system"
    assert runtime_messages[0].task_run_id == task_run_id
    assert "boom" in (runtime_messages[0].text or "").lower()
    assert session_record is not None
    assert session_record.last_message_at == runtime_messages[0].created_at


def test_process_task_run_fails_post_route_errors_with_runtime_message(db_session, monkeypatch) -> None:
    session_id, task_run_id = _create_owner_message(
        db_session,
        message_type="text",
        text="check stock left for cola",
        media_ids=[],
        client_request_id="runtime_post_route_error",
    )

    def raise_post_route_error(*, task_type: str, transcript: str | None):
        raise RuntimeError(f"post-route failure for {task_type}")

    monkeypatch.setattr(runtime_processor, "summarize_completed_task", raise_post_route_error)

    result = process_task_run(db_session, task_run_id)
    task_run = db_session.get(TaskRun, task_run_id)
    runtime_messages = db_session.scalars(
        select(Message)
        .where(Message.task_run_id == task_run_id, Message.actor_type == "system")
        .order_by(Message.created_at.asc(), Message.message_id.asc())
    ).all()
    session_record = db_session.get(SessionRecord, session_id)

    assert result.status == "failed"
    assert result.task_run_id == task_run_id
    assert result.task_type is None
    assert result.error_code == "runtime_processing_error"
    assert task_run is not None
    assert task_run.status == "failed"
    assert task_run.error_code == "runtime_processing_error"
    assert task_run.error_message == "Runtime processing failed: post-route failure for voice-stock-query"
    assert task_run.completed_at is not None
    assert len(runtime_messages) == 1
    assert runtime_messages[0].actor_type == "system"
    assert runtime_messages[0].actor_id == "runtime_system"
    assert runtime_messages[0].task_run_id == task_run_id
    assert "post-route failure" in (runtime_messages[0].text or "").lower()
    assert session_record is not None
    assert session_record.last_message_at == runtime_messages[0].created_at


def test_process_task_run_skips_when_recovery_claim_is_lost_to_other_worker(db_session, monkeypatch) -> None:
    _, task_run_id = _create_owner_message(
        db_session,
        message_type="text",
        text="check stock left for cola",
        media_ids=[],
        client_request_id="runtime_recovery_claim_lost",
    )

    original_claim = runtime_processor.claim_task_run_for_runtime
    claim_calls = 0
    competing_session = sessionmaker(
        bind=db_session.bind,
        autoflush=False,
        expire_on_commit=False,
    )()

    def claim_with_competitor(session, *, task_run_id: str):
        nonlocal claim_calls
        claim_calls += 1
        if claim_calls == 2:
            competing_claim = original_claim(competing_session, task_run_id=task_run_id)
            assert competing_claim.changed is True
            competing_session.commit()
        return original_claim(session, task_run_id=task_run_id)

    def raise_unexpected_error(_context):
        raise RuntimeError("boom")

    monkeypatch.setattr(runtime_processor, "claim_task_run_for_runtime", claim_with_competitor)
    monkeypatch.setattr(runtime_processor, "route_runtime_input", raise_unexpected_error)

    try:
        result = process_task_run(db_session, task_run_id)
    finally:
        competing_session.close()

    task_run = db_session.get(TaskRun, task_run_id)
    runtime_messages = db_session.scalars(
        select(Message).where(Message.task_run_id == task_run_id, Message.actor_type == "system")
    ).all()

    assert result.status == "skipped"
    assert result.task_run_id == task_run_id
    assert result.task_type == "pending-classification"
    assert result.error_code is None
    assert task_run is not None
    assert task_run.status == "processing"
    assert task_run.task_type == "pending-classification"
    assert task_run.error_code is None
    assert task_run.error_message is None
    assert runtime_messages == []


def test_claim_task_run_uses_current_db_state_for_exclusive_claims(db_session) -> None:
    _, task_run_id = _create_owner_message(
        db_session,
        message_type="text",
        text="restock pears",
        media_ids=[],
        client_request_id="runtime_claim_exclusive",
    )

    primary_session = sessionmaker(
        bind=db_session.bind,
        autoflush=False,
        expire_on_commit=False,
    )()
    competing_session = sessionmaker(
        bind=db_session.bind,
        autoflush=False,
        expire_on_commit=False,
    )()

    try:
        stale_task_run = primary_session.get(TaskRun, task_run_id)
        assert stale_task_run is not None
        assert stale_task_run.status == "created"

        competing_claim = claim_task_run_for_runtime(competing_session, task_run_id=task_run_id)
        competing_session.commit()

        second_claim = claim_task_run_for_runtime(primary_session, task_run_id=task_run_id)

        assert competing_claim.changed is True
        assert competing_claim.task_run.status == "processing"
        assert second_claim.changed is False
        assert second_claim.task_run.task_run_id == task_run_id
        assert second_claim.task_run.status == "processing"
    finally:
        primary_session.close()
        competing_session.close()


def test_complete_task_run_rejects_illegal_direct_transition(db_session) -> None:
    _, task_run_id = _create_owner_message(
        db_session,
        message_type="text",
        text="restock cola",
        media_ids=[],
        client_request_id="runtime_complete_direct",
    )

    with pytest.raises(TaskRunTransitionError):
        complete_task_run(
            db_session,
            task_run_id=task_run_id,
            task_type="voice-stock-in",
            assigned_employee_id="xiaoya",
            result_summary="summary",
        )

    task_run = db_session.get(TaskRun, task_run_id)
    assert task_run is not None
    assert task_run.status == "created"
    assert task_run.task_type == "pending-classification"
    assert task_run.completed_at is None


def test_fail_task_run_rejects_illegal_direct_transition(db_session) -> None:
    _, task_run_id = _create_owner_message(
        db_session,
        message_type="image",
        text=None,
        media_ids=["image_demo"],
        client_request_id="runtime_fail_direct",
    )

    with pytest.raises(TaskRunTransitionError):
        fail_task_run(
            db_session,
            task_run_id=task_run_id,
            error_code="runtime_input_not_supported",
            error_message="image inputs are not supported yet",
            result_summary="failed",
        )

    task_run = db_session.get(TaskRun, task_run_id)
    assert task_run is not None
    assert task_run.status == "created"
    assert task_run.error_code is None
    assert task_run.error_message is None
    assert task_run.completed_at is None
