from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select

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


def _seed_v2_inventory_item_crud_context(client) -> dict[str, str]:
    session = get_session_factory()()
    now = utc_now_naive()
    password_salt = "91" * 16
    account = V2Account(
        account_id="acct_item_crud_http",
        email="item-crud-http@example.com",
        display_name="Item CRUD HTTP Tester",
        password_hash=hash_v2_password("dev-password", password_salt),
        password_salt=password_salt,
        status="active",
        created_at=now,
        updated_at=now,
    )
    tenant = V2Tenant(
        tenant_id="tenant_item_crud_http",
        name="商品 CRUD 测试租户",
        slug="item-crud-http-tenant",
        status="active",
        plan_code="trial",
        owner_account_id=account.account_id,
        created_at=now,
        updated_at=now,
    )
    membership = V2TenantMembership(
        membership_id="mship_item_crud_http",
        tenant_id=tenant.tenant_id,
        account_id=account.account_id,
        role_key="owner",
        status="active",
        joined_at=now,
        updated_at=now,
    )
    shop = V2Shop(
        shop_id="shop_item_crud_http",
        tenant_id=tenant.tenant_id,
        code="ITEM-CRUD-HTTP",
        name="商品 CRUD 测试门店",
        locale="zh-CN",
        timezone="Asia/Shanghai",
        status="active",
        created_at=now,
        updated_at=now,
    )
    access = V2ShopAccess(
        shop_access_id="access_item_crud_http",
        tenant_id=tenant.tenant_id,
        shop_id=shop.shop_id,
        membership_id=membership.membership_id,
        access_level="write",
        status="active",
        created_at=now,
    )
    existing_item = V2InventoryItem(
        inventory_item_id="item_crud_existing_drill",
        tenant_id=tenant.tenant_id,
        sku="CRUD-DRILL-OLD",
        name="商品CRUD旧电钻",
        barcode="690000000001",
        default_unit="把",
        status="active",
        created_at=now,
        updated_at=now,
    )
    snapshot = V2InventoryStockSnapshot(
        snapshot_id="snap_item_crud_existing_drill",
        tenant_id=tenant.tenant_id,
        shop_id=shop.shop_id,
        inventory_item_id=existing_item.inventory_item_id,
        current_quantity=Decimal("8"),
        current_price=Decimal("88.00"),
        low_stock_threshold=Decimal("2"),
        updated_at=now,
    )
    event = V2InventoryLedgerEvent(
        event_id="event_item_crud_existing_drill",
        tenant_id=tenant.tenant_id,
        shop_id=shop.shop_id,
        inventory_item_id=existing_item.inventory_item_id,
        event_type="stock_in",
        quantity_delta=Decimal("8"),
        quantity_after=Decimal("8"),
        unit="把",
        price=Decimal("88.00"),
        source_type="seed",
        source_id="seed_item_crud",
        reason="seed existing stock",
        created_by_account_id=account.account_id,
        occurred_at=now,
    )

    other_account = V2Account(
        account_id="acct_item_crud_http_other",
        email="item-crud-http-other@example.com",
        display_name="Other Item CRUD Tester",
        password_hash=hash_v2_password("dev-password", "92" * 16),
        password_salt="92" * 16,
        status="active",
        created_at=now,
        updated_at=now,
    )
    other_tenant = V2Tenant(
        tenant_id="tenant_item_crud_http_other",
        name="商品 CRUD 其他租户",
        slug="item-crud-http-other-tenant",
        status="active",
        plan_code="trial",
        owner_account_id=other_account.account_id,
        created_at=now,
        updated_at=now,
    )
    foreign_item = V2InventoryItem(
        inventory_item_id="item_crud_foreign_drill",
        tenant_id=other_tenant.tenant_id,
        sku="FOREIGN-CRUD-DRILL",
        name="其他租户CRUD电钻",
        barcode="690000000002",
        default_unit="把",
        status="active",
        created_at=now,
        updated_at=now,
    )

    session.add_all([
        account,
        tenant,
        membership,
        shop,
        access,
        existing_item,
        snapshot,
        event,
        other_account,
        other_tenant,
        foreign_item,
    ])
    session.commit()
    session.close()
    return {
        "tenant_id": tenant.tenant_id,
        "shop_id": shop.shop_id,
        "email": account.email,
        "existing_item_id": existing_item.inventory_item_id,
        "foreign_item_id": foreign_item.inventory_item_id,
    }


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


