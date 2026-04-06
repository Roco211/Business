from dataclasses import replace
from datetime import datetime

import pytest
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app.models import Confirmation, MediaUpload, Message, OcrDocument, SessionRecord, SessionStreamEvent, TaskRun
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
    if media_ids:
        media_type = {
            "voice": "audio",
            "image": "image",
            "receipt-image": "receipt-image",
        }[message_type]
        for media_id in media_ids:
            db_session.add(
                MediaUpload(
                    media_id=media_id,
                    shop_id=context.shop.shop_id,
                    uploader_actor_type="owner",
                    uploader_actor_id="owner_default",
                    media_type=media_type,
                    file_name=f"{media_id}.bin",
                    content_type="application/octet-stream",
                    size_bytes=1024,
                    status="uploaded",
                    upload_url=f"https://mock.example/uploads/{media_id}",
                    public_url=f"https://mock.example/media/{media_id}",
                    checksum_sha256="abc123",
                    uploaded_at=context.session.created_at,
                    created_at=context.session.created_at,
                    updated_at=context.session.created_at,
                )
            )
        db_session.commit()
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


def _confirmation_fields(transcript: str) -> dict[str, object]:
    return {
        "summary": "Please confirm the stock-in details before commit.",
        "transcript": transcript,
        "draft_fields": {
            "item_name": None,
            "quantity": None,
            "unit": None,
            "price": None,
        },
        "required_fields": ["item_name", "quantity", "unit", "price"],
    }


def _stock_out_confirmation_fields(transcript: str) -> dict[str, object]:
    return {
        "summary": "Please confirm the stock-out details before commit.",
        "transcript": transcript,
        "draft_fields": {
            "item_id": None,
            "item_name": None,
            "stock_out_quantity": None,
            "unit": None,
            "reason": "stock out via chat",
        },
        "required_fields": ["item_name", "stock_out_quantity", "reason"],
    }


def _insert_confirmation_probe(
    db_session,
    *,
    confirmation_id: str,
    task_run_id: str,
    transcript: str,
    status: str,
    resolved_at: datetime | None,
) -> Confirmation:
    confirmation = Confirmation(
        confirmation_id=confirmation_id,
        task_run_id=task_run_id,
        confirmation_type="low-confidence-recognition",
        status=status,
        fields=_confirmation_fields(transcript),
        requested_by_employee_id="xiaoya",
        resolution_payload=None if resolved_at is None else {"fields": {"item_name": "Apple"}},
        approved_by_actor_id=None if resolved_at is None else "owner_default",
        created_at=datetime(2026, 4, 4, 12, 0, 0),
        resolved_at=resolved_at,
    )
    db_session.add(confirmation)
    db_session.commit()
    return confirmation


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


def test_text_stock_out_message_pauses_for_confirmation_and_writes_runtime_message(db_session) -> None:
    session_id, task_run_id = _create_owner_message(
        db_session,
        message_type="text",
        text="stock out cola for walk in sale",
        media_ids=[],
        client_request_id="runtime_stock_out_awaiting_confirmation",
    )

    result = process_task_run(db_session, task_run_id)
    task_run = db_session.get(TaskRun, task_run_id)
    confirmation = db_session.scalar(select(Confirmation).where(Confirmation.task_run_id == task_run_id))
    runtime_messages = db_session.scalars(
        select(Message)
        .where(Message.task_run_id == task_run_id, Message.actor_type == "system")
        .order_by(Message.created_at.asc(), Message.message_id.asc())
    ).all()
    stream_events = db_session.scalars(
        select(SessionStreamEvent)
        .where(SessionStreamEvent.session_id == session_id)
        .order_by(SessionStreamEvent.seq.asc())
    ).all()
    session_record = db_session.get(SessionRecord, session_id)

    assert result.status == "awaiting-confirmation"
    assert result.task_run_id == task_run_id
    assert result.task_type == "voice-stock-out"
    assert result.error_code is None
    assert task_run is not None
    assert task_run.status == "awaiting-confirmation"
    assert task_run.task_type == "voice-stock-out"
    assert task_run.assigned_employee_id == "xiaoya"
    assert task_run.result_summary == "Awaiting owner confirmation for stock-out details."
    assert task_run.completed_at is None
    assert confirmation is not None
    assert confirmation.status == "pending"
    assert confirmation.confirmation_type == "stock-out"
    assert confirmation.requested_by_employee_id == "xiaoya"
    assert confirmation.fields == _stock_out_confirmation_fields("stock out cola for walk in sale")
    assert len(runtime_messages) == 1
    assert runtime_messages[0].actor_type == "system"
    assert runtime_messages[0].actor_id == "runtime_system"
    assert runtime_messages[0].message_type == "text"
    assert runtime_messages[0].task_run_id == task_run_id
    assert "stock-out" in (runtime_messages[0].text or "").lower()
    assert "confirm" in (runtime_messages[0].text or "").lower()
    assert [event.event_type for event in stream_events] == [
        "message.created",
        "task.updated",
        "confirmation.created",
        "task.updated",
        "message.created",
    ]
    assert stream_events[2].payload["confirmation_id"] == confirmation.confirmation_id
    assert stream_events[3].payload["status"] == "awaiting-confirmation"
    assert stream_events[4].message_id == runtime_messages[0].message_id
    assert session_record is not None
    assert session_record.last_message_at == runtime_messages[0].created_at


