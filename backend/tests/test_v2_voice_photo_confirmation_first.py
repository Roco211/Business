from __future__ import annotations

import asyncio
from decimal import Decimal

from sqlalchemy import select

from app.models import (
    V2Account,
    V2Confirmation,
    V2InventoryLedgerEvent,
    V2InventoryStockSnapshot,
    V2Shop,
    V2TaskRun,
    V2Tenant,
)
from app.services import v2_voice
from app.services.v2_photo import process_photo_stock_in
from app.services.v2_time import utc_now_naive
from app.services.v2_voice import IntentParseResult, TranscriptionResult, process_voice_stock_in


def _seed_ai_write_context(db_session) -> tuple[str, str, str]:
    now = utc_now_naive()
    account = V2Account(
        account_id="acct_voice_photo_confirm",
        email="voice-photo-confirm@example.com",
        display_name="Voice Photo Confirm Tester",
        password_hash="hash",
        password_salt="salt",
        status="active",
        created_at=now,
        updated_at=now,
    )
    tenant = V2Tenant(
        tenant_id="tenant_voice_photo_confirm",
        name="语音图片确认流测试租户",
        slug="voice-photo-confirm-tenant",
        status="active",
        plan_code="trial",
        owner_account_id=account.account_id,
        created_at=now,
        updated_at=now,
    )
    shop = V2Shop(
        shop_id="shop_voice_photo_confirm",
        tenant_id=tenant.tenant_id,
        code="MAIN",
        name="语音图片确认流测试门店",
        locale="zh-CN",
        timezone="Asia/Shanghai",
        status="active",
        created_at=now,
        updated_at=now,
    )
    db_session.add_all([account, tenant, shop])
    db_session.commit()
    return tenant.tenant_id, shop.shop_id, account.account_id


async def _collect_events(async_events):
    return [event async for event in async_events]


def test_voice_stock_in_creates_real_pending_confirmation_without_committing_inventory(db_session, monkeypatch):
    tenant_id, shop_id, account_id = _seed_ai_write_context(db_session)

    async def fake_transcribe_audio(audio_data: bytes, mime_type: str) -> TranscriptionResult:
        return TranscriptionResult(text="进货50把螺丝刀", confidence=0.99)

    async def fake_parse_intent(text: str) -> IntentParseResult:
        return IntentParseResult(intent_type="stock_in", item_name="螺丝刀", confidence=0.98)

    monkeypatch.setattr(v2_voice, "transcribe_audio", fake_transcribe_audio)
    monkeypatch.setattr(v2_voice, "parse_intent", fake_parse_intent)

    events = asyncio.run(
        _collect_events(
            process_voice_stock_in(
                db_session,
                tenant_id=tenant_id,
                shop_id=shop_id,
                account_id=account_id,
                audio_data=b"fake-audio",
                mime_type="audio/webm",
            )
        )
    )

    confirmation = db_session.scalar(select(V2Confirmation))
    task_run = db_session.scalar(select(V2TaskRun))
    ledger_event = db_session.scalar(select(V2InventoryLedgerEvent))
    snapshot = db_session.scalar(select(V2InventoryStockSnapshot))
    awaiting_event = next(event for event in events if event.event_type == "awaiting_confirmation")

    assert confirmation is not None
    assert confirmation.status == "pending"
    assert confirmation.confirmation_type == "inventory.stock_in"
    assert confirmation.draft_payload["item_name"] == "螺丝刀"
    assert confirmation.draft_payload["quantity"] == 50
    assert confirmation.draft_payload["unit"] == "把"
    assert task_run is not None
    assert task_run.status == "awaiting_confirmation"
    assert task_run.intent_type == "inventory.stock_in"
    assert awaiting_event.data["confirmation_id"] == confirmation.confirmation_id
    assert ledger_event is None
    assert snapshot is None


def test_photo_stock_in_creates_real_pending_confirmation_without_committing_inventory(db_session):
    tenant_id, shop_id, account_id = _seed_ai_write_context(db_session)

    events = asyncio.run(
        _collect_events(
            process_photo_stock_in(
                db_session,
                tenant_id=tenant_id,
                shop_id=shop_id,
                account_id=account_id,
                image_data=b"fake-receipt-image",
                mime_type="image/jpeg",
            )
        )
    )

    confirmation = db_session.scalar(select(V2Confirmation))
    task_run = db_session.scalar(select(V2TaskRun))
    ledger_event = db_session.scalar(select(V2InventoryLedgerEvent))
    snapshot = db_session.scalar(select(V2InventoryStockSnapshot))
    awaiting_event = next(event for event in events if event.event_type == "awaiting_confirmation")

    assert confirmation is not None
    assert confirmation.status == "pending"
    assert confirmation.confirmation_type == "inventory.stock_in"
    assert confirmation.draft_payload["item_name"]
    assert Decimal(str(confirmation.draft_payload["quantity"])) > 0
    assert confirmation.draft_payload["unit"]
    assert task_run is not None
    assert task_run.status == "awaiting_confirmation"
    assert task_run.intent_type == "inventory.stock_in"
    assert awaiting_event.data["confirmation_id"] == confirmation.confirmation_id
    assert ledger_event is None
    assert snapshot is None
