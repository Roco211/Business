from datetime import UTC, datetime
from decimal import Decimal
import importlib

import pytest
from sqlalchemy import select


def _dt(value: str) -> datetime:
    return datetime.fromisoformat(value).replace(tzinfo=None)


def _utc_now_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _load_projection_service():
    try:
        return importlib.import_module("app.services.v2_inventory_projections")
    except ModuleNotFoundError as exc:  # pragma: no cover - red stage only
        pytest.fail(f"app.services.v2_inventory_projections is not implemented yet: {exc}")


def _seed_v2_inventory_projection_scope(db_session) -> None:
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


def _seed_v2_inventory_item(db_session, *, inventory_item_id: str, name: str) -> None:
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


def _seed_v2_inventory_snapshot(
    db_session,
    *,
    snapshot_id: str,
    inventory_item_id: str,
    current_quantity: Decimal,
    current_price: Decimal,
    updated_at: datetime,
    low_stock_threshold: Decimal | None = None,
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
            low_stock_threshold=low_stock_threshold,
            updated_at=updated_at,
        )
    )


def _seed_v2_inventory_event(
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
            source_type="projection_replay_test",
            source_id=inventory_item_id,
            reason="projection replay test",
            created_by_account_id="acct_001",
            occurred_at=occurred_at,
        )
    )


def test_replay_v2_inventory_stock_projection_rebuilds_snapshots_from_ledger_and_deletes_stale_rows(db_session) -> None:
    from app.models import V2InventoryStockSnapshot

    projection_service = _load_projection_service()
    _seed_v2_inventory_projection_scope(db_session)
    _seed_v2_inventory_item(db_session, inventory_item_id="vitem_cola", name="Cola")
    _seed_v2_inventory_snapshot(
        db_session,
        snapshot_id="vsnapshot_cola",
        inventory_item_id="vitem_cola",
        current_quantity=Decimal("99"),
        current_price=Decimal("99"),
        low_stock_threshold=Decimal("1"),
        updated_at=_dt("2026-04-18T09:00:00"),
    )
    _seed_v2_inventory_item(db_session, inventory_item_id="vitem_stale", name="Stale")
    _seed_v2_inventory_snapshot(
        db_session,
        snapshot_id="vsnapshot_stale",
        inventory_item_id="vitem_stale",
        current_quantity=Decimal("7"),
        current_price=Decimal("10"),
        updated_at=_dt("2026-04-18T09:00:00"),
    )
    _seed_v2_inventory_event(
        db_session,
        event_id="vevent_cola_in",
        inventory_item_id="vitem_cola",
        event_type="stock_in",
        quantity_delta=Decimal("3"),
        quantity_after=Decimal("3"),
        price=Decimal("18.5"),
        occurred_at=_dt("2026-04-18T10:00:00"),
    )
    _seed_v2_inventory_event(
        db_session,
        event_id="vevent_cola_out",
        inventory_item_id="vitem_cola",
        event_type="stock_out",
        quantity_delta=Decimal("-1"),
        quantity_after=Decimal("2"),
        price=Decimal("18.5"),
        occurred_at=_dt("2026-04-18T11:00:00"),
    )
    db_session.commit()

    result = projection_service.replay_v2_inventory_stock_projection(
        db_session,
        tenant_id="tenant_a",
        shop_id="shop_a1",
    )

    db_session.expire_all()
    rebuilt_snapshot = db_session.scalar(
        select(V2InventoryStockSnapshot).where(V2InventoryStockSnapshot.inventory_item_id == "vitem_cola")
    )
    deleted_snapshot = db_session.scalar(
        select(V2InventoryStockSnapshot).where(V2InventoryStockSnapshot.inventory_item_id == "vitem_stale")
    )

    assert result.tenant_id == "tenant_a"
    assert result.shop_id == "shop_a1"
    assert result.inventory_item_id is None
    assert result.replayed_item_count == 1
    assert result.replayed_snapshot_count == 1
    assert result.deleted_snapshot_count == 1
    assert result.ledger_event_count == 2
    assert rebuilt_snapshot is not None
    assert rebuilt_snapshot.current_quantity == Decimal("2")
    assert rebuilt_snapshot.current_price == Decimal("18.50")
    assert rebuilt_snapshot.low_stock_threshold == Decimal("1")
    assert rebuilt_snapshot.updated_at == _dt("2026-04-18T11:00:00")
    assert deleted_snapshot is None


def test_replay_v2_inventory_stock_projection_scopes_to_single_item(db_session) -> None:
    from app.models import V2InventoryStockSnapshot

    projection_service = _load_projection_service()
    _seed_v2_inventory_projection_scope(db_session)
    _seed_v2_inventory_item(db_session, inventory_item_id="vitem_cola", name="Cola")
    _seed_v2_inventory_item(db_session, inventory_item_id="vitem_orange", name="Orange")
    _seed_v2_inventory_snapshot(
        db_session,
        snapshot_id="vsnapshot_cola",
        inventory_item_id="vitem_cola",
        current_quantity=Decimal("0"),
        current_price=Decimal("0"),
        updated_at=_dt("2026-04-18T09:00:00"),
    )
    _seed_v2_inventory_snapshot(
        db_session,
        snapshot_id="vsnapshot_orange",
        inventory_item_id="vitem_orange",
        current_quantity=Decimal("99"),
        current_price=Decimal("99"),
        updated_at=_dt("2026-04-18T09:00:00"),
    )
    _seed_v2_inventory_event(
        db_session,
        event_id="vevent_cola_in",
        inventory_item_id="vitem_cola",
        event_type="stock_in",
        quantity_delta=Decimal("3"),
        quantity_after=Decimal("3"),
        price=Decimal("18.5"),
        occurred_at=_dt("2026-04-18T10:00:00"),
    )
    _seed_v2_inventory_event(
        db_session,
        event_id="vevent_cola_out",
        inventory_item_id="vitem_cola",
        event_type="stock_out",
        quantity_delta=Decimal("-1"),
        quantity_after=Decimal("2"),
        price=Decimal("18.5"),
        occurred_at=_dt("2026-04-18T11:00:00"),
    )
    _seed_v2_inventory_event(
        db_session,
        event_id="vevent_orange_in",
        inventory_item_id="vitem_orange",
        event_type="stock_in",
        quantity_delta=Decimal("8"),
        quantity_after=Decimal("8"),
        price=Decimal("12"),
        occurred_at=_dt("2026-04-18T10:30:00"),
    )
    db_session.commit()

    result = projection_service.replay_v2_inventory_stock_projection(
        db_session,
        tenant_id="tenant_a",
        shop_id="shop_a1",
        inventory_item_id="vitem_cola",
    )

    db_session.expire_all()
    refreshed_target = db_session.scalar(
        select(V2InventoryStockSnapshot).where(V2InventoryStockSnapshot.inventory_item_id == "vitem_cola")
    )
    untouched_other = db_session.scalar(
        select(V2InventoryStockSnapshot).where(V2InventoryStockSnapshot.inventory_item_id == "vitem_orange")
    )

    assert result.inventory_item_id == "vitem_cola"
    assert result.replayed_item_count == 1
    assert result.replayed_snapshot_count == 1
    assert result.deleted_snapshot_count == 0
    assert result.ledger_event_count == 2
    assert refreshed_target is not None
    assert refreshed_target.current_quantity == Decimal("2")
    assert untouched_other is not None
    assert untouched_other.current_quantity == Decimal("99")