def test_text_stock_in_message_pauses_for_confirmation_and_writes_runtime_message(db_session) -> None:
    session_id, task_run_id = _create_owner_message(
        db_session,
        message_type="text",
        text="restock apples today",
        media_ids=[],
        client_request_id="runtime_stock_in_awaiting_confirmation",
    )

    result = process_task_run(db_session, task_run_id)
    task_run = db_session.get(TaskRun, task_run_id)
    confirmation = db_session.scalar(select(Confirmation).where(Confirmation.task_run_id == task_run_id))
    runtime_messages = db_session.scalars(
        select(Message)
        .where(Message.task_run_id == task_run_id, Message.actor_type == "system")
        .order_by(Message.created_at.asc(), Message.message_id.asc())
    ).all()
    stream_events = db_session.scalars(
        select(SessionStreamEvent)
        .where(SessionStreamEvent.session_id == session_id)
        .order_by(SessionStreamEvent.seq.asc())
    ).all()
    session_record = db_session.get(SessionRecord, session_id)

    assert result.status == "awaiting-confirmation"
    assert result.task_run_id == task_run_id
    assert result.task_type == "voice-stock-in"
    assert result.error_code is None
    assert task_run is not None
    assert task_run.status == "awaiting-confirmation"
    assert task_run.task_type == "voice-stock-in"
    assert task_run.assigned_employee_id == "xiaoya"
    assert task_run.result_summary == "Awaiting owner confirmation for stock-in details."
    assert task_run.error_code is None
    assert task_run.error_message is None
    assert task_run.completed_at is None
    assert confirmation is not None
    assert confirmation.status == "pending"
    assert confirmation.confirmation_type == "low-confidence-recognition"
    assert confirmation.requested_by_employee_id == "xiaoya"
    assert confirmation.fields == _confirmation_fields("restock apples today")
    assert len(runtime_messages) == 1
    assert runtime_messages[0].actor_type == "system"
    assert runtime_messages[0].actor_id == "runtime_system"
    assert runtime_messages[0].message_type == "text"
    assert runtime_messages[0].task_run_id == task_run_id
    assert "confirm" in (runtime_messages[0].text or "").lower()
    assert [event.event_type for event in stream_events] == [
        "message.created",
        "task.updated",
        "confirmation.created",
        "task.updated",
        "message.created",
    ]
    assert stream_events[1].payload["status"] == "processing"
    assert stream_events[2].payload["confirmation_id"] == confirmation.confirmation_id
    assert stream_events[3].payload["status"] == "awaiting-confirmation"
    assert stream_events[4].message_id == runtime_messages[0].message_id
    assert session_record is not None
    assert session_record.last_message_at == runtime_messages[0].created_at


