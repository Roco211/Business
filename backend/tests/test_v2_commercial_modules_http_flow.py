from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select

from app.db.session import get_session_factory
from app.models import V2AuditLog, V2Confirmation, V2InventoryLedgerEvent, V2InventoryStockSnapshot
from app.models.v2_commercial import V2FinanceTransaction, V2PurchaseOrder
from app.models.v2_sales import V2SalesOrder
from test_v2_sales_orders_http_flow import _login_and_select_context, _seed_v2_sales_order_context


def _create_order(client, headers, item_id: str, *, customer_id: str | None = None) -> dict:
    payload = {
        "customer_name": "老王",
        "payment_method": "cash",
        "items": [{"inventory_item_id": item_id, "quantity": "2", "unit_price": "150.00"}],
        "note": "commercial regression",
    }
    if customer_id:
        payload["customer_id"] = customer_id
    response = client.post(
        "/api/v2/sales/orders",
        headers=headers,
        json=payload,
    )
    assert response.status_code == 200
    return response.json()["data"]["order"]


def test_sales_order_detail_cancel_and_return_restore_stock_and_write_finance(client):
    context = _seed_v2_sales_order_context(client)
    headers = _login_and_select_context(client, email=context["email"], tenant_id=context["tenant_id"], shop_id=context["shop_id"])
    order = _create_order(client, headers, context["item_id"])

    detail = client.get(f"/api/v2/sales/orders/{order['sales_order_id']}", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["data"]["order"]["sales_order_id"] == order["sales_order_id"]
    assert len(detail.json()["data"]["order"]["items"]) == 1

    cancel = client.post(f"/api/v2/sales/orders/{order['sales_order_id']}/cancel", headers=headers, json={"reason": "客户不要了"})
    assert cancel.status_code == 200
    assert cancel.json()["data"]["order"]["status"] == "cancelled"

    session = get_session_factory()()
    try:
        snapshot = session.scalar(select(V2InventoryStockSnapshot).where(V2InventoryStockSnapshot.inventory_item_id == context["item_id"]))
        assert snapshot.current_quantity == Decimal("8.000")
        reasons = [row.reason for row in session.scalars(select(V2InventoryLedgerEvent)).all()]
        assert "sales order cancelled" in reasons
        audit_actions = [row.action for row in session.scalars(select(V2AuditLog).where(V2AuditLog.tenant_id == context["tenant_id"], V2AuditLog.shop_id == context["shop_id"])).all()]
        assert "sales_order.cancel" in audit_actions
    finally:
        session.close()

    second_order = _create_order(client, headers, context["item_id"])
    ret = client.post(
        f"/api/v2/sales/orders/{second_order['sales_order_id']}/returns",
        headers=headers,
        json={"items": [{"sales_order_line_id": second_order["items"][0]["sales_order_line_id"], "quantity": "1"}], "reason": "退货"},
    )
    assert ret.status_code == 200
    assert ret.json()["data"]["order"]["status"] == "partially_refunded"

    audit = client.get(f"/api/v2/audit-logs?shop_id={context['shop_id']}&limit=50", headers=headers)
    assert audit.status_code == 200
    actions = [row["action"] for row in audit.json()["data"]["logs"]]
    assert "sales_order.cancel" in actions
    assert "sales_order.return" in actions

    finance = client.get("/api/v2/finance/transactions?limit=50", headers=headers)
    assert finance.status_code == 200
    tx_types = [tx["transaction_type"] for tx in finance.json()["data"]["transactions"]]
    assert "sales_revenue" in tx_types
    assert "sales_refund" in tx_types


def test_purchase_supplier_customer_finance_and_ai_sales_order_confirmation(client):
    context = _seed_v2_sales_order_context(client)
    headers = _login_and_select_context(client, email=context["email"], tenant_id=context["tenant_id"], shop_id=context["shop_id"])

    supplier = client.post("/api/v2/purchasing/suppliers", headers=headers, json={"name": "测试供应商", "phone": "13800000000"})
    assert supplier.status_code == 200
    supplier_id = supplier.json()["data"]["supplier"]["supplier_id"]

    suppliers = client.get("/api/v2/purchasing/suppliers", headers=headers)
    assert suppliers.status_code == 200
    assert any(row["supplier_id"] == supplier_id for row in suppliers.json()["data"]["suppliers"])

    po = client.post(
        "/api/v2/purchasing/orders",
        headers=headers,
        json={"supplier_id": supplier_id, "items": [{"inventory_item_id": context["item_id"], "quantity": "3", "unit_cost": "80.00"}], "note": "补货"},
    )
    assert po.status_code == 200
    assert po.json()["data"]["purchase_order"]["status"] == "received"
    purchase_orders = client.get("/api/v2/purchasing/orders", headers=headers)
    assert purchase_orders.status_code == 200
    assert any(row["purchase_order_id"] == po.json()["data"]["purchase_order"]["purchase_order_id"] for row in purchase_orders.json()["data"]["purchase_orders"])

    customer = client.post("/api/v2/customers", headers=headers, json={"name": "老王", "phone": "13900000000"})
    assert customer.status_code == 200
    customer_id = customer.json()["data"]["customer"]["customer_id"]
    customers = client.get("/api/v2/customers", headers=headers)
    assert customers.status_code == 200
    assert any(row["customer_id"] == customer_id for row in customers.json()["data"]["customers"])
    order_with_customer = _create_order(client, headers, context["item_id"], customer_id=customer_id)
    assert order_with_customer["customer_id"] == customer_id
    analysis = client.get("/api/v2/customers/repurchase-analysis", headers=headers)
    assert analysis.status_code == 200
    analysis_data = analysis.json()["data"]
    assert analysis_data["summary"]["customer_count"] >= 1
    assert any(row["customer_id"] == customer_id and row["order_count"] >= 1 for row in analysis_data["customers"])

    revenue_only = client.get("/api/v2/finance/transactions?transaction_type=sales_revenue&limit=50", headers=headers)
    assert revenue_only.status_code == 200
    assert {tx["transaction_type"] for tx in revenue_only.json()["data"]["transactions"]} == {"sales_revenue"}

    sales_export = client.get("/api/v2/exports/sales-orders", headers=headers)
    assert sales_export.status_code == 200
    assert sales_export.headers["content-type"].startswith("text/csv")
    assert "order_no,customer_name,total_amount,status" in sales_export.text
    assert order_with_customer["order_no"] in sales_export.text
    finance_export = client.get("/api/v2/exports/finance-transactions", headers=headers)
    assert finance_export.status_code == 200
    assert "transaction_type,direction,amount" in finance_export.text
    purchase_export = client.get("/api/v2/exports/purchase-orders", headers=headers)
    assert purchase_export.status_code == 200
    assert "order_no,supplier_id,total_amount,status" in purchase_export.text
    assert po.json()["data"]["purchase_order"]["order_no"] in purchase_export.text
    ledger_export = client.get("/api/v2/exports/inventory-ledger", headers=headers)
    assert ledger_export.status_code == 200
    assert "event_type,inventory_item_id,quantity_delta,quantity_after" in ledger_export.text
    assert "purchase_order" in ledger_export.text

    audit = client.get(f"/api/v2/audit-logs?shop_id={context['shop_id']}&limit=50", headers=headers)
    assert audit.status_code == 200
    audit_actions = [row["action"] for row in audit.json()["data"]["logs"]]
    assert "supplier.create" in audit_actions
    assert "purchase_order.create" in audit_actions
    assert "customer.create" in audit_actions

    finance = client.get("/api/v2/finance/summary", headers=headers)
    assert finance.status_code == 200
    summary = finance.json()["data"]["summary"]
    assert Decimal(str(summary["total_income"])) >= Decimal("300.00")
    assert Decimal(str(summary["total_expense"])) >= Decimal("240.00")

    draft = client.post("/api/v2/sales/order-drafts/from-text", headers=headers, json={"message": "卖出2把销售单测试电钻，单价150，客户老王"})
    assert draft.status_code == 200
    confirmation_id = draft.json()["data"]["confirmation"]["confirmation_id"]
    session = get_session_factory()()
    try:
        confirmation = session.scalar(select(V2Confirmation).where(V2Confirmation.confirmation_id == confirmation_id))
        assert confirmation is not None
        assert confirmation.confirmation_type == "sales.order_create"
        assert confirmation.status == "pending"
    finally:
        session.close()

    approve = client.post(f"/api/v2/confirmations/{confirmation_id}/approve", headers=headers, json={"resolution_payload": {}})
    assert approve.status_code == 200
    sales_execution_result = approve.json()["data"]["resolution_payload"]["execution_result"]
    assert sales_execution_result["status"] == "committed"
    assert sales_execution_result["entity_type"] == "sales_order"
    assert sales_execution_result["summary"].startswith("已创建销售单")
    assert sales_execution_result["effects"]["inventory"] == "已扣减库存"
    assert sales_execution_result["next_route"] == "/sales"
    orders = client.get("/api/v2/sales/orders?limit=50", headers=headers).json()["data"]["orders"]
    assert any(order["customer_name"] == "老王" for order in orders)

    purchase_before = len(client.get("/api/v2/purchasing/orders?limit=50", headers=headers).json()["data"]["purchase_orders"])
    purchase_draft = client.post(
        "/api/v2/purchasing/order-drafts/from-text",
        headers=headers,
        json={"message": "向测试供应商采购5把销售单测试电钻，单价80"},
    )
    assert purchase_draft.status_code == 200
    purchase_confirmation_id = purchase_draft.json()["data"]["confirmation"]["confirmation_id"]
    session = get_session_factory()()
    try:
        purchase_confirmation = session.scalar(select(V2Confirmation).where(V2Confirmation.confirmation_id == purchase_confirmation_id))
        assert purchase_confirmation is not None
        assert purchase_confirmation.confirmation_type == "purchase.order_create"
        assert purchase_confirmation.status == "pending"
        assert len(session.scalars(select(V2PurchaseOrder).where(V2PurchaseOrder.tenant_id == context["tenant_id"], V2PurchaseOrder.shop_id == context["shop_id"])).all()) == purchase_before
        assert not any(tx.source_type == "purchase_order" and tx.note == "AI purchase order draft" for tx in session.scalars(select(V2FinanceTransaction)).all())
    finally:
        session.close()

    approve_purchase = client.post(f"/api/v2/confirmations/{purchase_confirmation_id}/approve", headers=headers, json={"resolution_payload": {}})
    assert approve_purchase.status_code == 200
    purchase_execution_result = approve_purchase.json()["data"]["resolution_payload"]["execution_result"]
    assert purchase_execution_result["status"] == "committed"
    assert purchase_execution_result["entity_type"] == "purchase_order"
    assert purchase_execution_result["summary"].startswith("已创建采购单")
    assert purchase_execution_result["effects"]["inventory"] == "已入库"
    assert purchase_execution_result["effects"]["finance"] == "已记录采购支出"
    assert purchase_execution_result["next_route"] == "/purchases"
    purchase_orders_after = client.get("/api/v2/purchasing/orders?limit=50", headers=headers).json()["data"]["purchase_orders"]
    assert len(purchase_orders_after) == purchase_before + 1
    assert any(order["note"] == "AI purchase order draft" for order in purchase_orders_after)
