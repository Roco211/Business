from datetime import UTC, datetime
from decimal import Decimal
import importlib

import pytest
from sqlalchemy import func, select


def _dt(value: str) -> datetime:
    return datetime.fromisoformat(value).replace(tzinfo=None)


def _utc_now_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _load_v2_outbox_worker_service():
    try:
        return importlib.import_module("app.services.v2_outbox_worker")
    except ModuleNotFoundError as exc:  # pragma: no cover - red stage only
        pytest.fail(f"app.services.v2_outbox_worker is not implemented yet: {exc}")


def _seed_worker_scope(db_session) -> None:
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


def _seed_inventory_events(db_session, *, inventory_item_id: str) -> None:
    from app.models import V2InventoryLedgerEvent

    db_session.add(
        V2InventoryLedgerEvent(
            event_id=f"vevent_{inventory_item_id}_in",
            tenant_id="tenant_a",
            shop_id="shop_a1",
            inventory_item_id=inventory_item_id,
            event_type="stock_in",
            quantity_delta=Decimal("5"),
            quantity_after=Decimal("5"),
            unit="box",
            price=Decimal("12.5"),
            source_type="outbox_worker_test",
            source_id=inventory_item_id,
            reason="outbox worker test",
            created_by_account_id="acct_001",
            occurred_at=_dt("2026-04-19T09:00:00"),
        )
    )
    db_session.add(
        V2InventoryLedgerEvent(
            event_id=f"vevent_{inventory_item_id}_out",
            tenant_id="tenant_a",
            shop_id="shop_a1",
            inventory_item_id=inventory_item_id,
            event_type="stock_out",
            quantity_delta=Decimal("-2"),
            quantity_after=Decimal("3"),
            unit="box",
            price=Decimal("12.5"),
            source_type="outbox_worker_test",
            source_id=inventory_item_id,
            reason="outbox worker test",
            created_by_account_id="acct_001",
            occurred_at=_dt("2026-04-19T09:30:00"),
        )
    )


def _seed_supported_outbox_event(
    db_session,
    *,
    outbox_event_id: str,
    inventory_item_id: str,
) -> None:
    from app.models import V2OutboxEvent

    db_session.add(
        V2OutboxEvent(
            outbox_event_id=outbox_event_id,
            tenant_id="tenant_a",
            shop_id="shop_a1",
            aggregate_type="task_run",
            aggregate_id=f"task_{outbox_event_id}",
            event_type="inventory.stock_in.committed",
            payload_json={"inventory_item_id": inventory_item_id},
            status="pending",
            attempt_count=0,
            last_error_code=None,
            last_error_message=None,
            available_at=_dt("2026-04-19T09:45:00"),
            processed_at=None,
            created_at=_dt("2026-04-19T09:45:00"),
            updated_at=_dt("2026-04-19T09:45:00"),
        )
    )


def _count_outbox_by_status(db_session, *, status: str) -> int:
    from app.models import V2OutboxEvent

    return int(
        db_session.scalar(
            select(func.count()).where(
                V2OutboxEvent.tenant_id == "tenant_a",
                V2OutboxEvent.shop_id == "shop_a1",
                V2OutboxEvent.status == status,
            )
        )
        or 0
    )


def test_drain_v2_outbox_events_processes_multiple_batches(db_session) -> None:
    worker_service = _load_v2_outbox_worker_service()
    _seed_worker_scope(db_session)
    _seed_inventory_item(db_session, inventory_item_id="vitem_cola", name="Cola")
    _seed_inventory_events(db_session, inventory_item_id="vitem_cola")
    _seed_supported_outbox_event(db_session, outbox_event_id="evt_001", inventory_item_id="vitem_cola")
    _seed_supported_outbox_event(db_session, outbox_event_id="evt_002", inventory_item_id="vitem_cola")
    _seed_supported_outbox_event(db_session, outbox_event_id="evt_003", inventory_item_id="vitem_cola")
    db_session.commit()

    result = worker_service.drain_v2_outbox_events(
        db_session,
        tenant_id="tenant_a",
        shop_id="shop_a1",
        batch_limit=2,
        max_batches=5,
        now=_dt("2026-04-19T10:00:00"),
    )

    db_session.expire_all()

    assert result.tenant_id == "tenant_a"
    assert result.shop_id == "shop_a1"
    assert result.batch_limit == 2
    assert result.max_batches == 5
    assert result.batches_run == 2
    assert result.claimed_count == 3
    assert result.completed_count == 3
    assert result.retried_count == 0
    assert result.failed_count == 0
    assert result.drained_at == _dt("2026-04-19T10:00:00")
    assert _count_outbox_by_status(db_session, status="completed") == 3
    assert _count_outbox_by_status(db_session, status="pending") == 0


def test_drain_v2_outbox_events_stops_when_no_events_are_claimed(db_session) -> None:
    worker_service = _load_v2_outbox_worker_service()
    _seed_worker_scope(db_session)
    db_session.commit()

    result = worker_service.drain_v2_outbox_events(
        db_session,
        tenant_id="tenant_a",
        shop_id="shop_a1",
        batch_limit=10,
        max_batches=3,
        now=_dt("2026-04-19T10:00:00"),
    )

    assert result.batches_run == 0
    assert result.claimed_count == 0
    assert result.completed_count == 0
    assert result.retried_count == 0
    assert result.failed_count == 0


def test_drain_v2_outbox_events_stops_at_max_batches(db_session) -> None:
    worker_service = _load_v2_outbox_worker_service()
    _seed_worker_scope(db_session)
    _seed_inventory_item(db_session, inventory_item_id="vitem_cola", name="Cola")
    _seed_inventory_events(db_session, inventory_item_id="vitem_cola")
    for index in range(3):
        _seed_supported_outbox_event(
            db_session,
            outbox_event_id=f"evt_{index}",
            inventory_item_id="vitem_cola",
        )
    db_session.commit()

    result = worker_service.drain_v2_outbox_events(
        db_session,
        tenant_id="tenant_a",
        shop_id="shop_a1",
        batch_limit=1,
        max_batches=2,
        now=_dt("2026-04-19T10:00:00"),
    )

    db_session.expire_all()

    assert result.batches_run == 2
    assert result.claimed_count == 2
    assert result.completed_count == 2
    assert _count_outbox_by_status(db_session, status="completed") == 2
    assert _count_outbox_by_status(db_session, status="pending") == 1


def test_drain_v2_outbox_events_rejects_invalid_limits(db_session) -> None:
    worker_service = _load_v2_outbox_worker_service()

    with pytest.raises(ValueError, match="batch_limit must be > 0"):
        worker_service.drain_v2_outbox_events(
            db_session,
            tenant_id="tenant_a",
            shop_id="shop_a1",
            batch_limit=0,
            max_batches=1,
        )

    with pytest.raises(ValueError, match="max_batches must be > 0"):
        worker_service.drain_v2_outbox_events(
            db_session,
            tenant_id="tenant_a",
            shop_id="shop_a1",
            batch_limit=1,
            max_batches=0,
        )
