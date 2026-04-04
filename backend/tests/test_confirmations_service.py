import pytest
from sqlalchemy import select

from app.models import Confirmation, TaskRun
from app.services.confirmations import (
    APPROVED_STATUS,
    ConfirmationConflictError,
    PENDING_STATUS,
    REJECTED_STATUS,
    approve_confirmation,
    create_pending_confirmation,
    list_confirmations,
    reject_confirmation,
)
from app.services.bootstrap import ensure_default_context
from app.services.messages import create_message


def _create_processing_stock_in_task(db_session, *, client_request_id: str) -> TaskRun:
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


def test_create_pending_confirmation_is_idempotent_per_task_run(db_session) -> None:
    task_run = _create_processing_stock_in_task(db_session, client_request_id="confirmation_seed_001")

    first = create_pending_confirmation(
        db_session,
        task_run_id=task_run.task_run_id,
        confirmation_type="low-confidence-recognition",
        fields={
            "summary": "Please confirm stock-in details before commit.",
            "transcript": "restock apples today",
            "draft_fields": {"item_name": None, "quantity": None, "unit": None, "price": None},
            "required_fields": ["item_name", "quantity", "unit", "price"],
        },
        requested_by_employee_id=None,
    )
    second = create_pending_confirmation(
        db_session,
        task_run_id=task_run.task_run_id,
        confirmation_type="low-confidence-recognition",
        fields={
            "summary": "Please confirm stock-in details before commit.",
            "transcript": "restock apples today",
            "draft_fields": {"item_name": None, "quantity": None, "unit": None, "price": None},
            "required_fields": ["item_name", "quantity", "unit", "price"],
        },
        requested_by_employee_id=None,
    )

    assert first.confirmation_id == second.confirmation_id
    assert second.status == PENDING_STATUS
    assert second.requested_by_employee_id is None
    assert db_session.scalar(select(Confirmation).where(Confirmation.task_run_id == task_run.task_run_id)) is not None


def test_approve_confirmation_records_resolution_payload(db_session) -> None:
    task_run = _create_processing_stock_in_task(db_session, client_request_id="confirmation_seed_002")
    confirmation = create_pending_confirmation(
        db_session,
        task_run_id=task_run.task_run_id,
        confirmation_type="low-confidence-recognition",
        fields={
            "summary": "Please confirm stock-in details before commit.",
            "transcript": "restock apples today",
            "draft_fields": {"item_name": None, "quantity": None, "unit": None, "price": None},
            "required_fields": ["item_name", "quantity", "unit", "price"],
        },
        requested_by_employee_id="xiaoya",
    )

    approved = approve_confirmation(
        db_session,
        confirmation_id=confirmation.confirmation_id,
        resolution_payload={
            "fields": {
                "item_name": "Apple",
                "quantity": 3,
                "unit": "box",
                "price": 18.5,
            }
        },
        approved_by_actor_id="owner_default",
    )

    assert approved.status == APPROVED_STATUS
    assert approved.resolution_payload == {
        "fields": {"item_name": "Apple", "quantity": 3, "unit": "box", "price": 18.5}
    }
    assert approved.approved_by_actor_id == "owner_default"
    assert approved.resolved_at is not None


def test_reject_confirmation_marks_record_rejected(db_session) -> None:
    task_run = _create_processing_stock_in_task(db_session, client_request_id="confirmation_seed_003")
    confirmation = create_pending_confirmation(
        db_session,
        task_run_id=task_run.task_run_id,
        confirmation_type="low-confidence-recognition",
        fields={
            "summary": "Please confirm stock-in details before commit.",
            "transcript": "restock apples today",
            "draft_fields": {"item_name": None, "quantity": None, "unit": None, "price": None},
            "required_fields": ["item_name", "quantity", "unit", "price"],
        },
        requested_by_employee_id="xiaoya",
    )

    rejected = reject_confirmation(
        db_session,
        confirmation_id=confirmation.confirmation_id,
    )

    assert rejected.status == REJECTED_STATUS
    assert rejected.resolution_payload is None
    assert rejected.resolved_at is not None


def test_resolving_already_resolved_confirmation_raises_conflict(db_session) -> None:
    task_run = _create_processing_stock_in_task(db_session, client_request_id="confirmation_seed_004")
    confirmation = create_pending_confirmation(
        db_session,
        task_run_id=task_run.task_run_id,
        confirmation_type="low-confidence-recognition",
        fields={
            "summary": "Please confirm stock-in details before commit.",
            "transcript": "restock apples today",
            "draft_fields": {"item_name": None, "quantity": None, "unit": None, "price": None},
            "required_fields": ["item_name", "quantity", "unit", "price"],
        },
        requested_by_employee_id="xiaoya",
    )
    approve_confirmation(
        db_session,
        confirmation_id=confirmation.confirmation_id,
        resolution_payload={"fields": {"item_name": "Apple", "quantity": 1, "unit": "box", "price": 18.5}},
        approved_by_actor_id="owner_default",
    )

    with pytest.raises(ConfirmationConflictError):
        reject_confirmation(db_session, confirmation_id=confirmation.confirmation_id)


def test_list_confirmations_filters_by_status_newest_first(db_session) -> None:
    first_task_run = _create_processing_stock_in_task(db_session, client_request_id="confirmation_seed_005")
    older = create_pending_confirmation(
        db_session,
        task_run_id=first_task_run.task_run_id,
        confirmation_type="low-confidence-recognition",
        fields={
            "summary": "Please confirm stock-in details before commit.",
            "transcript": "restock apples today",
            "draft_fields": {"item_name": None, "quantity": None, "unit": None, "price": None},
            "required_fields": ["item_name", "quantity", "unit", "price"],
        },
        requested_by_employee_id="xiaoya",
    )
    newer_task_run = _create_processing_stock_in_task(db_session, client_request_id="confirmation_seed_006")
    newer = create_pending_confirmation(
        db_session,
        task_run_id=newer_task_run.task_run_id,
        confirmation_type="low-confidence-recognition",
        fields={
            "summary": "Please confirm stock-in details before commit.",
            "transcript": "restock apples today",
            "draft_fields": {"item_name": None, "quantity": None, "unit": None, "price": None},
            "required_fields": ["item_name", "quantity", "unit", "price"],
        },
        requested_by_employee_id="xiaoya",
    )

    page = list_confirmations(db_session, status=PENDING_STATUS, limit=20)

    assert [item.confirmation_id for item in page.items] == [newer.confirmation_id, older.confirmation_id]
