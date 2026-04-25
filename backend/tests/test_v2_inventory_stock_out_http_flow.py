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


def _seed_v2_inventory_stock_out_context(client) -> dict[str, str]:
    session = get_session_factory()()
    now = utc_now_naive()
    password_salt = "77" * 16
    account = V2Account(
        account_id="acct_stock_out_http",
        email="stock-out-http@example.com",
        display_name="Stock Out HTTP Tester",
        password_hash=hash_v2_password("dev-password", password_salt),
        password_salt=password_salt,
        status="active",
        created_at=now,
        updated_at=now,
    )
    tenant = V2Tenant(
        tenant_id="tenant_stock_out_http",
        name="正式出库接口测试租户",
        slug="stock-out-http-tenant",
        status="active",
        plan_code="trial",
        owner_account_id=account.account_id,
        created_at=now,
        updated_at=now,
    )
    membership = V2TenantMembership(
        membership_id="mship_stock_out_http",
        tenant_id=tenant.tenant_id,
        account_id=account.account_id,
        role_key="owner",
        status="active",
        joined_at=now,
        updated_at=now,
    )
    shop = V2Shop(
        shop_id="shop_stock_out_http",
        tenant_id=tenant.tenant_id,
        code="STOCK-OUT-HTTP",
        name="正式出库接口测试门店",
        locale="zh-CN",
        timezone="Asia/Shanghai",
        status="active",
        created_at=now,
        updated_at=now,
    )
    access = V2ShopAccess(
        shop_access_id="access_stock_out_http",
        tenant_id=tenant.tenant_id,
        shop_id=shop.shop_id,
        membership_id=membership.membership_id,
        access_level="write",
        status="active",
        created_at=now,
    )
    item = V2InventoryItem(
        inventory_item_id="item_stock_out_http_drill",
        tenant_id=tenant.tenant_id,
        sku="STOCK-OUT-HTTP-DRILL",
        name="正式出库测试电钻",
        barcode=None,
        default_unit="把",
        status="active",
        created_at=now,
        updated_at=now,
    )
    snapshot = V2InventoryStockSnapshot(
        snapshot_id="snap_stock_out_http_drill",
        tenant_id=tenant.tenant_id,
        shop_id=shop.shop_id,
        inventory_item_id=item.inventory_item_id,
        current_quantity=Decimal("10"),
        current_price=Decimal("99.00"),
        low_stock_threshold=Decimal("3"),
        updated_at=now,
    )

    other_account = V2Account(
        account_id="acct_stock_out_http_other",
        email="stock-out-http-other@example.com",
        display_name="Other Tenant Tester",
        password_hash=hash_v2_password("dev-password", "88" * 16),
        password_salt="88" * 16,
        status="active",
        created_at=now,
        updated_at=now,
    )
    other_tenant = V2Tenant(
        tenant_id="tenant_stock_out_http_other",
        name="其他出库租户",
        slug="stock-out-http-other-tenant",
        status="active",
        plan_code="trial",
        owner_account_id=other_account.account_id,
        created_at=now,
        updated_at=now,
    )
    other_item = V2InventoryItem(
        inventory_item_id="item_stock_out_http_foreign",
        tenant_id=other_tenant.tenant_id,
        sku="FOREIGN-STOCK-OUT-DRILL",
        name="其他租户出库电钻",
        barcode=None,
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
        item,
        snapshot,
        other_account,
        other_tenant,
        other_item,
    ])
    session.commit()
    session.close()
    return {
        "tenant_id": tenant.tenant_id,
        "shop_id": shop.shop_id,
        "email": account.email,
        "item_id": item.inventory_item_id,
        "foreign_item_id": other_item.inventory_item_id,
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


def test_http_inventory_stock_out_writes_ledger_event_and_decrements_snapshot(client):
    context = _seed_v2_inventory_stock_out_context(client)
    headers = _login_and_select_context(
        client,
        email=context["email"],
        tenant_id=context["tenant_id"],
        shop_id=context["shop_id"],
    )

    response = client.post(
        "/api/v2/inventory/stock-out",
        headers=headers,
        json={
            "inventory_item_id": context["item_id"],
            "expected_quantity": "10",
            "stock_out_quantity": "4",
            "reason": "pytest formal stock-out",
        },
    )

    assert response.status_code == 200
    assert response.json()["data"]["inventory_item_id"] == context["item_id"]
    assert Decimal(str(response.json()["data"]["new_quantity"])) == Decimal("6")

    session = get_session_factory()()
    try:
        event = session.scalar(select(V2InventoryLedgerEvent))
        snapshot = session.scalar(
            select(V2InventoryStockSnapshot).where(
                V2InventoryStockSnapshot.tenant_id == context["tenant_id"],
                V2InventoryStockSnapshot.shop_id == context["shop_id"],
                V2InventoryStockSnapshot.inventory_item_id == context["item_id"],
            )
        )
        assert event is not None
        assert event.tenant_id == context["tenant_id"]
        assert event.shop_id == context["shop_id"]
        assert event.inventory_item_id == context["item_id"]
        assert event.event_type == "stock_out"
        assert event.quantity_delta == Decimal("-4.000")
        assert event.quantity_after == Decimal("6.000")
        assert event.source_type == "inventory_stock_out"
        assert event.reason == "pytest formal stock-out"
        assert snapshot is not None
        assert snapshot.current_quantity == Decimal("6.000")
        assert snapshot.current_price == Decimal("99.000")
    finally:
        session.close()


def test_http_inventory_stock_out_rejects_conflict_without_side_effects(client):
    context = _seed_v2_inventory_stock_out_context(client)
    headers = _login_and_select_context(
        client,
        email=context["email"],
        tenant_id=context["tenant_id"],
        shop_id=context["shop_id"],
    )

    response = client.post(
        "/api/v2/inventory/stock-out",
        headers=headers,
        json={
            "inventory_item_id": context["item_id"],
            "expected_quantity": "9",
            "stock_out_quantity": "2",
            "reason": "stale client quantity",
        },
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "inventory_conflict"

    session = get_session_factory()()
    try:
        events = list(session.scalars(select(V2InventoryLedgerEvent)))
        snapshot = session.scalar(
            select(V2InventoryStockSnapshot).where(
                V2InventoryStockSnapshot.tenant_id == context["tenant_id"],
                V2InventoryStockSnapshot.shop_id == context["shop_id"],
                V2InventoryStockSnapshot.inventory_item_id == context["item_id"],
            )
        )
        assert events == []
        assert snapshot is not None
        assert snapshot.current_quantity == Decimal("10.000")
    finally:
        session.close()


def test_http_inventory_stock_out_rejects_insufficient_stock_without_side_effects(client):
    context = _seed_v2_inventory_stock_out_context(client)
    headers = _login_and_select_context(
        client,
        email=context["email"],
        tenant_id=context["tenant_id"],
        shop_id=context["shop_id"],
    )

    response = client.post(
        "/api/v2/inventory/stock-out",
        headers=headers,
        json={
            "inventory_item_id": context["item_id"],
            "expected_quantity": "10",
            "stock_out_quantity": "11",
            "reason": "exceeds stock",
        },
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"

    session = get_session_factory()()
    try:
        events = list(session.scalars(select(V2InventoryLedgerEvent)))
        snapshot = session.scalar(
            select(V2InventoryStockSnapshot).where(
                V2InventoryStockSnapshot.tenant_id == context["tenant_id"],
                V2InventoryStockSnapshot.shop_id == context["shop_id"],
                V2InventoryStockSnapshot.inventory_item_id == context["item_id"],
            )
        )
        assert events == []
        assert snapshot is not None
        assert snapshot.current_quantity == Decimal("10.000")
    finally:
        session.close()


def test_http_inventory_stock_out_rejects_foreign_tenant_item_without_side_effects(client):
    context = _seed_v2_inventory_stock_out_context(client)
    headers = _login_and_select_context(
        client,
        email=context["email"],
        tenant_id=context["tenant_id"],
        shop_id=context["shop_id"],
    )

    response = client.post(
        "/api/v2/inventory/stock-out",
        headers=headers,
        json={
            "inventory_item_id": context["foreign_item_id"],
            "expected_quantity": "10",
            "stock_out_quantity": "2",
            "reason": "should be rejected",
        },
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "inventory_item_not_found"

    session = get_session_factory()()
    try:
        events = list(session.scalars(select(V2InventoryLedgerEvent)))
        snapshot = session.scalar(
            select(V2InventoryStockSnapshot).where(
                V2InventoryStockSnapshot.tenant_id == context["tenant_id"],
                V2InventoryStockSnapshot.shop_id == context["shop_id"],
                V2InventoryStockSnapshot.inventory_item_id == context["item_id"],
            )
        )
        foreign_snapshot = session.scalar(
            select(V2InventoryStockSnapshot).where(
                V2InventoryStockSnapshot.inventory_item_id == context["foreign_item_id"]
            )
        )
        assert events == []
        assert snapshot is not None
        assert snapshot.current_quantity == Decimal("10.000")
        assert foreign_snapshot is None
    finally:
        session.close()