def test_text_stock_in_message_reuses_existing_pending_confirmation_without_creating_another(
    db_session,
    monkeypatch,
) -> None:
    _, task_run_id = _create_owner_message(
        db_session,
        message_type="text",
        text="restock apples today",
        media_ids=[],
        client_request_id="runtime_stock_in_reuse_pending_confirmation",
    )
    existing_confirmation = _insert_confirmation_probe(
        db_session,
        confirmation_id="conf_probe_pending_reuse",
        task_run_id=task_run_id,
        transcript="restock apples today",
        status="pending",
        resolved_at=None,
    )

    def fail_if_create_is_called(*args, **kwargs):
        raise AssertionError("create_pending_confirmation should not be called when a pending confirmation already exists")

    monkeypatch.setattr(runtime_processor, "create_pending_confirmation", fail_if_create_is_called)

    result = process_task_run(db_session, task_run_id)
    confirmations = db_session.scalars(select(Confirmation).where(Confirmation.task_run_id == task_run_id)).all()

    assert result.status == "awaiting-confirmation"
    assert len(confirmations) == 1
    assert confirmations[0].confirmation_id == existing_confirmation.confirmation_id
    assert confirmations[0].status == "pending"


def test_text_stock_in_message_does_not_treat_resolved_confirmation_as_pending(db_session) -> None:
    _, task_run_id = _create_owner_message(
        db_session,
        message_type="text",
        text="restock apples today",
        media_ids=[],
        client_request_id="runtime_stock_in_resolved_confirmation",
    )
    resolved_confirmation = _insert_confirmation_probe(
        db_session,
        confirmation_id="conf_probe_resolved",
        task_run_id=task_run_id,
        transcript="restock apples today",
        status="approved",
        resolved_at=datetime(2026, 4, 4, 12, 5, 0),
    )

    result = process_task_run(db_session, task_run_id)
    task_run = db_session.get(TaskRun, task_run_id)
    confirmations = db_session.scalars(select(Confirmation).where(Confirmation.task_run_id == task_run_id)).all()
    runtime_messages = db_session.scalars(
        select(Message)
        .where(Message.task_run_id == task_run_id, Message.actor_type == "system")
        .order_by(Message.created_at.asc(), Message.message_id.asc())
    ).all()

    assert result.status == "failed"
    assert result.error_code == "runtime_processing_error"
    assert task_run is not None
    assert task_run.status == "failed"
    assert len(confirmations) == 1
    assert confirmations[0].confirmation_id == resolved_confirmation.confirmation_id
    assert confirmations[0].status == "approved"
    assert len(runtime_messages) == 1
    assert "could not process" in (runtime_messages[0].text or "").lower()


def test_text_stock_in_message_freshly_loads_pending_confirmation_status(db_session, monkeypatch) -> None:
    _, task_run_id = _create_owner_message(
        db_session,
        message_type="text",
        text="restock apples today",
        media_ids=[],
        client_request_id="runtime_stock_in_stale_pending_probe",
    )
    confirmation = _insert_confirmation_probe(
        db_session,
        confirmation_id="conf_probe_stale_read",
        task_run_id=task_run_id,
        transcript="restock apples today",
        status="pending",
        resolved_at=None,
    )
    stale_loaded = db_session.get(Confirmation, confirmation.confirmation_id)
    assert stale_loaded is not None
    assert stale_loaded.status == "pending"

    competing_session = sessionmaker(
        bind=db_session.bind,
        autoflush=False,
        expire_on_commit=False,
    )()
    original_build_context = runtime_processor.build_runtime_turn_context

    def build_context_with_probe(db_session, *, task_run_id: str):
        context = original_build_context(db_session, task_run_id=task_run_id)
        return replace(context, pending_confirmation_id=confirmation.confirmation_id)

    try:
        competing_confirmation = competing_session.get(Confirmation, confirmation.confirmation_id)
        assert competing_confirmation is not None
        competing_confirmation.status = "approved"
        competing_confirmation.resolution_payload = {"fields": {"item_name": "Apple"}}
        competing_confirmation.approved_by_actor_id = "owner_default"
        competing_confirmation.resolved_at = datetime(2026, 4, 4, 12, 6, 0)
        competing_session.commit()

        monkeypatch.setattr(runtime_processor, "build_runtime_turn_context", build_context_with_probe)
        result = process_task_run(db_session, task_run_id)
    finally:
        competing_session.close()

    task_run = db_session.get(TaskRun, task_run_id)
    runtime_messages = db_session.scalars(
        select(Message)
        .where(Message.task_run_id == task_run_id, Message.actor_type == "system")
        .order_by(Message.created_at.asc(), Message.message_id.asc())
    ).all()

    assert result.status == "failed"
    assert result.error_code == "runtime_processing_error"
    assert task_run is not None
    assert task_run.status == "failed"
    assert len(runtime_messages) == 1
    assert "could not process" in (runtime_messages[0].text or "").lower()


