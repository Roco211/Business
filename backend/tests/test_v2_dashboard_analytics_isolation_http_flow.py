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


def _seed_v2_dashboard_analytics_context(client) -> dict[str, str]:
    session = get_session_factory()()
    now = utc_now_naive()
    password_salt = "c5" * 16
    account = V2Account(
        account_id="acct_dashboard_analytics",
        email="dashboard-analytics@example.com",
        display_name="Dashboard Analytics Tester",
        password_hash=hash_v2_password("dev-password", password_salt),
        password_salt=password_salt,
        status="active",
        created_at=now,
        updated_at=now,
    )
    tenant = V2Tenant(
        tenant_id="tenant_dashboard_analytics",
        name="Dashboard Analytics 租户",
        slug="dashboard-analytics-tenant",
        status="active",
        plan_code="trial",
        owner_account_id=account.account_id,
        created_at=now,
        updated_at=now,
    )
    membership = V2TenantMembership(
        membership_id="mship_dashboard_analytics",
        tenant_id=tenant.tenant_id,
        account_id=account.account_id,
        role_key="owner",
        status="active",
        joined_at=now,
        updated_at=now,
    )
    shop = V2Shop(
        shop_id="shop_dashboard_analytics",
        tenant_id=tenant.tenant_id,
        code="DASH-ANALYTICS",
        name="Dashboard Analytics 当前门店",
        locale="zh-CN",
        timezone="Asia/Shanghai",
        status="active",
        created_at=now,
        updated_at=now,
    )
    other_shop = V2Shop(
        shop_id="shop_dashboard_analytics_other",
        tenant_id=tenant.tenant_id,
        code="DASH-ANALYTICS-OTHER",
        name="Dashboard Analytics 同租户其他门店",
        locale="zh-CN",
        timezone="Asia/Shanghai",
        status="active",
        created_at=now,
        updated_at=now,
    )
    access = V2ShopAccess(
        shop_access_id="access_dashboard_analytics",
        tenant_id=tenant.tenant_id,
        shop_id=shop.shop_id,
        membership_id=membership.membership_id,
        access_level="write",
        status="active",
        created_at=now,
    )

    active_item = V2InventoryItem(
        inventory_item_id="item_dashboard_active",
        tenant_id=tenant.tenant_id,
        sku="DASH-ACTIVE",
        name="Dashboard 可见电钻",
        barcode=None,
        default_unit="把",
        status="active",
        created_at=now,
        updated_at=now,
    )
    deleted_item = V2InventoryItem(
        inventory_item_id="item_dashboard_deleted",
        tenant_id=tenant.tenant_id,
        sku="DASH-DELETED",
        name="Dashboard 已删除电钻",
        barcode=None,
        default_unit="把",
        status="deleted",
        created_at=now,
        updated_at=now,
    )
    active_snapshot = V2InventoryStockSnapshot(
        snapshot_id="snap_dashboard_active",
        tenant_id=tenant.tenant_id,
        shop_id=shop.shop_id,
        inventory_item_id=active_item.inventory_item_id,
        current_quantity=Decimal("1"),
        current_price=Decimal("100.00"),
        low_stock_threshold=Decimal("3"),
        updated_at=now,
    )
    deleted_snapshot = V2InventoryStockSnapshot(
        snapshot_id="snap_dashboard_deleted",
        tenant_id=tenant.tenant_id,
        shop_id=shop.shop_id,
        inventory_item_id=deleted_item.inventory_item_id,
        current_quantity=Decimal("0"),
        current_price=Decimal("999.00"),
        low_stock_threshold=Decimal("10"),
        updated_at=now,
    )
    other_shop_snapshot = V2InventoryStockSnapshot(
        snapshot_id="snap_dashboard_other_shop",
        tenant_id=tenant.tenant_id,
        shop_id=other_shop.shop_id,
        inventory_item_id=active_item.inventory_item_id,
        current_quantity=Decimal("0"),
        current_price=Decimal("888.00"),
        low_stock_threshold=Decimal("20"),
        updated_at=now,
    )

    active_stock_out = V2InventoryLedgerEvent(
        event_id="event_dashboard_active_stock_out",
        tenant_id=tenant.tenant_id,
        shop_id=shop.shop_id,
        inventory_item_id=active_item.inventory_item_id,
        event_type="stock_out",
        quantity_delta=Decimal("-3"),
        quantity_after=Decimal("1"),
        unit="把",
        price=Decimal("100.00"),
        source_type="seed",
        source_id="seed-active-out",
        reason="active sale",
        created_by_account_id=account.account_id,
        occurred_at=now,
    )
    active_stock_in = V2InventoryLedgerEvent(
        event_id="event_dashboard_active_stock_in",
        tenant_id=tenant.tenant_id,
        shop_id=shop.shop_id,
        inventory_item_id=active_item.inventory_item_id,
        event_type="stock_in",
        quantity_delta=Decimal("1"),
        quantity_after=Decimal("4"),
        unit="把",
        price=Decimal("60.00"),
        source_type="seed",
        source_id="seed-active-in",
        reason="active cost",
        created_by_account_id=account.account_id,
        occurred_at=now,
    )
    deleted_stock_out = V2InventoryLedgerEvent(
        event_id="event_dashboard_deleted_stock_out",
        tenant_id=tenant.tenant_id,
        shop_id=shop.shop_id,
        inventory_item_id=deleted_item.inventory_item_id,
        event_type="stock_out",
        quantity_delta=Decimal("-7"),
        quantity_after=Decimal("0"),
        unit="把",
        price=Decimal("1000.00"),
        source_type="seed",
        source_id="seed-deleted-out",
        reason="deleted sale should be hidden",
        created_by_account_id=account.account_id,
        occurred_at=now,
    )
    deleted_stock_in = V2InventoryLedgerEvent(
        event_id="event_dashboard_deleted_stock_in",
        tenant_id=tenant.tenant_id,
        shop_id=shop.shop_id,
        inventory_item_id=deleted_item.inventory_item_id,
        event_type="stock_in",
        quantity_delta=Decimal("10"),
        quantity_after=Decimal("10"),
        unit="把",
        price=Decimal("999.00"),
        source_type="seed",
        source_id="seed-deleted-in",
        reason="deleted cost should be hidden",
        created_by_account_id=account.account_id,
        occurred_at=now,
    )
    other_shop_stock_out = V2InventoryLedgerEvent(
        event_id="event_dashboard_other_shop_stock_out",
        tenant_id=tenant.tenant_id,
        shop_id=other_shop.shop_id,
        inventory_item_id=active_item.inventory_item_id,
        event_type="stock_out",
        quantity_delta=Decimal("-9"),
        quantity_after=Decimal("0"),
        unit="把",
        price=Decimal("888.00"),
        source_type="seed",
        source_id="seed-other-shop-out",
        reason="other shop sale should be hidden",
        created_by_account_id=account.account_id,
        occurred_at=now,
    )

    foreign_account = V2Account(
        account_id="acct_dashboard_foreign",
        email="dashboard-foreign@example.com",
        display_name="Dashboard Foreign Tester",
        password_hash=hash_v2_password("dev-password", "d5" * 16),
        password_salt="d5" * 16,
        status="active",
        created_at=now,
        updated_at=now,
    )
    foreign_tenant = V2Tenant(
        tenant_id="tenant_dashboard_foreign",
        name="Dashboard 其他租户",
        slug="dashboard-foreign-tenant",
        status="active",
        plan_code="trial",
        owner_account_id=foreign_account.account_id,
        created_at=now,
        updated_at=now,
    )
    foreign_shop = V2Shop(
        shop_id="shop_dashboard_foreign",
        tenant_id=foreign_tenant.tenant_id,
        code="DASH-FOREIGN",
        name="Dashboard 其他租户门店",
        locale="zh-CN",
        timezone="Asia/Shanghai",
        status="active",
        created_at=now,
        updated_at=now,
    )
    foreign_item = V2InventoryItem(
        inventory_item_id="item_dashboard_foreign",
        tenant_id=foreign_tenant.tenant_id,
        sku="DASH-FOREIGN",
        name="Dashboard 其他租户电钻",
        barcode=None,
        default_unit="把",
        status="active",
        created_at=now,
        updated_at=now,
    )
    foreign_snapshot = V2InventoryStockSnapshot(
        snapshot_id="snap_dashboard_foreign",
        tenant_id=foreign_tenant.tenant_id,
        shop_id=foreign_shop.shop_id,
        inventory_item_id=foreign_item.inventory_item_id,
        current_quantity=Decimal("0"),
        current_price=Decimal("777.00"),
        low_stock_threshold=Decimal("30"),
        updated_at=now,
    )
    foreign_stock_out = V2InventoryLedgerEvent(
        event_id="event_dashboard_foreign_stock_out",
        tenant_id=foreign_tenant.tenant_id,
        shop_id=foreign_shop.shop_id,
        inventory_item_id=foreign_item.inventory_item_id,
        event_type="stock_out",
        quantity_delta=Decimal("-11"),
        quantity_after=Decimal("0"),
        unit="把",
        price=Decimal("777.00"),
        source_type="seed",
        source_id="seed-foreign-out",
        reason="foreign sale should be hidden",
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
        active_stock_out,
        active_stock_in,
        deleted_stock_out,
        deleted_stock_in,
        other_shop_stock_out,
        foreign_account,
        foreign_tenant,
        foreign_shop,
        foreign_item,
        foreign_snapshot,
        foreign_stock_out,
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


def test_dashboard_summary_only_aggregates_current_shop_active_item_data(client):
    context = _seed_v2_dashboard_analytics_context(client)
    headers = _login_and_select_context(
        client, email=context["email"], tenant_id=context["tenant_id"], shop_id=context["shop_id"]
    )

    response = client.get("/api/v2/dashboard/summary?days=30", headers=headers)

    assert response.status_code == 200
    payload = response.json()["data"]

    revenue = payload["revenue_summary"]
    assert revenue["total_revenue"] == 300.0
    assert revenue["total_cost"] == 60.0
    assert revenue["gross_profit"] == 240.0
    assert revenue["transaction_count"] == 1
    assert revenue["items_sold"] == 3.0

    ranking_item_ids = {item["item_id"] for item in payload["sales_ranking"]}
    assert ranking_item_ids == {"item_dashboard_active"}
    assert payload["sales_ranking"][0]["total_sold"] == 3.0
    assert payload["sales_ranking"][0]["total_revenue"] == 300.0

    low_stock_item_ids = {item["item_id"] for item in payload["low_stock"]["items"]}
    assert low_stock_item_ids == {"item_dashboard_active"}
    assert payload["low_stock"]["count"] == 1

    assert payload["pending_tasks"]["low_stock_count"] == 1
    assert payload["pending_tasks"]["recent_tx_count"] == 1
    assert len(payload["daily_revenue_series"]) == 1
    assert payload["daily_revenue_series"][0]["revenue"] == 300.0
    assert payload["daily_revenue_series"][0]["items_sold"] == 3.0
    assert payload["daily_revenue_series"][0]["transactions"] == 1
