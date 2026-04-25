from __future__ import annotations

import json
from decimal import Decimal

from sqlalchemy import select

from app.models import (
    V2Account,
    V2Confirmation,
    V2InventoryLedgerEvent,
    V2InventoryStockSnapshot,
    V2Shop,
    V2ShopAccess,
    V2Tenant,
    V2TenantMembership,
)
from app.services import v2_voice
from app.services.v2_identity import hash_v2_password
from app.services.v2_time import utc_now_naive
from app.services.v2_voice import IntentParseResult, TranscriptionResult


def _seed_v2_http_ai_context(db_session) -> tuple[str, str, str]:
    now = utc_now_naive()
    password_salt = "33" * 16
    account = V2Account(
        account_id="acct_http_ai_confirm",
        email="http-ai-confirm@example.com",
        display_name="HTTP AI Confirm Tester",
        password_hash=hash_v2_password("dev-password", password_salt),
        password_salt=password_salt,
        status="active",
        created_at=now,
        updated_at=now,
    )
    tenant = V2Tenant(
        tenant_id="tenant_http_ai_confirm",
        name="HTTP AI 确认流测试租户",
        slug="http-ai-confirm-tenant",
        status="active",
        plan_code="trial",
        owner_account_id=account.account_id,
        created_at=now,
        updated_at=now,
    )
    membership = V2TenantMembership(
        membership_id="mship_http_ai_confirm",
        tenant_id=tenant.tenant_id,
        account_id=account.account_id,
        role_key="owner",
        status="active",
        joined_at=now,
        updated_at=now,
    )
    shop = V2Shop(
        shop_id="shop_http_ai_confirm",
        tenant_id=tenant.tenant_id,
        code="HTTP-AI",
        name="HTTP AI 确认流测试门店",
        locale="zh-CN",
        timezone="Asia/Shanghai",
        status="active",
        created_at=now,
        updated_at=now,
    )
    access = V2ShopAccess(
        shop_access_id="access_http_ai_confirm",
        tenant_id=tenant.tenant_id,
        shop_id=shop.shop_id,
        membership_id=membership.membership_id,
        access_level="write",
        status="active",
        created_at=now,
    )
    db_session.add_all([account, tenant, membership, shop, access])
    db_session.commit()
    return tenant.tenant_id, shop.shop_id, account.email


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


def _parse_sse_events(response_text: str) -> list[dict[str, object]]:
    events: list[dict[str, object]] = []
    for block in response_text.strip().split("\n\n"):
        if not block.strip():
            continue
        event_type = None
        data: dict[str, object] = {}
        for line in block.splitlines():
            if line.startswith("event: "):
                event_type = line.removeprefix("event: ").strip()
            elif line.startswith("data: "):
                data = json.loads(line.removeprefix("data: "))
        if event_type is not None:
            events.append({"event": event_type, "data": data})
    return events


def _approve_confirmation_empty_payload(client, headers: dict[str, str], confirmation_id: str):
    response = client.post(
        f"/api/v2/confirmations/{confirmation_id}/approve",
        headers=headers,
        json={"resolution_payload": {}},
    )
    assert response.status_code == 200
    return response.json()["data"]


