import pytest

from app.models import TaskRun
from app.services.bootstrap import ensure_default_context
from app.services.messages import create_message
from app.services.task_runs import (
    TaskRunTransitionError,
    claim_task_run_for_runtime,
    mark_task_run_awaiting_confirmation,
    reject_awaiting_confirmation_task_run,
    resolve_awaiting_confirmation_task_run,
)


def _create_processing_task(db_session, *, client_request_id: str) -> TaskRun:
    ensure_default_context(db_session)
    result = create_message(
        db_session,
        session_id="sess_default",
        actor_type="owner",
        actor_id="owner_default",
        message_type="text",
        text="restock apples today",
        media_ids=[],
        client_request_id=client_request_id,
    )
    task_run = db_session.get(TaskRun, result.task_run_id)
    assert task_run is not None
    task_run.status = "processing"
    task_run.task_type = "voice-stock-in"
    task_run.assigned_employee_id = "xiaoya"
    db_session.commit()
    return task_run


def _create_claimed_processing_task(db_session, *, client_request_id: str) -> TaskRun:
    ensure_default_context(db_session)
    result = create_message(
        db_session,
        session_id="sess_default",
        actor_type="owner",
        actor_id="owner_default",
        message_type="text",
        text="restock apples today",
        media_ids=[],
        client_request_id=client_request_id,
    )
    claimed = claim_task_run_for_runtime(db_session, task_run_id=result.task_run_id)
    db_session.commit()
    assert claimed.task_run is not None
    return claimed.task_run


def test_mark_task_run_awaiting_confirmation_moves_processing_task(db_session) -> None:
    task_run = _create_claimed_processing_task(db_session, client_request_id="task_transition_001")

    updated = mark_task_run_awaiting_confirmation(
        db_session,
        task_run_id=task_run.task_run_id,
        task_type="voice-stock-in",
        assigned_employee_id="xiaoya",
        result_summary="Awaiting owner confirmation for stock-in details.",
    )

    assert updated.status == "awaiting-confirmation"
    assert updated.task_type == "voice-stock-in"
    assert updated.assigned_employee_id == "xiaoya"
    assert updated.result_summary == "Awaiting owner confirmation for stock-in details."
    assert updated.completed_at is None


def test_resolve_awaiting_confirmation_task_run_completes_task(db_session) -> None:
    task_run = _create_processing_task(db_session, client_request_id="task_transition_002")
    mark_task_run_awaiting_confirmation(
        db_session,
        task_run_id=task_run.task_run_id,
        task_type="voice-stock-in",
        assigned_employee_id="xiaoya",
        result_summary="Awaiting owner confirmation for stock-in details.",
    )

    updated = resolve_awaiting_confirmation_task_run(
        db_session,
        task_run_id=task_run.task_run_id,
        result_summary="Owner approved confirmation. Business commit is deferred to a later phase.",
    )

    assert updated.status == "completed"
    assert updated.completed_at is not None
    assert updated.result_summary.startswith("Owner approved confirmation.")


def test_reject_awaiting_confirmation_task_run_marks_task_rejected(db_session) -> None:
    task_run = _create_processing_task(db_session, client_request_id="task_transition_003")
    mark_task_run_awaiting_confirmation(
        db_session,
        task_run_id=task_run.task_run_id,
        task_type="voice-stock-in",
        assigned_employee_id="xiaoya",
        result_summary="Awaiting owner confirmation for stock-in details.",
    )

    updated = reject_awaiting_confirmation_task_run(
        db_session,
        task_run_id=task_run.task_run_id,
        result_summary="Owner rejected the pending stock-in confirmation.",
    )

    assert updated.status == "rejected"
    assert updated.completed_at is not None


def test_mark_task_run_awaiting_confirmation_requires_processing_state(db_session) -> None:
    task_run = _create_processing_task(db_session, client_request_id="task_transition_004")
    task_run.status = "created"
    db_session.commit()

    with pytest.raises(TaskRunTransitionError):
        mark_task_run_awaiting_confirmation(
            db_session,
            task_run_id=task_run.task_run_id,
            task_type="voice-stock-in",
            assigned_employee_id="xiaoya",
            result_summary="Awaiting owner confirmation for stock-in details.",
        )


def test_resolve_awaiting_confirmation_requires_awaiting_state(db_session) -> None:
    task_run = _create_processing_task(db_session, client_request_id="task_transition_005")

    with pytest.raises(TaskRunTransitionError):
        resolve_awaiting_confirmation_task_run(
            db_session,
            task_run_id=task_run.task_run_id,
            result_summary="Owner approved confirmation. Business commit is deferred to a later phase.",
        )


def test_reject_awaiting_confirmation_requires_awaiting_state(db_session) -> None:
    task_run = _create_processing_task(db_session, client_request_id="task_transition_006")

    with pytest.raises(TaskRunTransitionError):
        reject_awaiting_confirmation_task_run(
            db_session,
            task_run_id=task_run.task_run_id,
            result_summary="Owner rejected the pending stock-in confirmation.",
        )
