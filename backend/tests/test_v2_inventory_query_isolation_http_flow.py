from __future__ import annotations

from decimal import Decimal

from app.db.session import get_session_factory
from app.models import (
    V2Account,
    V2InventoryItem,
    V2InventoryLedgerEvent,
    V2InventoryStockSnapshot,
    V2Shop,
    V2ShopAccess,
    V2Tenant,
    V2TenantMembership,
)
from app.services.v2_identity import hash_v2_password
from app.services.v2_time import utc_now_naive


def _seed_v2_inventory_query_context(client) -> dict[str, str]:
    session = get_session_factory()()
    now = utc_now_naive()
    password_salt = "99" * 16
    account = V2Account(
        account_id="acct_inventory_query",
        email="inventory-query@example.com",
        display_name="Inventory Query Tester",
        password_hash=hash_v2_password("dev-password", password_salt),
        password_salt=password_salt,
        status="active",
        created_at=now,
        updated_at=now,
    )
    tenant = V2Tenant(
        tenant_id="tenant_inventory_query",
        name="库存查询隔离测试租户",
        slug="inventory-query-tenant",
        status="active",
        plan_code="trial",
        owner_account_id=account.account_id,
        created_at=now,
        updated_at=now,
    )
    membership = V2TenantMembership(
        membership_id="mship_inventory_query",
        tenant_id=tenant.tenant_id,
        account_id=account.account_id,
        role_key="owner",
        status="active",
        joined_at=now,
        updated_at=now,
    )
    shop = V2Shop(
        shop_id="shop_inventory_query",
        tenant_id=tenant.tenant_id,
        code="INV-QUERY",
        name="库存查询测试门店",
        locale="zh-CN",
        timezone="Asia/Shanghai",
        status="active",
        created_at=now,
        updated_at=now,
    )
    other_shop = V2Shop(
        shop_id="shop_inventory_query_other",
        tenant_id=tenant.tenant_id,
        code="INV-QUERY-OTHER",
        name="同租户其他门店",
        locale="zh-CN",
        timezone="Asia/Shanghai",
        status="active",
        created_at=now,
        updated_at=now,
    )
    access = V2ShopAccess(
        shop_access_id="access_inventory_query",
        tenant_id=tenant.tenant_id,
        shop_id=shop.shop_id,
        membership_id=membership.membership_id,
        access_level="write",
        status="active",
        created_at=now,
    )
    active_item = V2InventoryItem(
        inventory_item_id="item_inventory_query_active",
        tenant_id=tenant.tenant_id,
        sku="INV-QUERY-ACTIVE",
        name="查询可见电钻",
        barcode=None,
        default_unit="把",
        status="active",
        created_at=now,
        updated_at=now,
    )
    deleted_item = V2InventoryItem(
        inventory_item_id="item_inventory_query_deleted",
        tenant_id=tenant.tenant_id,
        sku="INV-QUERY-DELETED",
        name="查询已删除电钻",
        barcode=None,
        default_unit="把",
        status="deleted",
        created_at=now,
        updated_at=now,
    )
    active_snapshot = V2InventoryStockSnapshot(
        snapshot_id="snap_inventory_query_active",
        tenant_id=tenant.tenant_id,
        shop_id=shop.shop_id,
        inventory_item_id=active_item.inventory_item_id,
        current_quantity=Decimal("8"),
        current_price=Decimal("120.00"),
        low_stock_threshold=Decimal("2"),
        updated_at=now,
    )
    deleted_snapshot = V2InventoryStockSnapshot(
        snapshot_id="snap_inventory_query_deleted",
        tenant_id=tenant.tenant_id,
        shop_id=shop.shop_id,
        inventory_item_id=deleted_item.inventory_item_id,
        current_quantity=Decimal("6"),
        current_price=Decimal("80.00"),
        low_stock_threshold=Decimal("2"),
        updated_at=now,
    )
    other_shop_snapshot = V2InventoryStockSnapshot(
        snapshot_id="snap_inventory_query_other_shop",
        tenant_id=tenant.tenant_id,
        shop_id=other_shop.shop_id,
        inventory_item_id=active_item.inventory_item_id,
        current_quantity=Decimal("99"),
        current_price=Decimal("121.00"),
        low_stock_threshold=Decimal("2"),
        updated_at=now,
    )
    active_event = V2InventoryLedgerEvent(
        event_id="event_inventory_query_active",
        tenant_id=tenant.tenant_id,
        shop_id=shop.shop_id,
        inventory_item_id=active_item.inventory_item_id,
        event_type="stock_in",
        quantity_delta=Decimal("8"),
        quantity_after=Decimal("8"),
        unit="把",
        price=Decimal("120.00"),
        source_type="seed",
        source_id="seed-active",
        reason="active item event",
        created_by_account_id=account.account_id,
        occurred_at=now,
    )
    deleted_event = V2InventoryLedgerEvent(
        event_id="event_inventory_query_deleted",
        tenant_id=tenant.tenant_id,
        shop_id=shop.shop_id,
        inventory_item_id=deleted_item.inventory_item_id,
        event_type="stock_in",
        quantity_delta=Decimal("6"),
        quantity_after=Decimal("6"),
        unit="把",
        price=Decimal("80.00"),
        source_type="seed",
        source_id="seed-deleted",
        reason="deleted item event",
        created_by_account_id=account.account_id,
        occurred_at=now,
    )
    other_shop_event = V2InventoryLedgerEvent(
        event_id="event_inventory_query_other_shop",
        tenant_id=tenant.tenant_id,
        shop_id=other_shop.shop_id,
        inventory_item_id=active_item.inventory_item_id,
        event_type="stock_in",
        quantity_delta=Decimal("99"),
        quantity_after=Decimal("99"),
        unit="把",
        price=Decimal("121.00"),
        source_type="seed",
        source_id="seed-other-shop",
        reason="other shop event",
        created_by_account_id=account.account_id,
        occurred_at=now,
    )

    foreign_account = V2Account(
        account_id="acct_inventory_query_foreign",
        email="inventory-query-foreign@example.com",
        display_name="Foreign Tenant Tester",
        password_hash=hash_v2_password("dev-password", "aa" * 16),
        password_salt="aa" * 16,
        status="active",
        created_at=now,
        updated_at=now,
    )
    foreign_tenant = V2Tenant(
        tenant_id="tenant_inventory_query_foreign",
        name="其他库存查询租户",
        slug="inventory-query-foreign-tenant",
        status="active",
        plan_code="trial",
        owner_account_id=foreign_account.account_id,
        created_at=now,
        updated_at=now,
    )
    foreign_shop = V2Shop(
        shop_id="shop_inventory_query_foreign",
        tenant_id=foreign_tenant.tenant_id,
        code="INV-QUERY-FOREIGN",
        name="其他租户门店",
        locale="zh-CN",
        timezone="Asia/Shanghai",
        status="active",
        created_at=now,
        updated_at=now,
    )
    foreign_item = V2InventoryItem(
        inventory_item_id="item_inventory_query_foreign",
        tenant_id=foreign_tenant.tenant_id,
        sku="INV-QUERY-FOREIGN",
        name="其他租户电钻",
        barcode=None,
        default_unit="把",
        status="active",
        created_at=now,
        updated_at=now,
    )
    foreign_snapshot = V2InventoryStockSnapshot(
        snapshot_id="snap_inventory_query_foreign",
        tenant_id=foreign_tenant.tenant_id,
        shop_id=foreign_shop.shop_id,
        inventory_item_id=foreign_item.inventory_item_id,
        current_quantity=Decimal("77"),
        current_price=Decimal("122.00"),
        low_stock_threshold=Decimal("2"),
        updated_at=now,
    )
    foreign_event = V2InventoryLedgerEvent(
        event_id="event_inventory_query_foreign",
        tenant_id=foreign_tenant.tenant_id,
        shop_id=foreign_shop.shop_id,
        inventory_item_id=foreign_item.inventory_item_id,
        event_type="stock_in",
        quantity_delta=Decimal("77"),
        quantity_after=Decimal("77"),
        unit="把",
        price=Decimal("122.00"),
        source_type="seed",
        source_id="seed-foreign",
        reason="foreign tenant event",
        created_by_account_id=foreign_account.account_id,
        occurred_at=now,
    )

    session.add_all([
        account,
        tenant,
        membership,
        shop,
        other_shop,
        access,
        active_item,
        deleted_item,
        active_snapshot,
        deleted_snapshot,
        other_shop_snapshot,
        active_event,
        deleted_event,
        other_shop_event,
        foreign_account,
        foreign_tenant,
        foreign_shop,
        foreign_item,
        foreign_snapshot,
        foreign_event,
    ])
    session.commit()
    session.close()
    return {"tenant_id": tenant.tenant_id, "shop_id": shop.shop_id, "email": account.email}


