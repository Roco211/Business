from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models import AuditLog, Confirmation, InventoryEvent, InventoryItem, MediaUpload, Message, SessionStreamEvent, TaskRun
from app.runtime.processor import process_task_run
from app.services.approved_receipt_stock_in_commits import commit_approved_receipt_stock_in_confirmation
from app.services.approved_stock_in_commits import commit_approved_stock_in_confirmation
from app.services.approved_stock_out_commits import commit_approved_stock_out_confirmation
from app.services.bootstrap import ensure_default_context
from app.services.messages import create_message


def _create_pending_stock_in_confirmation(db_session, *, client_request_id: str) -> tuple[Confirmation, TaskRun]:
    context = ensure_default_context(db_session)
    result = create_message(
        db_session,
        session_id=context.session.session_id,
        actor_type="owner",
        actor_id="owner_default",
        message_type="text",
        text="restock apples today",
        media_ids=[],
        client_request_id=client_request_id,
    )
    runtime_result = process_task_run(db_session, result.task_run_id)
    assert runtime_result.status == "awaiting-confirmation"

    confirmation = db_session.scalar(
        select(Confirmation).where(Confirmation.task_run_id == result.task_run_id)
    )
    task_run = db_session.get(TaskRun, result.task_run_id)
    assert confirmation is not None
    assert task_run is not None
    return confirmation, task_run


def _create_pending_stock_out_confirmation(db_session, *, client_request_id: str) -> tuple[Confirmation, TaskRun]:
    context = ensure_default_context(db_session)
    result = create_message(
        db_session,
        session_id=context.session.session_id,
        actor_type="owner",
        actor_id="owner_default",
        message_type="text",
        text="stock out cola for walk in sale",
        media_ids=[],
        client_request_id=client_request_id,
    )
    runtime_result = process_task_run(db_session, result.task_run_id)
    assert runtime_result.status == "awaiting-confirmation"

    confirmation = db_session.scalar(
        select(Confirmation).where(Confirmation.task_run_id == result.task_run_id)
    )
    task_run = db_session.get(TaskRun, result.task_run_id)
    assert confirmation is not None
    assert task_run is not None
    assert confirmation.confirmation_type == "stock-out"
    return confirmation, task_run


def _seed_uploaded_media(db_session, *, media_id: str, media_type: str) -> None:
    context = ensure_default_context(db_session)
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
            checksum_sha256=f"{media_id}-checksum",
            uploaded_at=context.session.created_at,
            created_at=context.session.created_at,
            updated_at=context.session.created_at,
        )
    )
    db_session.commit()


def _create_pending_receipt_confirmation(db_session, *, client_request_id: str) -> tuple[Confirmation, TaskRun]:
    context = ensure_default_context(db_session)
    _seed_uploaded_media(db_session, media_id="receipt_commit_demo", media_type="receipt-image")
    result = create_message(
        db_session,
        session_id=context.session.session_id,
        actor_type="owner",
        actor_id="owner_default",
        message_type="receipt-image",
        text=None,
        media_ids=["receipt_commit_demo"],
        client_request_id=client_request_id,
    )
    runtime_result = process_task_run(db_session, result.task_run_id)
    assert runtime_result.status == "awaiting-confirmation"

    confirmation = db_session.scalar(
        select(Confirmation).where(Confirmation.task_run_id == result.task_run_id)
    )
    task_run = db_session.get(TaskRun, result.task_run_id)
    assert confirmation is not None
    assert task_run is not None
    assert confirmation.confirmation_type == "receipt-stock-in-batch"
    return confirmation, task_run


def _seed_inventory_item(
    db_session,
    *,
    item_id: str,
    name: str,
    unit: str,
    stock: str,
    price: str,
) -> InventoryItem:
    context = ensure_default_context(db_session)
    item = InventoryItem(
        item_id=item_id,
        shop_id=context.shop.shop_id,
        sku=None,
        name=name,
        category=None,
        barcode=None,
        default_unit=unit,
        current_stock=Decimal(stock),
        current_price=Decimal(price),
        low_stock_threshold=context.shop.default_low_stock_threshold,
        image_media_id=None,
        is_active=True,
        created_at=context.shop.created_at,
        updated_at=context.shop.updated_at,
    )
    db_session.add(item)
    db_session.commit()
    return item