def test_http_voice_stock_in_sse_confirmation_can_be_approved_and_commits_inventory(
    client, db_session, monkeypatch
):
    tenant_id, shop_id, email = _seed_v2_http_ai_context(db_session)
    headers = _login_and_select_context(client, email=email, tenant_id=tenant_id, shop_id=shop_id)

    async def fake_transcribe_audio(audio_data: bytes, mime_type: str) -> TranscriptionResult:
        return TranscriptionResult(text="进货50把螺丝刀", confidence=0.99)

    async def fake_parse_intent(text: str) -> IntentParseResult:
        return IntentParseResult(intent_type="stock_in", item_name="螺丝刀", confidence=0.98)

    monkeypatch.setattr(v2_voice, "transcribe_audio", fake_transcribe_audio)
    monkeypatch.setattr(v2_voice, "parse_intent", fake_parse_intent)

    response = client.post(
        "/api/v2/voice/stock-in",
        headers=headers,
        data={"shop_id": shop_id},
        files={"audio": ("stock-in.webm", b"fake-audio", "audio/webm")},
    )

    assert response.status_code == 200
    events = _parse_sse_events(response.text)
    awaiting = next(event for event in events if event["event"] == "awaiting_confirmation")
    confirmation_id = awaiting["data"]["confirmation_id"]
    task_run_id = awaiting["data"]["task_run_id"]

    confirmation = db_session.scalar(
        select(V2Confirmation).where(V2Confirmation.confirmation_id == confirmation_id)
    )
    assert confirmation is not None
    assert confirmation.status == "pending"
    assert confirmation.task_run_id == task_run_id
    assert confirmation.draft_payload["item_name"] == "螺丝刀"
    assert db_session.scalar(select(V2InventoryLedgerEvent)) is None
    assert db_session.scalar(select(V2InventoryStockSnapshot)) is None

    approve_payload = _approve_confirmation_empty_payload(client, headers, confirmation_id)

    db_session.expire_all()
    ledger_event = db_session.scalar(select(V2InventoryLedgerEvent))
    snapshot = db_session.scalar(select(V2InventoryStockSnapshot))
    assert approve_payload["status"] == "approved"
    assert approve_payload["resolution_payload"]["fields"]["item_name"] == "螺丝刀"
    assert ledger_event is not None
    assert ledger_event.event_type == "stock_in"
    assert ledger_event.quantity_delta == Decimal("50.000")
    assert snapshot is not None
    assert snapshot.current_quantity == Decimal("50.000")


def test_http_photo_stock_in_sse_confirmation_can_be_approved_and_commits_inventory(client, db_session):
    tenant_id, shop_id, email = _seed_v2_http_ai_context(db_session)
    headers = _login_and_select_context(client, email=email, tenant_id=tenant_id, shop_id=shop_id)

    response = client.post(
        "/api/v2/photo/stock-in",
        headers=headers,
        data={"shop_id": shop_id},
        files={"image": ("receipt.jpg", b"fake-receipt-image", "image/jpeg")},
    )

    assert response.status_code == 200
    events = _parse_sse_events(response.text)
    awaiting = next(event for event in events if event["event"] == "awaiting_confirmation")
    confirmation_id = awaiting["data"]["confirmation_id"]
    task_run_id = awaiting["data"]["task_run_id"]

    confirmation = db_session.scalar(
        select(V2Confirmation).where(V2Confirmation.confirmation_id == confirmation_id)
    )
    assert confirmation is not None
    assert confirmation.status == "pending"
    assert confirmation.task_run_id == task_run_id
    assert confirmation.draft_payload["item_name"]
    assert Decimal(str(confirmation.draft_payload["quantity"])) > 0
    assert db_session.scalar(select(V2InventoryLedgerEvent)) is None
    assert db_session.scalar(select(V2InventoryStockSnapshot)) is None

    approve_payload = _approve_confirmation_empty_payload(client, headers, confirmation_id)

    db_session.expire_all()
    ledger_event = db_session.scalar(select(V2InventoryLedgerEvent))
    snapshot = db_session.scalar(select(V2InventoryStockSnapshot))
    assert approve_payload["status"] == "approved"
    assert approve_payload["resolution_payload"]["fields"]["item_name"] == confirmation.draft_payload["item_name"]
    assert ledger_event is not None
    assert ledger_event.event_type == "stock_in"
    assert ledger_event.quantity_delta == Decimal(str(confirmation.draft_payload["quantity"])).quantize(Decimal("0.001"))
    assert snapshot is not None
    assert snapshot.current_quantity == ledger_event.quantity_after