def _login_and_select_context(client, *, email: str, tenant_id: str, shop_id: str) -> dict[str, str]:
    login_response = client.post(
        "/api/v2/auth/login",
        json={"auth_method": "email_password", "email": email, "password": "dev-password"},
    )
    assert login_response.status_code == 200
    token = login_response.json()["data"].get("accessToken") or login_response.json()["data"].get("access_token")
    context_response = client.post(
        "/api/v2/context/select",
        headers={"Authorization": f"Bearer {token}"},
        json={"tenant_id": tenant_id, "shop_id": shop_id},
    )
    assert context_response.status_code == 200
    context_token = context_response.json()["data"].get("contextToken") or context_response.json()["data"].get(
        "context_token"
    )
    return {"Authorization": f"Bearer {token}", "X-Context-Token": context_token}


def test_inventory_item_list_only_returns_active_items_in_current_tenant(client):
    context = _seed_v2_inventory_query_context(client)
    headers = _login_and_select_context(
        client, email=context["email"], tenant_id=context["tenant_id"], shop_id=context["shop_id"]
    )

    response = client.get("/api/v2/inventory/items?limit=50", headers=headers)

    assert response.status_code == 200
    item_ids = {item["inventory_item_id"] for item in response.json()["data"]["items"]}
    assert "item_inventory_query_active" in item_ids
    assert "item_inventory_query_deleted" not in item_ids
    assert "item_inventory_query_foreign" not in item_ids


def test_inventory_stock_list_only_returns_current_shop_active_item_snapshots(client):
    context = _seed_v2_inventory_query_context(client)
    headers = _login_and_select_context(
        client, email=context["email"], tenant_id=context["tenant_id"], shop_id=context["shop_id"]
    )

    response = client.get("/api/v2/inventory/stock?limit=50", headers=headers)

    assert response.status_code == 200
    snapshot_ids = {item["snapshot_id"] for item in response.json()["data"]["items"]}
    assert snapshot_ids == {"snap_inventory_query_active"}


def test_inventory_event_list_only_returns_current_shop_active_item_events(client):
    context = _seed_v2_inventory_query_context(client)
    headers = _login_and_select_context(
        client, email=context["email"], tenant_id=context["tenant_id"], shop_id=context["shop_id"]
    )

    response = client.get("/api/v2/inventory/events?limit=50", headers=headers)

    assert response.status_code == 200
    event_ids = {event["event_id"] for event in response.json()["data"]["events"]}
    assert event_ids == {"event_inventory_query_active"}
