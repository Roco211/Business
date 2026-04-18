from datetime import UTC, datetime
from decimal import Decimal
import importlib

import pytest
from sqlalchemy import select


def _dt(value: str) -> datetime:
    return datetime.fromisoformat(value).replace(tzinfo=None)


def _utc_now_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _load_v2_outbox_dispatch_service():
    try:
        return importlib.import_module("app.services.v2_outbox_dispatch")
    except ModuleNotFoundError as exc:  # pragma: no cover - red stage only
        pytest.fail(f"app.services.v2_outbox_dispatch is not implemented yet: {exc}")


def _seed_dispatch_scope(db_session) -> None:
    from app.models import V2Account, V2Shop, V2Tenant

    now = _utc_now_naive()
    db_session.add(
        V2Account(
            account_id="acct_001",
            email="owner@example.com",
            display_name="Owner",
            password_hash="hash",
            password_salt="salt",
            status="active",
            created_at=now,
            updated_at=now,
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
            created_at=now,
            updated_at=now,
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
            created_at=now,
            updated_at=now,
        )
    )
    db_session.commit()


def _seed_conversation_task(db_session) -> None:
    from app.models import V2ConversationSession, V2Message, V2TaskRun

    now = _dt("2026-04-18T09:30:00")
    db_session.add(
        V2ConversationSession(
            session_id="vsess_001",
            tenant_id="tenant_a",
            shop_id="shop_a1",
            session_type="workgroup",
            title="Dispatch session",
            status="active",
            last_event_seq=0,
            initiated_by_account_id="acct_001",
            created_at=now,
            updated_at=now,
        )
    )
    db_session.add(
        V2Message(
            message_id="vmsg_001",
            tenant_id="tenant_a",
            shop_id="shop_a1",
            session_id="vsess_001",
            actor_type="account",
            actor_id="acct_001",
            message_kind="text",
            payload_json={"text": "restock cola"},
            client_request_id="dispatch_msg_001",
            created_at=now,
        )
    )
    db_session.add(
        V2TaskRun(
            task_run_id="vtask_001",
            tenant_id="tenant_a",
            shop_id="shop_a1",
            session_id="vsess_001",
            source_message_id="vmsg_001",
            intent_type="inventory.stock_in",
            status="committed",
            risk_level="medium",
            trace_id="trace_dispatch_001",
            result_summary="Committed",
            error_code=None,
            created_at=now,
            updated_at=now,
            completed_at=now,
        )
    )


def _seed_inventory_item(db_session, *, inventory_item_id: str, name: str) -> None:
    from app.models import V2InventoryItem

    now = _utc_now_naive()
    db_session.add(
        V2InventoryItem(
            inventory_item_id=inventory_item_id,
            tenant_id="tenant_a",
            sku=None,
            name=name,
            barcode=None,
            default_unit="box",
            status="active",
            created_at=now,
            updated_at=now,
        )
    )


def _seed_inventory_snapshot(
    db_session,
    *,
    snapshot_id: str,
    inventory_item_id: str,
    current_quantity: Decimal,
    current_price: Decimal,
    updated_at: datetime,
) -> None:
    from app.models import V2InventoryStockSnapshot

    db_session.add(
        V2InventoryStockSnapshot(
            snapshot_id=snapshot_id,
            tenant_id="tenant_a",
            shop_id="shop_a1",
            inventory_item_id=inventory_item_id,
            current_quantity=current_quantity,
            current_price=current_price,
            low_stock_threshold=None,
            updated_at=updated_at,
        )
    )


def _seed_inventory_event(
    db_session,
    *,
    event_id: str,
    inventory_item_id: str,
    event_type: str,
    quantity_delta: Decimal,
    quantity_after: Decimal,
    price: Decimal | None,
    occurred_at: datetime,
) -> None:
    from app.models import V2InventoryLedgerEvent

    db_session.add(
        V2InventoryLedgerEvent(
            event_id=event_id,
            tenant_id="tenant_a",
            shop_id="shop_a1",
            inventory_item_id=inventory_item_id,
            event_type=event_type,
            quantity_delta=quantity_delta,
            quantity_after=quantity_after,
            unit="box",
            price=price,
            source_type="dispatch_test",
            source_id=inventory_item_id,
            reason="dispatch test",
            created_by_account_id="acct_001",
            occurred_at=occurred_at,
        )
    )


