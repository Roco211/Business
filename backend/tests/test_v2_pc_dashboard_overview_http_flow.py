from __future__ import annotations

from decimal import Decimal

from app.db.session import get_session_factory
from app.models import (
    V2Account,
    V2Confirmation,
    V2ConversationSession,
    V2InventoryItem,
    V2InventoryLedgerEvent,
    V2InventoryStockSnapshot,
    V2Message,
    V2Shop,
    V2ShopAccess,
    V2TaskRun,
    V2Tenant,
    V2TenantMembership,
)
from app.services.v2_identity import hash_v2_password
from app.services.v2_time import utc_now_naive


def _seed_pc_dashboard_context() -> dict[str, str]:
    session = get_session_factory()()
    now = utc_now_naive()
    salt = "f1" * 16
    account = V2Account(
        account_id="acct_pc_dashboard",
        email="pc-dashboard@example.com",
        display_name="PC Dashboard Owner",
        password_hash=hash_v2_password("dev-password", salt),
        password_salt=salt,
        status="active",
        created_at=now,
        updated_at=now,
    )
    tenant = V2Tenant(
        tenant_id="tenant_pc_dashboard",
        name="PC Dashboard 租户",
        slug="pc-dashboard-tenant",
        status="active",
        plan_code="trial",
        owner_account_id=account.account_id,
        created_at=now,
        updated_at=now,
    )
    membership = V2TenantMembership(
        membership_id="mship_pc_dashboard",
        tenant_id=tenant.tenant_id,
        account_id=account.account_id,
        role_key="owner",
        status="active",
        joined_at=now,
        updated_at=now,
    )
    shop = V2Shop(
        shop_id="shop_pc_dashboard",
        tenant_id=tenant.tenant_id,
        code="PC-DASH",
        name="PC Dashboard 当前门店",
        locale="zh-CN",
        timezone="Asia/Shanghai",
        status="active",
        created_at=now,
        updated_at=now,
    )
    access = V2ShopAccess(
        shop_access_id="access_pc_dashboard",
        tenant_id=tenant.tenant_id,
        shop_id=shop.shop_id,
        membership_id=membership.membership_id,
        access_level="write",
        status="active",
        created_at=now,
    )
    item = V2InventoryItem(
        inventory_item_id="item_pc_dashboard_active",
        tenant_id=tenant.tenant_id,
        sku="PC-ACTIVE",
        name="PC Dashboard 螺丝",
        barcode=None,
        default_unit="个",
        status="active",
        created_at=now,
        updated_at=now,
    )
    deleted_item = V2InventoryItem(
        inventory_item_id="item_pc_dashboard_deleted",
        tenant_id=tenant.tenant_id,
        sku="PC-DELETED",
        name="PC Dashboard 已删除商品",
        barcode=None,
        default_unit="个",
        status="deleted",
        created_at=now,
        updated_at=now,
    )
    snapshot = V2InventoryStockSnapshot(
        snapshot_id="snap_pc_dashboard_active",
        tenant_id=tenant.tenant_id,
        shop_id=shop.shop_id,
        inventory_item_id=item.inventory_item_id,
        current_quantity=Decimal("2"),
        current_price=Decimal("9.90"),
        low_stock_threshold=Decimal("5"),
        updated_at=now,
    )
    deleted_snapshot = V2InventoryStockSnapshot(
        snapshot_id="snap_pc_dashboard_deleted",
        tenant_id=tenant.tenant_id,
        shop_id=shop.shop_id,
        inventory_item_id=deleted_item.inventory_item_id,
        current_quantity=Decimal("0"),
        current_price=Decimal("999.00"),
        low_stock_threshold=Decimal("10"),
        updated_at=now,
    )
    sale_event = V2InventoryLedgerEvent(
        event_id="event_pc_dashboard_sale",
        tenant_id=tenant.tenant_id,
        shop_id=shop.shop_id,
        inventory_item_id=item.inventory_item_id,
        event_type="stock_out",
        quantity_delta=Decimal("-3"),
        quantity_after=Decimal("2"),
        unit="个",
        price=Decimal("9.90"),
        source_type="seed",
        source_id="seed-sale",
        reason="pc dashboard sale",
        created_by_account_id=account.account_id,
        occurred_at=now,
    )
    deleted_sale_event = V2InventoryLedgerEvent(
        event_id="event_pc_dashboard_deleted_sale",
        tenant_id=tenant.tenant_id,
        shop_id=shop.shop_id,
        inventory_item_id=deleted_item.inventory_item_id,
        event_type="stock_out",
        quantity_delta=Decimal("-1"),
        quantity_after=Decimal("0"),
        unit="个",
        price=Decimal("999.00"),
        source_type="seed",
        source_id="seed-deleted-sale",
        reason="deleted sale should not leak",
        created_by_account_id=account.account_id,
        occurred_at=now,
    )
    convo = V2ConversationSession(
        session_id="session_pc_dashboard",
        tenant_id=tenant.tenant_id,
        shop_id=shop.shop_id,
        session_type="chat",
        title="PC Dashboard AI",
        status="active",
        last_event_seq=0,
        initiated_by_account_id=account.account_id,
        created_at=now,
        updated_at=now,
    )
    msg = V2Message(
        message_id="msg_pc_dashboard",
        tenant_id=tenant.tenant_id,
        shop_id=shop.shop_id,
        session_id=convo.session_id,
        actor_type="user",
        actor_id=account.account_id,
        message_kind="text",
        payload_json={"text": "螺丝入库10个"},
        client_request_id="pc-dashboard-seed",
        created_at=now,
    )
    task = V2TaskRun(
        task_run_id="task_pc_dashboard",
        tenant_id=tenant.tenant_id,
        shop_id=shop.shop_id,
        session_id=convo.session_id,
        source_message_id=msg.message_id,
        intent_type="inventory.stock_in",
        status="awaiting_confirmation",
        risk_level="medium",
        trace_id="trace-pc-dashboard",
        result_summary="等待确认入库",
        created_at=now,
        updated_at=now,
    )
    confirmation = V2Confirmation(
        confirmation_id="confirm_pc_dashboard",
        tenant_id=tenant.tenant_id,
        shop_id=shop.shop_id,
        task_run_id=task.task_run_id,
        confirmation_type="inventory.stock_in",
        status="pending",
        draft_payload={"fields": {"inventory_item_id": item.inventory_item_id, "quantity": "10"}},
        created_at=now,
    )
    session.add_all([
        account,
        tenant,
        membership,
        shop,
        access,
        item,
        deleted_item,
        snapshot,
        deleted_snapshot,
        sale_event,
        deleted_sale_event,
        convo,
        msg,
        task,
        confirmation,
    ])
    session.commit()
    session.close()
    return {"email": account.email, "tenant_id": tenant.tenant_id, "shop_id": shop.shop_id}


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