def test_commit_approved_stock_in_confirmation_writes_truth_and_completes_task(db_session) -> None:
    confirmation, task_run = _create_pending_stock_in_confirmation(
        db_session,
        client_request_id="inventory_commit_success",
    )

    result = commit_approved_stock_in_confirmation(
        db_session,
        confirmation_id=confirmation.confirmation_id,
        payload_fields={"item_name": "Apple", "quantity": 3, "unit": "box", "price": 18.5},
        approved_by_actor_id="owner_default",
    )

    persisted_confirmation = db_session.get(Confirmation, confirmation.confirmation_id)
    persisted_task_run = db_session.get(TaskRun, task_run.task_run_id)
    inventory_item = db_session.get(InventoryItem, result.inventory_item.item_id)
    inventory_event = db_session.get(InventoryEvent, result.inventory_event.inventory_event_id)
    audit_log = db_session.get(AuditLog, result.audit_log.audit_log_id)
    runtime_messages = db_session.scalars(
        select(Message)
        .where(Message.task_run_id == task_run.task_run_id, Message.actor_type == "system")
        .order_by(Message.created_at.asc(), Message.message_id.asc())
    ).all()
    stream_events = db_session.scalars(
        select(SessionStreamEvent)
        .where(SessionStreamEvent.session_id == task_run.session_id)
        .order_by(SessionStreamEvent.seq.asc())
    ).all()

    assert persisted_confirmation is not None
    assert persisted_confirmation.status == "approved"
    assert persisted_task_run is not None
    assert persisted_task_run.status == "completed"
    assert inventory_item is not None
    assert inventory_item.name == "Apple"
    assert inventory_item.current_stock == Decimal("3")
    assert inventory_item.current_price == Decimal("18.5")
    assert inventory_event is not None
    assert inventory_event.event_type == "stock-in"
    assert inventory_event.quantity_delta == Decimal("3")
    assert inventory_event.quantity_after == Decimal("3")
    assert audit_log is not None
    assert audit_log.action == "inventory.stock_in_confirmed"
    assert audit_log.metadata_json["confirmation_id"] == confirmation.confirmation_id
    assert len(runtime_messages) == 2
    assert runtime_messages[-1].text == "Stock-in committed for Apple (+3 box). Current stock: 3 box."
    assert "mock runtime" not in (runtime_messages[-1].text or "").lower()
    assert [event.event_type for event in stream_events[-5:]] == [
        "confirmation.resolved",
        "inventory.updated",
        "alert.updated",
        "task.updated",
        "message.created",
    ]
    assert stream_events[-5].payload["status"] == "approved"
    assert stream_events[-4].payload["inventory_event_id"] == inventory_event.inventory_event_id
    assert stream_events[-3].payload["alert_type"] == "low-stock"
    assert stream_events[-2].payload["status"] == "completed"
    assert stream_events[-1].message_id == runtime_messages[-1].message_id


def test_commit_approved_stock_out_confirmation_writes_frontline_runtime_message(db_session) -> None:
    confirmation, task_run = _create_pending_stock_out_confirmation(
        db_session,
        client_request_id="inventory_commit_stock_out_copy",
    )
    item = _seed_inventory_item(
        db_session,
        item_id="item_stock_out_commit_copy",
        name="Cola",
        unit="bottle",
        stock="9",
        price="7.5",
    )

    commit_approved_stock_out_confirmation(
        db_session,
        confirmation_id=confirmation.confirmation_id,
        payload_fields={
            "item_id": item.item_id,
            "stock_out_quantity": 2,
            "reason": "walk in sale",
        },
        approved_by_actor_id="owner_default",
    )

    runtime_messages = db_session.scalars(
        select(Message)
        .where(Message.task_run_id == task_run.task_run_id, Message.actor_type == "system")
        .order_by(Message.created_at.asc(), Message.message_id.asc())
    ).all()

    assert len(runtime_messages) == 2
    assert runtime_messages[-1].text == "Stock-out committed for Cola (-2 bottle). Current stock: 7 bottle."
    assert "mock runtime" not in (runtime_messages[-1].text or "").lower()


