from __future__ import annotations

from sqlalchemy import select

from app.db.session import get_session_factory
from app.models import V2AuditLog, V2Shop, V2ShopAccess, V2TenantMembership
from app.models.v2_governance import V2ExportJob
from app.services.v2_time import utc_now_naive
from test_v2_sales_orders_http_flow import _login_and_select_context, _seed_v2_sales_order_context


def _create_sample_sales_order(client, headers, item_id: str) -> str:
    response = client.post(
        "/api/v2/sales/orders",
        headers=headers,
        json={
            "customer_name": "异步导出客户",
            "payment_method": "cash",
            "items": [{"inventory_item_id": item_id, "quantity": "1", "unit_price": "99.00"}],
            "note": "async export regression",
        },
    )
    assert response.status_code == 200
    return response.json()["data"]["order"]["order_no"]


def test_async_export_job_creates_completed_downloadable_csv_and_audit(client):
    context = _seed_v2_sales_order_context(client)
    headers = _login_and_select_context(client, email=context["email"], tenant_id=context["tenant_id"], shop_id=context["shop_id"])
    order_no = _create_sample_sales_order(client, headers, context["item_id"])

    create = client.post("/api/v2/exports/jobs", headers=headers, json={"export_type": "sales_orders", "limit": 100})
    assert create.status_code == 200
    job = create.json()["data"]["job"]
    assert job["export_type"] == "sales_orders"
    assert job["status"] in {"queued", "running", "completed"}
    job_id = job["export_job_id"]

    detail = client.get(f"/api/v2/exports/jobs/{job_id}", headers=headers)
    assert detail.status_code == 200
    detail_job = detail.json()["data"]["job"]
    assert detail_job["status"] == "completed"
    assert detail_job["row_count"] >= 1
    assert detail_job["download_ready"] is True

    download = client.get(f"/api/v2/exports/jobs/{job_id}/download", headers=headers)
    assert download.status_code == 200
    assert download.headers["content-type"].startswith("text/csv")
    assert "order_no,customer_name,total_amount,status" in download.text
    assert order_no in download.text

    list_response = client.get("/api/v2/exports/jobs", headers=headers)
    assert list_response.status_code == 200
    assert any(row["export_job_id"] == job_id for row in list_response.json()["data"]["jobs"])

    session = get_session_factory()()
    try:
        persisted = session.get(V2ExportJob, job_id)
        assert persisted is not None
        assert persisted.tenant_id == context["tenant_id"]
        assert persisted.shop_id == context["shop_id"]
        assert persisted.status == "completed"
        audit_actions = [
            row.action
            for row in session.scalars(
                select(V2AuditLog).where(V2AuditLog.tenant_id == context["tenant_id"], V2AuditLog.shop_id == context["shop_id"])
            ).all()
        ]
        assert "export_job.create" in audit_actions
        assert "export_job.complete" in audit_actions
        assert "export_job.download" in audit_actions
    finally:
        session.close()


def test_async_export_job_enforces_export_permission(client):
    context = _seed_v2_sales_order_context(client)
    session = get_session_factory()()
    try:
        membership = session.scalar(select(V2TenantMembership).where(V2TenantMembership.tenant_id == context["tenant_id"]))
        assert membership is not None
        membership.role_key = "clerk"
        session.commit()
    finally:
        session.close()
    headers = _login_and_select_context(client, email=context["email"], tenant_id=context["tenant_id"], shop_id=context["shop_id"])

    response = client.post("/api/v2/exports/jobs", headers=headers, json={"export_type": "finance_transactions", "limit": 100})
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "permission_denied"


def test_async_export_job_is_hidden_across_shop_contexts(client):
    context = _seed_v2_sales_order_context(client)
    headers_a = _login_and_select_context(client, email=context["email"], tenant_id=context["tenant_id"], shop_id=context["shop_id"])
    create = client.post("/api/v2/exports/jobs", headers=headers_a, json={"export_type": "sales_orders", "limit": 100})
    assert create.status_code == 200
    job_id = create.json()["data"]["job"]["export_job_id"]

    session = get_session_factory()()
    try:
        now = utc_now_naive()
        membership = session.scalar(select(V2TenantMembership).where(V2TenantMembership.tenant_id == context["tenant_id"]))
        assert membership is not None
        second_shop = V2Shop(
            shop_id="shop_async_export_other",
            tenant_id=context["tenant_id"],
            code="ASYNC-EXPORT-OTHER",
            name="异步导出隔离门店",
            locale="zh-CN",
            timezone="Asia/Shanghai",
            status="active",
            created_at=now,
            updated_at=now,
        )
        access = V2ShopAccess(
            shop_access_id="access_async_export_other",
            tenant_id=context["tenant_id"],
            shop_id=second_shop.shop_id,
            membership_id=membership.membership_id,
            access_level="write",
            status="active",
            created_at=now,
        )
        session.add_all([second_shop, access])
        session.commit()
    finally:
        session.close()

    headers_b = _login_and_select_context(client, email=context["email"], tenant_id=context["tenant_id"], shop_id="shop_async_export_other")

    detail = client.get(f"/api/v2/exports/jobs/{job_id}", headers=headers_b)
    assert detail.status_code == 404
    download = client.get(f"/api/v2/exports/jobs/{job_id}/download", headers=headers_b)
    assert download.status_code == 404