def test_pc_dashboard_overview_returns_ai_native_backend_backed_home_data(client):
    context = _seed_pc_dashboard_context()
    headers = _login_and_select_context(
        client, email=context["email"], tenant_id=context["tenant_id"], shop_id=context["shop_id"]
    )

    response = client.get("/api/v2/pc-dashboard/overview", headers=headers)

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["store"]["shop_id"] == context["shop_id"]
    assert payload["store"]["shop_name"] == "PC Dashboard 当前门店"
    assert payload["user"]["display_name"] == "PC Dashboard Owner"

    kpis = {item["key"]: item for item in payload["kpis"]}
    assert kpis["today_sales_amount"]["label"] == "今日销售额"
    assert kpis["today_sales_amount"]["value"] == 29.7
    assert kpis["today_sales_transactions"]["label"] == "今日销售笔数"
    assert kpis["today_sales_transactions"]["value"] == 1
    assert "订单" not in kpis["today_sales_transactions"]["label"]
    assert kpis["low_stock_count"]["value"] == 1
    assert kpis["pending_confirmation_count"]["value"] == 1

    employees = {employee["key"]: employee for employee in payload["ai_employees"]}
    employee_names = {employee["name"] for employee in employees.values()}
    assert "AI运营协调官" in employee_names
    assert "经营数据分析员" in employee_names
    assert "库存风控专员" in employee_names
    assert "商品档案管理员" in employee_names
    assert "经营策略顾问" in employee_names
    informal_coordinator_name = "\u5c0f\u96c5"
    assert informal_coordinator_name not in employee_names

    coordinator = employees["operations_coordinator"]
    assert coordinator["status"] == "attention_needed"
    assert coordinator["status_label"] == "等待老板确认"
    assert coordinator["today_task_count"] == 1
    assert coordinator["pending_confirmation_count"] == 1
    assert coordinator["completed_task_count"] == 0
    assert coordinator["last_activity_label"] == "等待确认入库"

    inventory_employee = employees["inventory_risk_controller"]
    assert inventory_employee["status_label"] == "等待老板确认"
    assert inventory_employee["today_task_count"] == 1
    assert inventory_employee["pending_confirmation_count"] == 1
    assert {metric["label"] for metric in inventory_employee["metrics"]} >= {"今日任务", "待确认", "低库存商品"}

    assert payload["top_priorities"]
    assert payload["suggestions"]
    assert payload["suggestions"][0]["evidence"]
    assert "risk" in payload["suggestions"][0]
    assert payload["suggestions"][0]["requires_confirmation"] is True
    assert payload["activities"]
    assert payload["todos"]
    notifications = payload["notifications"]
    assert notifications["unread_count"] == 2
    assert notifications["attention_count"] == 2
    assert notifications["generated_at"]
    notification_items = {item["id"]: item for item in notifications["items"]}
    assert notification_items["notification_pending_confirmations"]["source_employee"] == "AI运营协调官"
    assert notification_items["notification_pending_confirmations"]["route"] == "/tasks"
    assert notification_items["notification_pending_confirmations"]["action_label"] == "去确认"
    assert notification_items["notification_low_stock"]["source_employee"] == "库存风控专员"
    assert notification_items["notification_low_stock"]["route"] == "/inventory?filter=low-stock"
    assert notification_items["notification_low_stock"]["evidence"]

    report = payload["daily_advisor_report"]
    assert report["title"] == "今日经营参谋日报"
    assert report["generated_by"] == "经营策略顾问"
    assert report["summary"].startswith("今日销售额29.70元")
    assert report["business_health"] == "attention_needed"
    sections = {section["key"]: section for section in report["sections"]}
    assert sections["sales"]["title"] == "销售概况"
    assert "1笔销售" in sections["sales"]["content"]
    assert sections["inventory"]["metrics"]["low_stock_count"] == 1
    assert sections["tasks"]["metrics"]["pending_confirmation_count"] == 1
    assert report["next_actions"][0]["route"] == "/tasks"
    assert report["risk_notes"]
    assert any("确认" in note for note in report["risk_notes"])
    assert report["evidence"]["source"] == "pc-dashboard-overview"
    assert report["evidence"]["sales_transaction_count"] == 1