def _seed_outbox_event(
    db_session,
    *,
    outbox_event_id: str,
    event_type: str,
    payload_json: dict[str, object],
) -> None:
    from app.models import V2OutboxEvent

    db_session.add(
        V2OutboxEvent(
            outbox_event_id=outbox_event_id,
            tenant_id="tenant_a",
            shop_id="shop_a1",
            aggregate_type="task_run",
            aggregate_id=f"task_{outbox_event_id}",
            event_type=event_type,
            payload_json=payload_json,
            status="pending",
            attempt_count=0,
            last_error_code=None,
            last_error_message=None,
            available_at=_dt("2026-04-18T10:00:00"),
            processed_at=None,
            created_at=_dt("2026-04-18T10:00:00"),
            updated_at=_dt("2026-04-18T10:00:00"),
        )
    )


def test_dispatch_v2_outbox_events_replays_projection_and_completes_supported_inventory_event(db_session) -> None:
    from app.models import V2InventoryStockSnapshot, V2OutboxEvent

    dispatch_service = _load_v2_outbox_dispatch_service()
    _seed_dispatch_scope(db_session)
    _seed_inventory_item(db_session, inventory_item_id="vitem_cola", name="Cola")
    _seed_inventory_snapshot(
        db_session,
        snapshot_id="vsnapshot_cola",
        inventory_item_id="vitem_cola",
        current_quantity=Decimal("99"),
        current_price=Decimal("99"),
        updated_at=_dt("2026-04-18T09:00:00"),
    )
    _seed_inventory_event(
        db_session,
        event_id="vevent_cola_in",
        inventory_item_id="vitem_cola",
        event_type="stock_in",
        quantity_delta=Decimal("3"),
        quantity_after=Decimal("3"),
        price=Decimal("18.5"),
        occurred_at=_dt("2026-04-18T10:00:00"),
    )
    _seed_inventory_event(
        db_session,
        event_id="vevent_cola_out",
        inventory_item_id="vitem_cola",
        event_type="stock_out",
        quantity_delta=Decimal("-1"),
        quantity_after=Decimal("2"),
        price=Decimal("18.5"),
        occurred_at=_dt("2026-04-18T11:00:00"),
    )
    _seed_outbox_event(
        db_session,
        outbox_event_id="evt_inventory_commit",
        event_type="inventory.stock_in.committed",
        payload_json={"inventory_item_id": "vitem_cola"},
    )
    db_session.commit()

    result = dispatch_service.dispatch_v2_outbox_events(
        db_session,
        tenant_id="tenant_a",
        shop_id="shop_a1",
        limit=10,
        now=_dt("2026-04-18T11:30:00"),
    )

    db_session.expire_all()
    snapshot = db_session.scalar(
        select(V2InventoryStockSnapshot).where(V2InventoryStockSnapshot.inventory_item_id == "vitem_cola")
    )
    outbox = db_session.scalar(
        select(V2OutboxEvent).where(V2OutboxEvent.outbox_event_id == "evt_inventory_commit")
    )

    assert result.claimed_count == 1
    assert result.completed_count == 1
    assert result.retried_count == 0
    assert result.failed_count == 0
    assert snapshot is not None
    assert snapshot.current_quantity == Decimal("2")
    assert outbox is not None
    assert outbox.status == "completed"
    assert outbox.attempt_count == 1
    assert outbox.last_error_code is None
    assert outbox.processed_at == _dt("2026-04-18T11:30:00")


