from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select

from app.db.session import get_session_factory
from app.models import V2Confirmation, V2InventoryLedgerEvent, V2InventoryStockSnapshot
from app.models.v2_sales import V2SalesOrder
from test_v2_sales_orders_http_flow import _login_and_select_context, _seed_v2_sales_order_context


def _create_order(client, headers, item_id: str) -> dict:
    response = client.post(
        "/api/v2/sales/orders",
        headers=headers,
        json={
            "customer_name": "老王",
            "payment_method": "cash",
            "items": [{"inventory_item_id": item_id, "quantity": "2", "unit_price": "150.00"}],
            "note": "commercial regression",
        },
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
    customers = client.get("/api/v2/customers", headers=headers)
    assert customers.status_code == 200
    assert any(row["customer_id"] == customer.json()["data"]["customer"]["customer_id"] for row in customers.json()["data"]["customers"])
    _create_order(client, headers, context["item_id"])
    analysis = client.get("/api/v2/customers/repurchase-analysis", headers=headers)
    assert analysis.status_code == 200
    assert analysis.json()["data"]["summary"]["customer_count"] >= 1

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
    orders = client.get("/api/v2/sales/orders?limit=50", headers=headers).json()["data"]["orders"]
    assert any(order["customer_name"] == "老王" for order in orders)