def test_pc_dashboard_daily_report_detail_and_history_are_backend_backed(client):
    context = _seed_pc_dashboard_context()
    headers = _login_and_select_context(
        client, email=context["email"], tenant_id=context["tenant_id"], shop_id=context["shop_id"]
    )

    today_response = client.get("/api/v2/pc-dashboard/daily-reports/today", headers=headers)

    assert today_response.status_code == 200
    today = today_response.json()["data"]
    assert today["title"] == "AI经营日报详情"
    assert today["generated_by"] == "经营策略顾问"
    assert today["report_date"]
    assert today["summary"].startswith("今日销售额29.70元")
    assert today["business_health"] == "attention_needed"
    assert {section["key"] for section in today["sections"]} >= {"sales", "inventory", "tasks", "execution_recaps"}
    assert today["execution_recaps"][0]["summary"] == "等待确认入库"
    assert today["execution_recaps"][0]["status"] == "awaiting_confirmation"
    assert today["timeline"]
    assert today["history"]
    assert today["evidence"]["source"] == "pc-dashboard-daily-report"
    assert today["evidence"]["pending_confirmation_count"] == 1

    history_response = client.get("/api/v2/pc-dashboard/daily-reports/history?days=7", headers=headers)

    assert history_response.status_code == 200
    history = history_response.json()["data"]
    assert len(history["items"]) == 7
    first = history["items"][0]
    assert first["report_date"] == today["report_date"]
    assert first["total_revenue"] == 29.7
    assert first["transaction_count"] == 1
    assert first["low_stock_count"] == 1
    assert first["pending_confirmation_count"] == 1
    assert first["route"] == "/daily-report"


