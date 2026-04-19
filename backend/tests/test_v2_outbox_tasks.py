from datetime import datetime
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.services.v2_outbox_worker import V2OutboxDrainResult
from app.workers import v2_outbox_tasks
from app.workers.celery_app import celery_app


class _FakeSession:
    def __init__(self) -> None:
        self.committed = False
        self.rolled_back = False
        self.closed = False

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        self.rolled_back = True

    def close(self) -> None:
        self.closed = True


def test_v2_outbox_task_wrapper_invokes_drain_and_commits(monkeypatch) -> None:
    fake_session = _FakeSession()

    def fake_get_session_factory():
        return lambda: fake_session

    def fake_run_outbox_drain(
        db_session,
        *,
        tenant_id: str,
        shop_id: str,
        batch_limit: int,
        max_batches: int,
        retry_after_seconds: int | None,
    ) -> V2OutboxDrainResult:
        assert db_session is fake_session
        assert tenant_id == "tenant_a"
        assert shop_id == "shop_a1"
        assert batch_limit == 20
        assert max_batches == 3
        assert retry_after_seconds == 120
        return V2OutboxDrainResult(
            tenant_id=tenant_id,
            shop_id=shop_id,
            batch_limit=batch_limit,
            max_batches=max_batches,
            batches_run=2,
            claimed_count=5,
            completed_count=4,
            retried_count=1,
            failed_count=0,
            drained_at=datetime.fromisoformat("2026-04-19T10:00:00"),
        )

    monkeypatch.setattr(v2_outbox_tasks, "get_session_factory", fake_get_session_factory)
    monkeypatch.setattr(v2_outbox_tasks, "run_outbox_drain", fake_run_outbox_drain)

    result = v2_outbox_tasks.drain_v2_outbox(
        "tenant_a",
        "shop_a1",
        batch_limit=20,
        max_batches=3,
        retry_after_seconds=120,
    )

    assert result == {
        "tenant_id": "tenant_a",
        "shop_id": "shop_a1",
        "batch_limit": 20,
        "max_batches": 3,
        "batches_run": 2,
        "claimed_count": 5,
        "completed_count": 4,
        "retried_count": 1,
        "failed_count": 0,
        "drained_at": "2026-04-19T10:00:00",
    }
    assert fake_session.committed is True
    assert fake_session.rolled_back is False
    assert fake_session.closed is True


