from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from app.db.session import get_session_factory
from app.models import (
    V2Account,
    V2InventoryItem,
    V2InventoryLedgerEvent,
    V2Shop,
    V2ShopAccess,
    V2Tenant,
    V2TenantMembership,
)
from app.services.v2_identity import hash_v2_password
from app.services.v2_time import utc_now_naive


def _seed_v2_inventory_item_audit_context(client) -> dict[str, str]:
    session = get_session_factory()()
    now = utc_now_naive()
    password_salt = "a1" * 16
    account = V2Account(
        account_id="acct_item_audit_http",
        email="item-audit-http@example.com",
        display_name="Item Audit HTTP Tester",
        password_hash=hash_v2_password("dev-password", password_salt),
        password_salt=password_salt,
        status="active",
        created_at=now,
        updated_at=now,
    )
    tenant = V2Tenant(
        tenant_id="tenant_item_audit_http",
        name="商品审计测试租户",
        slug="item-audit-http-tenant",
        status="active",
        plan_code="trial",
        owner_account_id=account.account_id,
        created_at=now,
        updated_at=now,
    )
    membership = V2TenantMembership(
        membership_id="mship_item_audit_http",
        tenant_id=tenant.tenant_id,
        account_id=account.account_id,
        role_key="owner",
        status="active",
        joined_at=now,
        updated_at=now,
    )
    shop = V2Shop(
        shop_id="shop_item_audit_http",
        tenant_id=tenant.tenant_id,
        code="ITEM-AUDIT-HTTP",
        name="商品审计测试门店",
        locale="zh-CN",
        timezone="Asia/Shanghai",
        status="active",
        created_at=now,
        updated_at=now,
    )
    other_shop = V2Shop(
        shop_id="shop_item_audit_http_other",
        tenant_id=tenant.tenant_id,
        code="ITEM-AUDIT-OTHER",
        name="商品审计其他门店",
        locale="zh-CN",
        timezone="Asia/Shanghai",
        status="active",
        created_at=now,
        updated_at=now,
    )
    access = V2ShopAccess(
        shop_access_id="access_item_audit_http",
        tenant_id=tenant.tenant_id,
        shop_id=shop.shop_id,
        membership_id=membership.membership_id,
        access_level="write",
        status="active",
        created_at=now,
    )
    item = V2InventoryItem(
        inventory_item_id="item_audit_deleted_drill",
        tenant_id=tenant.tenant_id,
        sku="AUDIT-DELETED-DRILL",
        name="审计测试已删电钻",
        barcode=None,
        default_unit="把",
        status="deleted",
        created_at=now,
        updated_at=now,
    )
    active_item = V2InventoryItem(
        inventory_item_id="item_audit_active_wrench",
        tenant_id=tenant.tenant_id,
        sku="AUDIT-ACTIVE-WRENCH",
        name="审计测试活跃扳手",
        barcode=None,
        default_unit="把",
        status="active",
        created_at=now,
        updated_at=now,
    )

    other_account = V2Account(
        account_id="acct_item_audit_http_other",
        email="item-audit-http-other@example.com",
        display_name="Other Audit Tester",
        password_hash=hash_v2_password("dev-password", "a2" * 16),
        password_salt="a2" * 16,
        status="active",
        created_at=now,
        updated_at=now,
    )
    other_tenant = V2Tenant(
        tenant_id="tenant_item_audit_http_other",
        name="商品审计其他租户",
        slug="item-audit-http-other-tenant",
        status="active",
        plan_code="trial",
        owner_account_id=other_account.account_id,
        created_at=now,
        updated_at=now,
    )
    foreign_item = V2InventoryItem(
        inventory_item_id="item_audit_foreign_drill",
        tenant_id=other_tenant.tenant_id,
        sku="FOREIGN-AUDIT-DRILL",
        name="其他租户审计电钻",
        barcode=None,
        default_unit="把",
        status="active",
        created_at=now,
        updated_at=now,
    )

    events = [
        V2InventoryLedgerEvent(
            event_id="event_audit_001_stock_in_old",
            tenant_id=tenant.tenant_id,
            shop_id=shop.shop_id,
            inventory_item_id=item.inventory_item_id,
            event_type="stock_in",
            quantity_delta=Decimal("10"),
            quantity_after=Decimal("10"),
            unit="把",
            price=Decimal("80.00"),
            source_type="seed",
            source_id="seed_audit_001",
            reason="首次入库",
            created_by_account_id=account.account_id,
            occurred_at=now - timedelta(minutes=30),
        ),
        V2InventoryLedgerEvent(
            event_id="event_audit_002_stock_out_new",
            tenant_id=tenant.tenant_id,
            shop_id=shop.shop_id,
            inventory_item_id=item.inventory_item_id,
            event_type="stock_out",
            quantity_delta=Decimal("-3"),
            quantity_after=Decimal("7"),
            unit="把",
            price=Decimal("120.00"),
            source_type="seed",
            source_id="seed_audit_002",
            reason="客户销售出库",
            created_by_account_id=account.account_id,
            occurred_at=now - timedelta(minutes=5),
        ),
        V2InventoryLedgerEvent(
            event_id="event_audit_003_other_shop",
            tenant_id=tenant.tenant_id,
            shop_id=other_shop.shop_id,
            inventory_item_id=item.inventory_item_id,
            event_type="stock_in",
            quantity_delta=Decimal("99"),
            quantity_after=Decimal("99"),
            unit="把",
            price=Decimal("1.00"),
            source_type="seed",
            source_id="seed_audit_other_shop",
            reason="其他门店不应泄露",
            created_by_account_id=account.account_id,
            occurred_at=now - timedelta(minutes=1),
        ),
        V2InventoryLedgerEvent(
            event_id="event_audit_004_other_item",
            tenant_id=tenant.tenant_id,
            shop_id=shop.shop_id,
            inventory_item_id=active_item.inventory_item_id,
            event_type="stock_in",
            quantity_delta=Decimal("55"),
            quantity_after=Decimal("55"),
            unit="把",
            price=Decimal("2.00"),
            source_type="seed",
            source_id="seed_audit_other_item",
            reason="其他商品不应泄露",
            created_by_account_id=account.account_id,
            occurred_at=now,
        ),
        V2InventoryLedgerEvent(
            event_id="event_audit_005_foreign_tenant",
            tenant_id=other_tenant.tenant_id,
            shop_id="shop_foreign_audit",
            inventory_item_id=foreign_item.inventory_item_id,
            event_type="stock_in",
            quantity_delta=Decimal("66"),
            quantity_after=Decimal("66"),
            unit="把",
            price=Decimal("3.00"),
            source_type="seed",
            source_id="seed_audit_foreign",
            reason="其他租户不应泄露",
            created_by_account_id=other_account.account_id,
            occurred_at=now,
        ),
    ]

    session.add_all([
        account,
        tenant,
        membership,
        shop,
        other_shop,
        access,
        item,
        active_item,
        other_account,
        other_tenant,
        foreign_item,
        *events,
    ])
    session.commit()
    session.close()
    return {
        "tenant_id": tenant.tenant_id,
        "shop_id": shop.shop_id,
        "email": account.email,
        "deleted_item_id": item.inventory_item_id,
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


def test_http_inventory_item_audit_returns_deleted_item_history_for_current_shop_only(client):
    context = _seed_v2_inventory_item_audit_context(client)
    headers = _login_and_select_context(
        client,
        email=context["email"],
        tenant_id=context["tenant_id"],
        shop_id=context["shop_id"],
    )

    response = client.get(
        f"/api/v2/inventory/items/{context['deleted_item_id']}/audit?limit=10",
        headers=headers,
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["inventory_item_id"] == context["deleted_item_id"]
    assert data["count"] == 2
    events = data["events"]
    assert [event["event_id"] for event in events] == [
        "event_audit_002_stock_out_new",
        "event_audit_001_stock_in_old",
    ]
    assert events[0]["event_type"] == "stock_out"
    assert events[0]["quantity_delta"] == "-3.000"
    assert events[0]["quantity_after"] == "7.000"
    assert events[0]["reason"] == "客户销售出库"
    assert events[0]["created_by_account_id"] == "acct_item_audit_http"
    assert all(event["shop_id"] == context["shop_id"] for event in events)


def test_http_inventory_item_audit_enforces_tenant_boundary_and_limit(client):
    context = _seed_v2_inventory_item_audit_context(client)
    headers = _login_and_select_context(
        client,
        email=context["email"],
        tenant_id=context["tenant_id"],
        shop_id=context["shop_id"],
    )

    foreign_response = client.get(
        f"/api/v2/inventory/items/{context['foreign_item_id']}/audit",
        headers=headers,
    )
    assert foreign_response.status_code == 404

    limited_response = client.get(
        f"/api/v2/inventory/items/{context['deleted_item_id']}/audit?limit=1",
        headers=headers,
    )
    assert limited_response.status_code == 200
    limited_data = limited_response.json()["data"]
    assert limited_data["count"] == 1
    assert [event["event_id"] for event in limited_data["events"]] == ["event_audit_002_stock_out_new"]
