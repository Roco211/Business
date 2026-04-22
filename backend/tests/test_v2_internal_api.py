from datetime import datetime, timezone
UTC = timezone.utc, timedelta
from decimal import Decimal

from sqlalchemy import select


def _utc_now_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _seed_v2_internal_identity(db_session) -> None:
    from app.models import V2Account, V2Shop, V2ShopAccess, V2Tenant, V2TenantMembership
    from app.services.v2_identity import hash_v2_password

    now = _utc_now_naive()
    password_salt = "11" * 16
    db_session.add(
        V2Account(
            account_id="acct_001",
            email="owner@example.com",
            display_name="Owner",
            password_hash=hash_v2_password("dev-password", password_salt),
            password_salt=password_salt,
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
        V2TenantMembership(
            membership_id="mship_tenant_a",
            tenant_id="tenant_a",
            account_id="acct_001",
            role_key="owner",
            status="active",
            joined_at=now,
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
    db_session.add(
        V2ShopAccess(
            shop_access_id="access_shop_a1",
            tenant_id="tenant_a",
            shop_id="shop_a1",
            membership_id="mship_tenant_a",
            access_level="write",
            status="active",
            created_at=now,
        )
    )
    db_session.commit()


def _seed_v2_internal_context(client, db_session) -> tuple[str, str]:
    _seed_v2_internal_identity(db_session)
    login_response = client.post(
        "/api/v2/auth/login",
        json={"email": "owner@example.com", "password": "dev-password"},
    )
    assert login_response.status_code == 200
    token = login_response.json()["data"]["access_token"]

    context_response = client.post(
        "/api/v2/context/select",
        headers={"Authorization": f"Bearer {token}"},
        json={"tenant_id": "tenant_a", "shop_id": "shop_a1"},
    )
    assert context_response.status_code == 200
    return token, context_response.json()["data"]["context_token"]


def _seed_v2_outbox_event(
    db_session,
    *,
    outbox_event_id: str,
    status: str,
    available_at: datetime,
    created_at: datetime,
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
            payload_json={"source": outbox_event_id},
            status=status,
            attempt_count=0,
            available_at=available_at,
            created_at=created_at,
        )
    )


def test_v2_worker_health_returns_scoped_outbox_counts(client, db_session) -> None:
    token, context_token = _seed_v2_internal_context(client, db_session)
    now = _utc_now_naive()
    _seed_v2_outbox_event(
        db_session,
        outbox_event_id="evt_pending",
        status="pending",
        available_at=now - timedelta(minutes=10),
        created_at=now - timedelta(minutes=10),
    )
    _seed_v2_outbox_event(
        db_session,
        outbox_event_id="evt_processing",
        status="processing",
        available_at=now - timedelta(minutes=5),
        created_at=now - timedelta(minutes=5),
    )
    _seed_v2_outbox_event(
        db_session,
        outbox_event_id="evt_completed",
        status="completed",
        available_at=now - timedelta(minutes=4),
        created_at=now - timedelta(minutes=4),
    )
    _seed_v2_outbox_event(
        db_session,
        outbox_event_id="evt_failed",
        status="failed",
        available_at=now - timedelta(minutes=3),
        created_at=now - timedelta(minutes=3),
    )
    db_session.commit()

    response = client.get(
        "/api/v2/internal/worker-health",
        headers={"Authorization": f"Bearer {token}", "X-Context-Token": context_token},
    )

    assert response.status_code == 200
    assert response.json()["data"] == {
        "tenant_id": "tenant_a",
        "shop_id": "shop_a1",
        "pending_count": 1,
        "processing_count": 1,
        "completed_count": 1,
        "failed_count": 1,
        "oldest_pending_at": (now - timedelta(minutes=10)).isoformat(),
        "oldest_available_pending_at": (now - timedelta(minutes=10)).isoformat(),
    }


def _seed_v2_internal_inventory_item(db_session, *, inventory_item_id: str, name: str) -> None:
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


def _seed_v2_internal_inventory_snapshot(
    db_session,
    *,
    snapshot_id: str,
    inventory_item_id: str,
    current_quantity: Decimal,
    current_price: Decimal,
) -> None:
    from app.models import V2InventoryStockSnapshot

    now = _utc_now_naive()
    db_session.add(
        V2InventoryStockSnapshot(
            snapshot_id=snapshot_id,
            tenant_id="tenant_a",
            shop_id="shop_a1",
            inventory_item_id=inventory_item_id,
            current_quantity=current_quantity,
            current_price=current_price,
            low_stock_threshold=None,
            updated_at=now,
        )
    )


def _seed_v2_internal_inventory_event(
    db_session,
    *,
    event_id: str,
    inventory_item_id: str,
    event_type: str,
    quantity_delta: Decimal,
    quantity_after: Decimal,
    price: Decimal,
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
            source_type="internal_replay_test",
            source_id=inventory_item_id,
            reason="internal replay test",
            created_by_account_id="acct_001",
            occurred_at=occurred_at,
        )
    )


def _seed_v2_internal_inventory_replay_fixture(db_session) -> None:
    _seed_v2_internal_inventory_item(db_session, inventory_item_id="vitem_cola", name="Cola")
    _seed_v2_internal_inventory_item(db_session, inventory_item_id="vitem_stale", name="Stale")
    _seed_v2_internal_inventory_snapshot(
        db_session,
        snapshot_id="vsnapshot_cola",
        inventory_item_id="vitem_cola",
        current_quantity=Decimal("99"),
        current_price=Decimal("99"),
    )
    _seed_v2_internal_inventory_snapshot(
        db_session,
        snapshot_id="vsnapshot_stale",
        inventory_item_id="vitem_stale",
        current_quantity=Decimal("7"),
        current_price=Decimal("10"),
    )
    _seed_v2_internal_inventory_event(
        db_session,
        event_id="vevent_cola_in",
        inventory_item_id="vitem_cola",
        event_type="stock_in",
        quantity_delta=Decimal("3"),
        quantity_after=Decimal("3"),
        price=Decimal("18.5"),
        occurred_at=_utc_now_naive() - timedelta(minutes=10),
    )
    _seed_v2_internal_inventory_event(
        db_session,
        event_id="vevent_cola_out",
        inventory_item_id="vitem_cola",
        event_type="stock_out",
        quantity_delta=Decimal("-1"),
        quantity_after=Decimal("2"),
        price=Decimal("18.5"),
        occurred_at=_utc_now_naive() - timedelta(minutes=5),
    )
    db_session.commit()


def test_v2_projection_replay_rebuilds_inventory_snapshot_for_current_context(client, db_session) -> None:
    from app.models import V2InventoryStockSnapshot

    token, context_token = _seed_v2_internal_context(client, db_session)
    _seed_v2_internal_inventory_replay_fixture(db_session)

    response = client.post(
        "/api/v2/internal/projections/replay",
        headers={"Authorization": f"Bearer {token}", "X-Context-Token": context_token},
        json={},
    )

    db_session.expire_all()
    rebuilt_snapshot = db_session.scalar(
        select(V2InventoryStockSnapshot).where(V2InventoryStockSnapshot.inventory_item_id == "vitem_cola")
    )
    deleted_snapshot = db_session.scalar(
        select(V2InventoryStockSnapshot).where(V2InventoryStockSnapshot.inventory_item_id == "vitem_stale")
    )

    assert response.status_code == 200
    assert response.json()["data"]["tenant_id"] == "tenant_a"
    assert response.json()["data"]["shop_id"] == "shop_a1"
    assert response.json()["data"]["inventory_item_id"] is None
    assert response.json()["data"]["replayed_item_count"] == 1
    assert response.json()["data"]["replayed_snapshot_count"] == 1
    assert response.json()["data"]["deleted_snapshot_count"] == 1
    assert response.json()["data"]["ledger_event_count"] == 2
    assert rebuilt_snapshot is not None
    assert rebuilt_snapshot.current_quantity == Decimal("2")
    assert deleted_snapshot is None