def test_pc_dashboard_execution_recaps_list_returns_committed_ai_work(client):
    context = _seed_pc_dashboard_context()
    session = get_session_factory()()
    now = utc_now_naive()
    committed_task = session.get(V2TaskRun, "task_pc_dashboard")
    assert committed_task is not None
    committed_task.intent_type = "sales.order_create"
    committed_task.status = "committed"
    committed_task.risk_level = "medium"
    committed_task.result_summary = "销售单已落账"
    committed_task.updated_at = now
    committed_task.completed_at = now
    committed_confirmation = session.get(V2Confirmation, "confirm_pc_dashboard")
    assert committed_confirmation is not None
    committed_confirmation.confirmation_type = "sales.order_create"
    committed_confirmation.status = "approved"
    committed_confirmation.draft_payload = {"items": [{"name": "PC Dashboard 螺丝", "quantity": "3"}]}
    committed_confirmation.resolution_payload = {
        "execution_result": {
            "status": "committed",
            "kind": "sales_order",
            "summary": "已创建销售单 SO-PC-1，并完成库存与收入记录。",
            "effects": ["已创建销售单", "已扣减库存", "已记录销售收入"],
            "next_route": "/sales",
        }
    }
    committed_confirmation.approved_by_account_id = "acct_pc_dashboard"
    committed_confirmation.resolved_at = now
    session.commit()
    session.close()
    headers = _login_and_select_context(
        client, email=context["email"], tenant_id=context["tenant_id"], shop_id=context["shop_id"]
    )

    response = client.get("/api/v2/pc-dashboard/execution-recaps?limit=20", headers=headers)

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["summary"]["total_count"] == 1
    assert payload["summary"]["sales_order_count"] == 1
    assert payload["summary"]["purchase_order_count"] == 0
    assert payload["summary"]["inventory_count"] == 0
    assert payload["summary"]["other_count"] == 0
    assert len(payload["items"]) == 1
    recap = payload["items"][0]
    assert recap["confirmation_id"] == "confirm_pc_dashboard"
    assert recap["task_run_id"] == "task_pc_dashboard"
    assert recap["kind"] == "sales_order"
    assert recap["status"] == "committed"
    assert recap["summary"].startswith("已创建销售单")
    assert recap["effects"] == ["已创建销售单", "已扣减库存", "已记录销售收入"]
    assert recap["next_route"] == "/sales"
    assert recap["source_employee"] == "经营数据分析员"
    assert recap["intent_type"] == "sales.order_create"
    assert recap["risk_level"] == "medium"
    assert recap["evidence"]
    assert all("pending" not in item["confirmation_id"] for item in payload["items"])


def test_pc_dashboard_overview_requires_selected_context(client):
    response = client.get("/api/v2/pc-dashboard/overview")

    assert response.status_code in {401, 403}
