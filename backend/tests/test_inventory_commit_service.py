from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models import AuditLog, Confirmation, InventoryEvent, InventoryItem, Message, TaskRun
from app.runtime.processor import process_task_run
from app.services.approved_stock_in_commits import commit_approved_stock_in_confirmation
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
    assert "committed" in (runtime_messages[-1].text or "").lower()


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
    assert db_session.scalars(select(AuditLog)).all() == []
