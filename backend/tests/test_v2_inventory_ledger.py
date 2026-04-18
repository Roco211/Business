from datetime import UTC, datetime
from decimal import Decimal


def _utc_now_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _seed_v2_inventory_context(db_session, *, task_run_id: str) -> None:
    from app.models import (
        V2Account,
        V2ConversationSession,
        V2Message,
        V2Shop,
        V2TaskRun,
        V2Tenant,
    )

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
    _seed_v2_task_run_for_inventory(
        db_session,
        task_run_id=task_run_id,
        tenant_id="tenant_a",
        shop_id="shop_a1",
    )
    db_session.commit()


def _seed_v2_shop(
    db_session,
    *,
    shop_id: str,
    tenant_id: str,
    code: str,
    name: str,
) -> None:
    from app.models import V2Shop

    now = _utc_now_naive()
    db_session.add(
        V2Shop(
            shop_id=shop_id,
            tenant_id=tenant_id,
            code=code,
            name=name,
            locale="zh-CN",
            timezone="Asia/Shanghai",
            status="active",
            created_at=now,
            updated_at=now,
        )
    )
    db_session.commit()


def _seed_v2_task_run_for_inventory(
    db_session,
    *,
    task_run_id: str,
    tenant_id: str,
    shop_id: str,
) -> None:
    from app.models import V2ConversationSession, V2Message, V2TaskRun

    now = _utc_now_naive()
    session_id = f"vsess_{task_run_id}"[:40]
    message_id = f"vmsg_{task_run_id}"[:40]
    db_session.add(
        V2ConversationSession(
            session_id=session_id,
            tenant_id=tenant_id,
            shop_id=shop_id,
            session_type="workgroup",
            title="Inventory Workgroup",
            status="active",
            initiated_by_account_id="acct_001",
            created_at=now,
            updated_at=now,
        )
    )
    db_session.add(
        V2Message(
            message_id=message_id,
            tenant_id=tenant_id,
            shop_id=shop_id,
            session_id=session_id,
            actor_type="account",
            actor_id="acct_001",
            message_kind="text",
            payload_json={"text": "restock cola"},
            client_request_id=f"req_{task_run_id}"[:64],
            created_at=now,
        )
    )
    db_session.add(
        V2TaskRun(
            task_run_id=task_run_id,
            tenant_id=tenant_id,
            shop_id=shop_id,
            session_id=session_id,
            source_message_id=message_id,
            intent_type="inventory.stock_in",
            status="executing",
            risk_level="medium",
            trace_id=f"trace_{task_run_id}"[:64],
            result_summary=None,
            error_code=None,
            created_at=now,
            updated_at=now,
            completed_at=None,
        )
    )


def test_v2_inventory_ledger_schema_persists_tenant_and_shop_boundaries(db_session) -> None:
    from sqlalchemy import select

    from app.models import V2InventoryItem, V2InventoryLedgerEvent, V2InventoryStockSnapshot

    now = _utc_now_naive()
    _seed_v2_inventory_context(db_session, task_run_id="vtask_v2_inventory_schema")
    item = V2InventoryItem(
        inventory_item_id="vitem_001",
        tenant_id="tenant_a",
        sku="COLA-001",
        name="Cola",
        barcode="690000000001",
        default_unit="box",
        status="active",
        created_at=now,
        updated_at=now,
    )
    snapshot = V2InventoryStockSnapshot(
        snapshot_id="vsnapshot_001",
        tenant_id="tenant_a",
        shop_id="shop_a1",
        inventory_item_id="vitem_001",
        current_quantity=Decimal("2"),
        current_price=Decimal("18.5"),
        low_stock_threshold=Decimal("1"),
        updated_at=now,
    )
    event = V2InventoryLedgerEvent(
        event_id="vevent_001",
        tenant_id="tenant_a",
        shop_id="shop_a1",
        inventory_item_id="vitem_001",
        event_type="stock_in",
        quantity_delta=Decimal("2"),
        quantity_after=Decimal("2"),
        unit="box",
        price=Decimal("18.5"),
        source_type="task_run",
        source_id="vtask_v2_inventory_schema",
        reason="approved stock in",
        created_by_account_id="acct_001",
        occurred_at=now,
    )
    db_session.add_all([item, snapshot, event])
    db_session.commit()

    persisted = db_session.scalar(
        select(V2InventoryLedgerEvent).where(V2InventoryLedgerEvent.event_id == "vevent_001")
    )
    assert persisted is not None
    assert persisted.tenant_id == "tenant_a"
    assert persisted.shop_id == "shop_a1"


def test_v2_commit_stock_in_creates_item_snapshot_and_ledger_event(db_session) -> None:
    from app.services.v2_inventory import commit_v2_inventory_stock_in

    _seed_v2_inventory_context(db_session, task_run_id="vtask_v2_stock_in_create")

    result = commit_v2_inventory_stock_in(
        db_session,
        tenant_id="tenant_a",
        shop_id="shop_a1",
        task_run_id="vtask_v2_stock_in_create",
        created_by_account_id="acct_001",
        payload={"item_name": "Cola", "quantity": 3, "unit": "box", "price": 18.5},
    )

    assert result.item.tenant_id == "tenant_a"
    assert result.item.name == "Cola"
    assert result.snapshot.shop_id == "shop_a1"
    assert result.snapshot.current_quantity == Decimal("3")
    assert result.event.quantity_after == Decimal("3")


def test_v2_commit_stock_in_reuses_tenant_item_and_keeps_shop_snapshots_isolated(db_session) -> None:
    from sqlalchemy import select

    from app.models import V2InventoryItem, V2InventoryStockSnapshot
    from app.services.v2_inventory import commit_v2_inventory_stock_in

    _seed_v2_inventory_context(db_session, task_run_id="vtask_v2_shop_a1")
    _seed_v2_shop(
        db_session,
        shop_id="shop_a2",
        tenant_id="tenant_a",
        code="a-2",
        name="Shop A2",
    )
    _seed_v2_task_run_for_inventory(
        db_session,
        task_run_id="vtask_v2_shop_a2",
        tenant_id="tenant_a",
        shop_id="shop_a2",
    )
    db_session.commit()

    first = commit_v2_inventory_stock_in(
        db_session,
        tenant_id="tenant_a",
        shop_id="shop_a1",
        task_run_id="vtask_v2_shop_a1",
        created_by_account_id="acct_001",
        payload={"item_name": "Cola", "quantity": 3, "unit": "box", "price": 18.5},
    )
    second = commit_v2_inventory_stock_in(
        db_session,
        tenant_id="tenant_a",
        shop_id="shop_a2",
        task_run_id="vtask_v2_shop_a2",
        created_by_account_id="acct_001",
        payload={"item_name": "Cola", "quantity": 5, "unit": "box", "price": 19},
    )

    items = list(db_session.scalars(select(V2InventoryItem)))
    snapshots = list(
        db_session.scalars(
            select(V2InventoryStockSnapshot).where(
                V2InventoryStockSnapshot.inventory_item_id == first.item.inventory_item_id
            )
        )
    )

    assert first.item.inventory_item_id == second.item.inventory_item_id
    assert len(items) == 1
    assert {(snapshot.shop_id, snapshot.current_quantity) for snapshot in snapshots} == {
        ("shop_a1", Decimal("3")),
        ("shop_a2", Decimal("5")),
    }
