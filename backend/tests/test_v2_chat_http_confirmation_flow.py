from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import select

from app.api.v2.routes import chat as chat_routes
from app.models import (
    V2Account,
    V2Confirmation,
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


@dataclass(frozen=True)
class _FakeIntent:
    intent_type: str
    item_name: str | None
    quantity: int | None
    confidence: float = 0.99


class _FakeLLMService:
    def __init__(self, intent: _FakeIntent) -> None:
        self.intent = intent

    def parse_intent(self, user_message: str, db_session=None, history=None):
        return self.intent

    def generate_response(self, query_result, user_message: str, history=None):  # pragma: no cover - tx path bypasses this
        raise AssertionError("stock transaction path should not call generate_response")


def _seed_v2_chat_http_context(
    db_session,
    *,
    current_quantity: Decimal = Decimal("10"),
) -> tuple[str, str, str, str]:
    now = utc_now_naive()
    password_salt = "44" * 16
    account = V2Account(
        account_id="acct_chat_http_confirm",
        email="chat-http-confirm@example.com",
        display_name="Chat HTTP Confirm Tester",
        password_hash=hash_v2_password("dev-password", password_salt),
        password_salt=password_salt,
        status="active",
        created_at=now,
        updated_at=now,
    )
    tenant = V2Tenant(
        tenant_id="tenant_chat_http_confirm",
        name="Chat HTTP 确认流测试租户",
        slug="chat-http-confirm-tenant",
        status="active",
        plan_code="trial",
        owner_account_id=account.account_id,
        created_at=now,
        updated_at=now,
    )
    membership = V2TenantMembership(
        membership_id="mship_chat_http_confirm",
        tenant_id=tenant.tenant_id,
        account_id=account.account_id,
        role_key="owner",
        status="active",
        joined_at=now,
        updated_at=now,
    )
    shop = V2Shop(
        shop_id="shop_chat_http_confirm",
        tenant_id=tenant.tenant_id,
        code="CHAT-HTTP",
        name="Chat HTTP 确认流测试门店",
        locale="zh-CN",
        timezone="Asia/Shanghai",
        status="active",
        created_at=now,
        updated_at=now,
    )
    access = V2ShopAccess(
        shop_access_id="access_chat_http_confirm",
        tenant_id=tenant.tenant_id,
        shop_id=shop.shop_id,
        membership_id=membership.membership_id,
        access_level="write",
        status="active",
        created_at=now,
    )
    item = V2InventoryItem(
        inventory_item_id="item_chat_http_hammer",
        tenant_id=tenant.tenant_id,
        sku="CHAT-HTTP-HAMMER",
        name="测试锤子",
        barcode=None,
        default_unit="把",
        status="active",
        created_at=now,
        updated_at=now,
    )
    snapshot = V2InventoryStockSnapshot(
        snapshot_id="snap_chat_http_hammer",
        tenant_id=tenant.tenant_id,
        shop_id=shop.shop_id,
        inventory_item_id=item.inventory_item_id,
        current_quantity=current_quantity,
        current_price=Decimal("12.50"),
        low_stock_threshold=Decimal("3"),
        updated_at=now,
    )
    db_session.add_all([account, tenant, membership, shop, access, item, snapshot])
    db_session.commit()
    return tenant.tenant_id, shop.shop_id, account.email, item.inventory_item_id


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


def _approve_confirmation_empty_payload(client, headers: dict[str, str], confirmation_id: str):
    response = client.post(
        f"/api/v2/confirmations/{confirmation_id}/approve",
        headers=headers,
        json={"resolution_payload": {}},
    )
    assert response.status_code == 200
    return response.json()["data"]


def test_http_chat_stock_out_confirmation_can_be_approved_and_commits_inventory(
    client, db_session, monkeypatch
):
    tenant_id, shop_id, email, item_id = _seed_v2_chat_http_context(db_session, current_quantity=Decimal("10"))
    headers = _login_and_select_context(client, email=email, tenant_id=tenant_id, shop_id=shop_id)
    monkeypatch.setattr(
        chat_routes,
        "get_llm_service",
        lambda: _FakeLLMService(_FakeIntent(intent_type="stock_out", item_name="测试锤子", quantity=2)),
    )

    response = client.post(
        "/api/v2/chat",
        headers=headers,
        json={"message": "卖出2把测试锤子"},
    )

    assert response.status_code == 200
    assert response.json()["data"]["intent"] == "stock_out"
    assert "待确认" in response.json()["data"]["reply"]
    confirmation = db_session.scalar(select(V2Confirmation))
    snapshot = db_session.scalar(
        select(V2InventoryStockSnapshot).where(V2InventoryStockSnapshot.inventory_item_id == item_id)
    )
    assert confirmation is not None
    assert confirmation.status == "pending"
    assert confirmation.confirmation_type == "inventory.stock_out"
    assert confirmation.draft_payload["inventory_item_id"] == item_id
    assert confirmation.draft_payload["stock_out_quantity"] == 2
    assert snapshot.current_quantity == Decimal("10.000")
    assert db_session.scalar(select(V2InventoryLedgerEvent)) is None

    approve_payload = _approve_confirmation_empty_payload(client, headers, confirmation.confirmation_id)

    db_session.expire_all()
    ledger_event = db_session.scalar(select(V2InventoryLedgerEvent))
    snapshot = db_session.scalar(
        select(V2InventoryStockSnapshot).where(V2InventoryStockSnapshot.inventory_item_id == item_id)
    )
    assert approve_payload["status"] == "approved"
    assert approve_payload["resolution_payload"]["fields"]["inventory_item_id"] == item_id
    assert approve_payload["resolution_payload"]["fields"]["stock_out_quantity"] == 2
    assert ledger_event is not None
    assert ledger_event.event_type == "stock_out"
    assert ledger_event.quantity_delta == Decimal("-2.000")
    assert snapshot.current_quantity == Decimal("8.000")


def test_http_chat_stock_out_insufficient_inventory_does_not_create_confirmation(
    client, db_session, monkeypatch
):
    tenant_id, shop_id, email, item_id = _seed_v2_chat_http_context(db_session, current_quantity=Decimal("1"))
    headers = _login_and_select_context(client, email=email, tenant_id=tenant_id, shop_id=shop_id)
    monkeypatch.setattr(
        chat_routes,
        "get_llm_service",
        lambda: _FakeLLMService(_FakeIntent(intent_type="stock_out", item_name="测试锤子", quantity=2)),
    )

    response = client.post(
        "/api/v2/chat",
        headers=headers,
        json={"message": "卖出2把测试锤子"},
    )

    snapshot = db_session.scalar(
        select(V2InventoryStockSnapshot).where(V2InventoryStockSnapshot.inventory_item_id == item_id)
    )
    assert response.status_code == 200
    assert "库存不足" in response.json()["data"]["reply"]
    assert db_session.scalar(select(V2Confirmation)) is None
    assert db_session.scalar(select(V2InventoryLedgerEvent)) is None
    assert snapshot.current_quantity == Decimal("1.000")
