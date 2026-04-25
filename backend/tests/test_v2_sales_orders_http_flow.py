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


def _seed_v2_sales_order_context(client) -> dict[str, str]:
    session = get_session_factory()()
    now = utc_now_naive()
    password_salt = "91" * 16
    account = V2Account(
        account_id="acct_sales_order_http",
        email="sales-order-http@example.com",
        display_name="Sales Order HTTP Tester",
        password_hash=hash_v2_password("dev-password", password_salt),
        password_salt=password_salt,
        status="active",
        created_at=now,
        updated_at=now,
    )
    tenant = V2Tenant(
        tenant_id="tenant_sales_order_http",
        name="销售单接口测试租户",
        slug="sales-order-http-tenant",
        status="active",
        plan_code="trial",
        owner_account_id=account.account_id,
        created_at=now,
        updated_at=now,
    )
    membership = V2TenantMembership(
        membership_id="mship_sales_order_http",
        tenant_id=tenant.tenant_id,
        account_id=account.account_id,
        role_key="owner",
        status="active",
        joined_at=now,
        updated_at=now,
    )
    shop = V2Shop(
        shop_id="shop_sales_order_http",
        tenant_id=tenant.tenant_id,
        code="SALES-ORDER-HTTP",
        name="销售单接口测试门店",
        locale="zh-CN",
        timezone="Asia/Shanghai",
        status="active",
        created_at=now,
        updated_at=now,
    )
    access = V2ShopAccess(
        shop_access_id="access_sales_order_http",
        tenant_id=tenant.tenant_id,
        shop_id=shop.shop_id,
        membership_id=membership.membership_id,
        access_level="write",
        status="active",
        created_at=now,
    )
    item = V2InventoryItem(
        inventory_item_id="item_sales_order_drill",
        tenant_id=tenant.tenant_id,
        sku="SALES-ORDER-DRILL",
        name="销售单测试电钻",
        barcode=None,
        default_unit="把",
        status="active",
        created_at=now,
        updated_at=now,
    )
    snapshot = V2InventoryStockSnapshot(
        snapshot_id="snap_sales_order_drill",
        tenant_id=tenant.tenant_id,
        shop_id=shop.shop_id,
        inventory_item_id=item.inventory_item_id,
        current_quantity=Decimal("8"),
        current_price=Decimal("120.00"),
        low_stock_threshold=Decimal("2"),
        updated_at=now,
    )

    other_account = V2Account(
        account_id="acct_sales_order_other",
        email="sales-order-other@example.com",
        display_name="Other Sales Tenant Tester",
        password_hash=hash_v2_password("dev-password", "92" * 16),
        password_salt="92" * 16,
        status="active",
        created_at=now,
        updated_at=now,
    )
    other_tenant = V2Tenant(
        tenant_id="tenant_sales_order_other",
        name="其他销售单租户",
        slug="sales-order-other-tenant",
        status="active",
        plan_code="trial",
        owner_account_id=other_account.account_id,
        created_at=now,
        updated_at=now,
    )
    other_item = V2InventoryItem(
        inventory_item_id="item_sales_order_foreign",
        tenant_id=other_tenant.tenant_id,
        sku="FOREIGN-SALES-ORDER-DRILL",
        name="其他租户销售单电钻",
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


def test_http_sales_order_create_writes_order_lines_and_stock_out_ledger(client):
    context = _seed_v2_sales_order_context(client)
    headers = _login_and_select_context(
        client,
        email=context["email"],
        tenant_id=context["tenant_id"],
        shop_id=context["shop_id"],
    )

    response = client.post(
        "/api/v2/sales/orders",
        headers=headers,
        json={
            "customer_name": "散客",
            "payment_method": "cash",
            "items": [
                {
                    "inventory_item_id": context["item_id"],
                    "quantity": "2",
                    "unit_price": "150.00",
                }
            ],
            "note": "pytest sales order",
        },
    )

    assert response.status_code == 200
    data = response.json()["data"]["order"]
    assert data["tenant_id"] == context["tenant_id"]
    assert data["shop_id"] == context["shop_id"]
    assert data["order_no"].startswith("SO")
    assert data["status"] == "paid"
    assert Decimal(str(data["total_amount"])) == Decimal("300.00")
    assert data["items"][0]["item_name"] == "销售单测试电钻"
    assert Decimal(str(data["items"][0]["line_amount"])) == Decimal("300.00")

    session = get_session_factory()()
    try:
        snapshot = session.scalar(
            select(V2InventoryStockSnapshot).where(
                V2InventoryStockSnapshot.tenant_id == context["tenant_id"],
                V2InventoryStockSnapshot.shop_id == context["shop_id"],
                V2InventoryStockSnapshot.inventory_item_id == context["item_id"],
            )
        )
        event = session.scalar(select(V2InventoryLedgerEvent))
        assert snapshot is not None
        assert snapshot.current_quantity == Decimal("6.000")
        assert event is not None
        assert event.tenant_id == context["tenant_id"]
        assert event.shop_id == context["shop_id"]
        assert event.inventory_item_id == context["item_id"]
        assert event.event_type == "stock_out"
        assert event.quantity_delta == Decimal("-2.000")
        assert event.quantity_after == Decimal("6.000")
        assert event.source_type == "sales_order"
        assert event.reason == "sales order paid"
    finally:
        session.close()


def test_http_sales_order_list_is_tenant_and_shop_scoped(client):
    context = _seed_v2_sales_order_context(client)
    headers = _login_and_select_context(
        client,
        email=context["email"],
        tenant_id=context["tenant_id"],
        shop_id=context["shop_id"],
    )
    create_response = client.post(
        "/api/v2/sales/orders",
        headers=headers,
        json={
            "customer_name": "散客",
            "payment_method": "wechat",
            "items": [{"inventory_item_id": context["item_id"], "quantity": "1", "unit_price": "99.00"}],
        },
    )
    assert create_response.status_code == 200

    response = client.get("/api/v2/sales/orders?limit=20", headers=headers)

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["count"] == 1
    assert data["orders"][0]["tenant_id"] == context["tenant_id"]
    assert data["orders"][0]["shop_id"] == context["shop_id"]
    assert data["orders"][0]["items_count"] == 1


def test_http_sales_order_rejects_insufficient_stock_without_side_effects(client):
    context = _seed_v2_sales_order_context(client)
    headers = _login_and_select_context(
        client,
        email=context["email"],
        tenant_id=context["tenant_id"],
        shop_id=context["shop_id"],
    )

    response = client.post(
        "/api/v2/sales/orders",
        headers=headers,
        json={
            "items": [{"inventory_item_id": context["item_id"], "quantity": "99", "unit_price": "150.00"}],
        },
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "insufficient_stock"
    session = get_session_factory()()
    try:
        events = list(session.scalars(select(V2InventoryLedgerEvent)))
        snapshot = session.scalar(select(V2InventoryStockSnapshot))
        assert events == []
        assert snapshot is not None
        assert snapshot.current_quantity == Decimal("8.000")
    finally:
        session.close()


def test_http_sales_order_rejects_foreign_tenant_item(client):
    context = _seed_v2_sales_order_context(client)
    headers = _login_and_select_context(
        client,
        email=context["email"],
        tenant_id=context["tenant_id"],
        shop_id=context["shop_id"],
    )

    response = client.post(
        "/api/v2/sales/orders",
        headers=headers,
        json={
            "items": [{"inventory_item_id": context["foreign_item_id"], "quantity": "1", "unit_price": "150.00"}],
        },
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "inventory_item_not_found"