def test_http_inventory_item_create_detail_update_and_soft_delete(client):
    context = _seed_v2_inventory_item_crud_context(client)
    headers = _login_and_select_context(
        client,
        email=context["email"],
        tenant_id=context["tenant_id"],
        shop_id=context["shop_id"],
    )

    create_response = client.post(
        "/api/v2/inventory/items",
        headers=headers,
        json={
            "sku": "CRUD-NEW-WRENCH",
            "name": "商品CRUD新扳手",
            "barcode": "690000000003",
            "default_unit": "把",
        },
    )
    assert create_response.status_code == 200
    created = create_response.json()["data"]["item"]
    created_item_id = created["inventory_item_id"]
    assert created["tenant_id"] == context["tenant_id"]
    assert created["sku"] == "CRUD-NEW-WRENCH"
    assert created["name"] == "商品CRUD新扳手"
    assert created["barcode"] == "690000000003"
    assert created["default_unit"] == "把"
    assert created["status"] == "active"

    detail_response = client.get(f"/api/v2/inventory/items/{created_item_id}", headers=headers)
    assert detail_response.status_code == 200
    assert detail_response.json()["data"]["item"]["inventory_item_id"] == created_item_id

    update_response = client.patch(
        f"/api/v2/inventory/items/{created_item_id}",
        headers=headers,
        json={
            "sku": "CRUD-NEW-WRENCH-V2",
            "name": "商品CRUD新扳手二代",
            "barcode": None,
            "default_unit": "套",
        },
    )
    assert update_response.status_code == 200
    updated = update_response.json()["data"]["item"]
    assert updated["sku"] == "CRUD-NEW-WRENCH-V2"
    assert updated["name"] == "商品CRUD新扳手二代"
    assert updated["barcode"] is None
    assert updated["default_unit"] == "套"
    assert updated["status"] == "active"

    delete_response = client.delete(f"/api/v2/inventory/items/{created_item_id}", headers=headers)
    assert delete_response.status_code == 200
    deleted = delete_response.json()["data"]["item"]
    assert deleted["inventory_item_id"] == created_item_id
    assert deleted["status"] == "deleted"

    deleted_detail_response = client.get(f"/api/v2/inventory/items/{created_item_id}", headers=headers)
    assert deleted_detail_response.status_code == 404

    list_response = client.get("/api/v2/inventory/items?limit=50", headers=headers)
    assert list_response.status_code == 200
    listed_ids = {item["inventory_item_id"] for item in list_response.json()["data"]["items"]}
    assert created_item_id not in listed_ids

    session = get_session_factory()()
    try:
        stored = session.scalar(
            select(V2InventoryItem).where(V2InventoryItem.inventory_item_id == created_item_id)
        )
        assert stored is not None
        assert stored.status == "deleted"
    finally:
        session.close()


def test_http_inventory_item_crud_enforces_tenant_boundary_and_preserves_history(client):
    context = _seed_v2_inventory_item_crud_context(client)
    headers = _login_and_select_context(
        client,
        email=context["email"],
        tenant_id=context["tenant_id"],
        shop_id=context["shop_id"],
    )

    for method, path, kwargs in (
        (client.get, f"/api/v2/inventory/items/{context['foreign_item_id']}", {}),
        (client.patch, f"/api/v2/inventory/items/{context['foreign_item_id']}", {"json": {"name": "越权修改"}}),
        (client.delete, f"/api/v2/inventory/items/{context['foreign_item_id']}", {}),
    ):
        response = method(path, headers=headers, **kwargs)
        assert response.status_code == 404

    delete_existing_response = client.delete(
        f"/api/v2/inventory/items/{context['existing_item_id']}",
        headers=headers,
    )
    assert delete_existing_response.status_code == 200
    assert delete_existing_response.json()["data"]["item"]["status"] == "deleted"

    stock_response = client.get("/api/v2/inventory/stock?limit=50", headers=headers)
    assert stock_response.status_code == 200
    stock_ids = {item["inventory_item_id"] for item in stock_response.json()["data"]["items"]}
    assert context["existing_item_id"] not in stock_ids

    events_response = client.get("/api/v2/inventory/events?limit=50", headers=headers)
    assert events_response.status_code == 200
    event_ids = {event["inventory_item_id"] for event in events_response.json()["data"]["events"]}
    assert context["existing_item_id"] not in event_ids

    session = get_session_factory()()
    try:
        historical_event = session.scalar(
            select(V2InventoryLedgerEvent).where(
                V2InventoryLedgerEvent.inventory_item_id == context["existing_item_id"]
            )
        )
        historical_snapshot = session.scalar(
            select(V2InventoryStockSnapshot).where(
                V2InventoryStockSnapshot.inventory_item_id == context["existing_item_id"]
            )
        )
        assert historical_event is not None
        assert historical_snapshot is not None
    finally:
        session.close()