def test_dispatch_v2_outbox_events_appends_inventory_updated_stream_event(db_session) -> None:
    from app.models import V2ConversationSession, V2SessionStreamEvent

    dispatch_service = _load_v2_outbox_dispatch_service()
    _seed_dispatch_scope(db_session)
    _seed_conversation_task(db_session)
    _seed_inventory_item(db_session, inventory_item_id="vitem_cola", name="Cola")
    _seed_inventory_event(
        db_session,
        event_id="vevent_cola_in",
        inventory_item_id="vitem_cola",
        event_type="stock_in",
        quantity_delta=Decimal("3"),
        quantity_after=Decimal("3"),
        price=Decimal("18.5"),
        occurred_at=_dt("2026-04-18T10:00:00"),
    )
    _seed_outbox_event(
        db_session,
        outbox_event_id="evt_inventory_stream",
        event_type="inventory.stock_in.committed",
        payload_json={
            "session_id": "vsess_001",
            "task_run_id": "vtask_001",
            "inventory_item_id": "vitem_cola",
            "inventory_event_id": "vevent_cola_in",
            "event_type": "stock_in",
            "quantity_after": "3",
            "unit": "box",
        },
    )
    db_session.commit()

    dispatch_service.dispatch_v2_outbox_events(
        db_session,
        tenant_id="tenant_a",
        shop_id="shop_a1",
        limit=10,
        now=_dt("2026-04-18T11:30:00"),
    )

    db_session.expire_all()
    session = db_session.get(V2ConversationSession, "vsess_001")
    stream_event = db_session.scalar(
        select(V2SessionStreamEvent).where(V2SessionStreamEvent.event_id.like("vsevt_%"))
    )

    assert session is not None
    assert session.last_event_seq == 1
    assert stream_event is not None
    assert stream_event.event_type == "inventory.updated"
    assert stream_event.seq == 1
    assert stream_event.task_run_id == "vtask_001"
    assert stream_event.payload_json == {
        "inventory_item_id": "vitem_cola",
        "inventory_event_id": "vevent_cola_in",
        "event_type": "stock_in",
        "quantity_after": "3",
        "unit": "box",
    }


def test_dispatch_v2_outbox_events_marks_unsupported_event_failed_without_retry(db_session) -> None:
    from app.models import V2OutboxEvent

    dispatch_service = _load_v2_outbox_dispatch_service()
    _seed_dispatch_scope(db_session)
    _seed_outbox_event(
        db_session,
        outbox_event_id="evt_unsupported",
        event_type="catalog.item.created",
        payload_json={"inventory_item_id": "vitem_cola"},
    )
    db_session.commit()

    result = dispatch_service.dispatch_v2_outbox_events(
        db_session,
        tenant_id="tenant_a",
        shop_id="shop_a1",
        limit=10,
        now=_dt("2026-04-18T10:30:00"),
    )

    db_session.expire_all()
    outbox = db_session.scalar(select(V2OutboxEvent).where(V2OutboxEvent.outbox_event_id == "evt_unsupported"))

    assert result.claimed_count == 1
    assert result.completed_count == 0
    assert result.retried_count == 0
    assert result.failed_count == 1
    assert outbox is not None
    assert outbox.status == "failed"
    assert outbox.attempt_count == 1
    assert outbox.last_error_code == "unsupported_outbox_event"
    assert "Unsupported outbox event_type" in str(outbox.last_error_message)


def test_dispatch_v2_outbox_events_retries_when_projection_handler_raises(db_session, monkeypatch) -> None:
    from app.models import V2OutboxEvent

    dispatch_service = _load_v2_outbox_dispatch_service()
    _seed_dispatch_scope(db_session)
    _seed_outbox_event(
        db_session,
        outbox_event_id="evt_retry",
        event_type="inventory.stock_in.committed",
        payload_json={"inventory_item_id": "vitem_cola"},
    )
    db_session.commit()

    def _blow_up(*args, **kwargs):
        raise RuntimeError("temporary projection outage")

    monkeypatch.setattr(dispatch_service, "replay_v2_inventory_stock_projection", _blow_up)

    result = dispatch_service.dispatch_v2_outbox_events(
        db_session,
        tenant_id="tenant_a",
        shop_id="shop_a1",
        limit=10,
        retry_after_seconds=120,
        now=_dt("2026-04-18T10:10:00"),
    )

    db_session.expire_all()
    outbox = db_session.scalar(select(V2OutboxEvent).where(V2OutboxEvent.outbox_event_id == "evt_retry"))

    assert result.claimed_count == 1
    assert result.completed_count == 0
    assert result.retried_count == 1
    assert result.failed_count == 0
    assert outbox is not None
    assert outbox.status == "pending"
    assert outbox.attempt_count == 1
    assert outbox.available_at == _dt("2026-04-18T10:12:00")
    assert outbox.processed_at is None
    assert outbox.last_error_code == "dispatch_failed"
    assert outbox.last_error_message == "temporary projection outage"