def test_v2_outbox_task_drains_receipt_clarification_scope_and_commits_inventory_stream(db_session) -> None:
    from app.models import (
        V2Account,
        V2ConversationSession,
        V2InventoryItem,
        V2InventoryLedgerEvent,
        V2Message,
        V2OutboxEvent,
        V2SessionStreamEvent,
        V2Shop,
        V2TaskRun,
        V2Tenant,
    )

    created_at = datetime.fromisoformat("2020-01-01T09:00:00")
    session_id = "vsess_receipt_worker_task_001"
    task_run_id = "vtask_receipt_worker_task_001"
    inventory_item_id = "vitem_receipt_worker_task"
    inventory_event_id = "vevent_receipt_worker_task_in"
    outbox_event_id = "evt_receipt_worker_task"
    db_session.add(
        V2Account(
            account_id="acct_001",
            email="owner@example.com",
            display_name="Owner",
            password_hash="hash",
            password_salt="salt",
            status="active",
            created_at=created_at,
            updated_at=created_at,
        )
    )
    db_session.add(
        V2Tenant(
            tenant_id="tenant_a",
            name="Tenant A",
            slug="tenant-a",
            status="active",
            plan_code="trial",
            owner_account_id="acct_001",
            created_at=created_at,
            updated_at=created_at,
        )
    )
    db_session.add(
        V2Shop(
            shop_id="shop_a1",
            tenant_id="tenant_a",
            code="a-1",
            name="Shop A1",
            locale="zh-CN",
            timezone="Asia/Shanghai",
            status="active",
            created_at=created_at,
            updated_at=created_at,
        )
    )
    db_session.add(
        V2ConversationSession(
            session_id=session_id,
            tenant_id="tenant_a",
            shop_id="shop_a1",
            session_type="receipt",
            title="Receipt Worker Task",
            status="active",
            last_event_seq=0,
            initiated_by_account_id="acct_001",
            created_at=created_at,
            updated_at=created_at,
        )
    )
    db_session.add(
        V2Message(
            message_id="vmsg_receipt_worker_task_001",
            tenant_id="tenant_a",
            shop_id="shop_a1",
            session_id=session_id,
            actor_type="account",
            actor_id="acct_001",
            message_kind="receipt-image",
            payload_json={"text": "extract unclear receipt"},
            client_request_id="receipt_worker_task_msg_001",
            created_at=created_at,
        )
    )
    db_session.add(
        V2TaskRun(
            task_run_id=task_run_id,
            tenant_id="tenant_a",
            shop_id="shop_a1",
            session_id=session_id,
            source_message_id="vmsg_receipt_worker_task_001",
            intent_type="inventory.stock_in",
            status="committed",
            risk_level="medium",
            trace_id="trace_receipt_worker_task_001",
            result_summary="Committed",
            error_code=None,
            created_at=created_at,
            updated_at=created_at,
            completed_at=created_at,
        )
    )
    db_session.add(
        V2InventoryItem(
            inventory_item_id=inventory_item_id,
            tenant_id="tenant_a",
            sku=None,
            name="Receipt Worker Task Cola",
            barcode=None,
            default_unit="box",
            status="active",
            created_at=created_at,
            updated_at=created_at,
        )
    )
    db_session.add(
        V2InventoryLedgerEvent(
            event_id=inventory_event_id,
            tenant_id="tenant_a",
            shop_id="shop_a1",
            inventory_item_id=inventory_item_id,
            event_type="stock_in",
            quantity_delta=Decimal("2"),
            quantity_after=Decimal("2"),
            unit="box",
            price=Decimal("18.5"),
            source_type="task_run",
            source_id=task_run_id,
            reason="receipt clarification worker task test",
            created_by_account_id="acct_001",
            occurred_at=created_at,
        )
    )
    db_session.add(
        V2OutboxEvent(
            outbox_event_id=outbox_event_id,
            tenant_id="tenant_a",
            shop_id="shop_a1",
            aggregate_type="task_run",
            aggregate_id=task_run_id,
            event_type="inventory.stock_in.committed",
            payload_json={
                "session_id": session_id,
                "task_run_id": task_run_id,
                "inventory_item_id": inventory_item_id,
                "inventory_event_id": inventory_event_id,
                "event_type": "stock_in",
                "quantity_after": "2",
                "unit": "box",
                "source_type": "receipt-document",
                "source_id": "vdoc_receipt_001",
                "source_document_id": "vdoc_receipt_001",
                "source_media_asset_id": "vmedia_receipt_001",
                "ledger_source_type": "task_run",
                "ledger_source_id": task_run_id,
            },
            status="pending",
            attempt_count=0,
            last_error_code=None,
            last_error_message=None,
            available_at=created_at,
            processed_at=None,
            created_at=created_at,
            updated_at=created_at,
        )
    )
    db_session.commit()

    result = v2_outbox_tasks.drain_v2_outbox(
        "tenant_a",
        "shop_a1",
        batch_limit=10,
        max_batches=2,
        retry_after_seconds=60,
    )

    db_session.expire_all()
    session = db_session.get(V2ConversationSession, session_id)
    outbox = db_session.get(V2OutboxEvent, outbox_event_id)
    stream_event = db_session.scalar(
        select(V2SessionStreamEvent)
        .where(V2SessionStreamEvent.session_id == session_id)
        .order_by(V2SessionStreamEvent.seq.desc())
    )

    assert result["tenant_id"] == "tenant_a"
    assert result["shop_id"] == "shop_a1"
    assert result["claimed_count"] == 1
    assert result["completed_count"] == 1
    assert result["retried_count"] == 0
    assert result["failed_count"] == 0
    assert session is not None
    assert session.last_event_seq == 1
    assert outbox is not None
    assert outbox.status == "completed"
    assert outbox.processed_at is not None
    assert stream_event is not None
    assert stream_event.event_type == "inventory.updated"
    assert stream_event.seq == 1
    assert stream_event.task_run_id == task_run_id
    assert stream_event.payload_json["inventory_item_id"] == inventory_item_id
    assert stream_event.payload_json["inventory_event_id"] == inventory_event_id
    assert stream_event.payload_json["event_type"] == "stock_in"
    assert stream_event.payload_json["quantity_after"] == "2"
    assert stream_event.payload_json["unit"] == "box"
    assert stream_event.payload_json["source_type"] == "receipt-document"
    assert stream_event.payload_json["source_id"] == "vdoc_receipt_001"
    assert stream_event.payload_json["source_document_id"] == "vdoc_receipt_001"
    assert stream_event.payload_json["source_media_asset_id"] == "vmedia_receipt_001"
    assert stream_event.payload_json["ledger_source_type"] == "task_run"
    assert stream_event.payload_json["ledger_source_id"] == task_run_id


def test_v2_outbox_task_wrapper_rolls_back_on_failure(monkeypatch) -> None:
    fake_session = _FakeSession()

    def fake_get_session_factory():
        return lambda: fake_session

    def raise_boom(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(v2_outbox_tasks, "get_session_factory", fake_get_session_factory)
    monkeypatch.setattr(v2_outbox_tasks, "run_outbox_drain", raise_boom)

    with pytest.raises(RuntimeError, match="boom"):
        v2_outbox_tasks.drain_v2_outbox("tenant_a", "shop_a1")

    assert fake_session.committed is False
    assert fake_session.rolled_back is True
    assert fake_session.closed is True


def test_v2_outbox_task_is_registered_on_explicit_celery_app() -> None:
    assert v2_outbox_tasks.celery_app is celery_app
    assert v2_outbox_tasks.drain_v2_outbox.app is celery_app
    assert v2_outbox_tasks.drain_v2_outbox.name == "app.workers.v2_outbox_tasks.drain_v2_outbox"