def test_commit_approved_receipt_stock_in_confirmation_writes_frontline_runtime_message(db_session) -> None:
    confirmation, task_run = _create_pending_receipt_confirmation(
        db_session,
        client_request_id="inventory_commit_receipt_copy",
    )

    commit_approved_receipt_stock_in_confirmation(
        db_session,
        confirmation_id=confirmation.confirmation_id,
        payload_fields={
            "items": [
                {
                    "line_id": "line_1",
                    "item_name": "Red Bull 250ml",
                    "quantity": 3,
                    "unit": "can",
                    "price": 41.0,
                }
            ]
        },
        approved_by_actor_id="owner_default",
    )

    runtime_messages = db_session.scalars(
        select(Message)
        .where(Message.task_run_id == task_run.task_run_id, Message.actor_type == "system")
        .order_by(Message.created_at.asc(), Message.message_id.asc())
    ).all()

    assert len(runtime_messages) == 2
    assert runtime_messages[-1].text == "Receipt stock-in committed for 1 line items. Items: Red Bull 250ml."
    assert "mock runtime" not in (runtime_messages[-1].text or "").lower()


def test_commit_approved_stock_in_confirmation_reuses_existing_inventory_item(db_session) -> None:
    confirmation, _ = _create_pending_stock_in_confirmation(
        db_session,
        client_request_id="inventory_commit_existing_item",
    )
    context = ensure_default_context(db_session)
    existing = InventoryItem(
        item_id="item_existing_commit",
        shop_id=context.shop.shop_id,
        sku=None,
        name="Apple",
        category=None,
        barcode=None,
        default_unit="box",
        current_stock=Decimal("5"),
        current_price=Decimal("11.0"),
        low_stock_threshold=context.shop.default_low_stock_threshold,
        image_media_id=None,
        is_active=True,
        created_at=context.shop.created_at,
        updated_at=context.shop.updated_at,
    )
    db_session.add(existing)
    db_session.commit()

    commit_approved_stock_in_confirmation(
        db_session,
        confirmation_id=confirmation.confirmation_id,
        payload_fields={"item_id": existing.item_id, "quantity": 2, "unit": "box", "price": 13},
        approved_by_actor_id="owner_default",
    )

    persisted_item = db_session.get(InventoryItem, existing.item_id)
    assert persisted_item is not None
    assert persisted_item.current_stock == Decimal("7")
    assert persisted_item.current_price == Decimal("13")


def test_commit_approved_stock_in_confirmation_rolls_back_on_inner_failure(db_session, monkeypatch) -> None:
    confirmation, task_run = _create_pending_stock_in_confirmation(
        db_session,
        client_request_id="inventory_commit_rollback",
    )
    baseline_audit_logs = db_session.scalars(
        select(AuditLog).where(AuditLog.task_run_id == task_run.task_run_id)
    ).all()
    baseline_audit_log_ids = {log.audit_log_id for log in baseline_audit_logs}

    from app.services import approved_stock_in_commits as commit_service

    def blow_up(*args, **kwargs):
        raise RuntimeError("audit write failed")

    monkeypatch.setattr(commit_service, "append_inventory_stock_in_audit_log", blow_up)

    with pytest.raises(RuntimeError, match="audit write failed"):
        commit_approved_stock_in_confirmation(
            db_session,
            confirmation_id=confirmation.confirmation_id,
            payload_fields={"item_name": "Apple", "quantity": 3, "unit": "box", "price": 18.5},
            approved_by_actor_id="owner_default",
        )

    persisted_confirmation = db_session.get(Confirmation, confirmation.confirmation_id)
    persisted_task_run = db_session.get(TaskRun, task_run.task_run_id)
    assert persisted_confirmation is not None
    assert persisted_confirmation.status == "pending"
    assert persisted_task_run is not None
    assert persisted_task_run.status == "awaiting-confirmation"
    assert db_session.scalars(select(InventoryItem)).all() == []
    assert db_session.scalars(select(InventoryEvent)).all() == []
    task_run_audit_logs = db_session.scalars(
        select(AuditLog).where(AuditLog.task_run_id == task_run.task_run_id)
    ).all()
    assert {log.audit_log_id for log in task_run_audit_logs} == baseline_audit_log_ids
    assert all(log.action != "inventory.stock_in_confirmed" for log in task_run_audit_logs)