def test_image_query_owner_message_completes_and_writes_runtime_message(db_session) -> None:
    session_id, task_run_id = _create_owner_message(
        db_session,
        message_type="image",
        text="check shelf stock for red bull",
        media_ids=["image_query_demo"],
        client_request_id="runtime_image_query_001",
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
    assert result.task_type == "photo-stock-query"
    assert result.error_code is None
    assert task_run is not None
    assert task_run.status == "completed"
    assert task_run.task_type == "photo-stock-query"
    assert task_run.assigned_employee_id == "xiaoya"
    assert "red bull" in (task_run.result_summary or "").lower()
    assert task_run.error_code is None
    assert task_run.error_message is None
    assert task_run.completed_at is not None
    assert len(runtime_messages) == 1
    assert runtime_messages[0].actor_type == "system"
    assert runtime_messages[0].actor_id == "runtime_system"
    assert runtime_messages[0].message_type == "text"
    assert runtime_messages[0].task_run_id == task_run_id
    assert "red bull" in (runtime_messages[0].text or "").lower()
    assert "stock" in (runtime_messages[0].text or "").lower()
    assert session_record is not None
    assert session_record.last_message_at == runtime_messages[0].created_at


def test_image_stock_in_message_pauses_for_confirmation_and_writes_runtime_message(db_session) -> None:
    session_id, task_run_id = _create_owner_message(
        db_session,
        message_type="image",
        text="restock red bull cans",
        media_ids=["image_stock_in_demo"],
        client_request_id="runtime_image_stock_in_awaiting_confirmation",
    )

    result = process_task_run(db_session, task_run_id)
    task_run = db_session.get(TaskRun, task_run_id)
    confirmation = db_session.scalar(select(Confirmation).where(Confirmation.task_run_id == task_run_id))
    runtime_messages = db_session.scalars(
        select(Message)
        .where(Message.task_run_id == task_run_id, Message.actor_type == "system")
        .order_by(Message.created_at.asc(), Message.message_id.asc())
    ).all()
    session_record = db_session.get(SessionRecord, session_id)

    assert result.status == "awaiting-confirmation"
    assert result.task_type == "photo-stock-in"
    assert result.error_code is None
    assert task_run is not None
    assert task_run.status == "awaiting-confirmation"
    assert task_run.task_type == "photo-stock-in"
    assert task_run.assigned_employee_id == "xiaoya"
    assert confirmation is not None
    assert confirmation.status == "pending"
    assert confirmation.confirmation_type == "low-confidence-recognition"
    assert confirmation.fields["draft_fields"]["item_name"] == "Red Bull 250ml"
    assert confirmation.fields["draft_fields"]["quantity"] == 2
    assert confirmation.fields["draft_fields"]["unit"] == "can"
    assert confirmation.fields["draft_fields"]["price"] == 6.5
    assert confirmation.fields["image_media_id"] == "image_stock_in_demo"
    assert "red bull" in str(confirmation.fields["summary"]).lower()
    assert len(runtime_messages) == 1
    assert "confirm" in (runtime_messages[0].text or "").lower()
    assert session_record is not None
    assert session_record.last_message_at == runtime_messages[0].created_at


def test_receipt_image_message_pauses_for_receipt_confirmation_and_persists_ocr_document(db_session) -> None:
    session_id, task_run_id = _create_owner_message(
        db_session,
        message_type="receipt-image",
        text=None,
        media_ids=["receipt_demo"],
        client_request_id="runtime_receipt_ocr_001",
    )

    result = process_task_run(db_session, task_run_id)
    task_run = db_session.get(TaskRun, task_run_id)
    confirmation = db_session.scalar(select(Confirmation).where(Confirmation.task_run_id == task_run_id))
    runtime_messages = db_session.scalars(
        select(Message)
        .where(Message.task_run_id == task_run_id, Message.actor_type == "system")
        .order_by(Message.created_at.asc(), Message.message_id.asc())
    ).all()
    persisted_document = db_session.scalar(
        select(OcrDocument).where(OcrDocument.task_run_id == task_run_id)
    )
    session_record = db_session.get(SessionRecord, session_id)

    assert result.status == "awaiting-confirmation"
    assert result.task_type == "receipt-ocr"
    assert result.error_code is None
    assert task_run is not None
    assert task_run.status == "awaiting-confirmation"
    assert task_run.task_type == "receipt-ocr"
    assert confirmation is not None
    assert confirmation.status == "pending"
    assert confirmation.confirmation_type == "receipt-stock-in-batch"
    assert confirmation.fields["ocr_document_id"]
    assert confirmation.fields["total_amount"] == 147.0
    assert len(confirmation.fields["draft_items"]) == 2
    assert confirmation.fields["draft_items"][0]["item_name"] == "Red Bull 250ml"
    assert confirmation.fields["draft_items"][1]["item_name"] == "Coca Cola 500ml"
    assert persisted_document is not None
    assert persisted_document.media_id == "receipt_demo"
    assert persisted_document.status == "completed"
    assert len(runtime_messages) == 1
    assert "receipt" in (runtime_messages[0].text or "").lower()
    assert "confirm" in (runtime_messages[0].text or "").lower()
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


def test_build_runtime_turn_context_keeps_double_tie_filter_consistent_with_canonical_order(
    db_session,
) -> None:
    task_run_ids_by_message_id: dict[str, str] = {}
    for suffix in ("first", "second", "third"):
        _, task_run_id = _create_owner_message(
            db_session,
            message_type="text",
            text=f"{suffix} turn",
            media_ids=[],
            client_request_id=f"runtime_context_double_tie_{suffix}",
        )
        task_run = db_session.get(TaskRun, task_run_id)
        assert task_run is not None
        task_run_ids_by_message_id[task_run.source_message_id] = task_run_id

    shared_created_at = datetime(2026, 4, 4, 12, 0, 0)
    for message_id, task_run_id in task_run_ids_by_message_id.items():
        task_run = db_session.get(TaskRun, task_run_id)
        message = db_session.get(Message, message_id)
        assert task_run is not None
        assert message is not None
        task_run.created_at = shared_created_at
        message.created_at = shared_created_at
    db_session.commit()

    canonical_message_ids = sorted(task_run_ids_by_message_id, reverse=True)
    later_message_id = canonical_message_ids[0]
    source_message_id = canonical_message_ids[1]
    earlier_message_id = canonical_message_ids[2]

    context = build_runtime_turn_context(
        db_session,
        task_run_id=task_run_ids_by_message_id[source_message_id],
    )
    recent_message_ids = [message["message_id"] for message in context.recent_messages]

    assert recent_message_ids == [source_message_id, earlier_message_id]
    assert later_message_id not in recent_message_ids


def test_build_runtime_turn_context_uses_existing_pending_confirmation_id(db_session) -> None:
    _, task_run_id = _create_owner_message(
        db_session,
        message_type="text",
        text="restock apples today",
        media_ids=[],
        client_request_id="runtime_context_pending_confirmation",
    )

    confirmation = _insert_confirmation_probe(
        db_session,
        confirmation_id="conf_probe_context_pending",
        task_run_id=task_run_id,
        transcript="restock apples today",
        status="pending",
        resolved_at=None,
    )

    context = build_runtime_turn_context(db_session, task_run_id=task_run_id)

    assert context.pending_confirmation_id == confirmation.confirmation_id


def test_build_runtime_turn_context_resolves_ready_media_refs_for_voice_uploads(db_session) -> None:
    _, task_run_id = _create_owner_message(
        db_session,
        message_type="voice",
        text=None,
        media_ids=["voice_query_demo"],
        client_request_id="runtime_context_voice_media_refs",
    )

    context = build_runtime_turn_context(db_session, task_run_id=task_run_id)

    assert context.media_ids == ["voice_query_demo"]
    assert len(context.media_refs) == 1
    assert context.media_refs[0].media_id == "voice_query_demo"
    assert context.media_refs[0].media_type == "audio"
    assert context.media_refs[0].public_url == "https://mock.example/media/voice_query_demo"


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
