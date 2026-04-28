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
from app.services import v2_photo, v2_voice
from app.services.ocr_types import OcrExtractedLineItem, OcrExtraction, OcrMediaInput
from app.services.v2_photo import process_photo_stock_in, process_photo_stock_query
from app.services.v2_time import utc_now_naive
from app.services.v2_voice import IntentParseResult, TranscriptionResult, process_voice_stock_in
from app.services.vision_types import VisionCandidate, VisionMediaInput, VisionRecognition
from app.services.asr_types import AsrMediaInput, AsrTranscription


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


def test_voice_transcribe_audio_uses_asr_gateway_not_fixed_stub(monkeypatch):
    called = {"asr": False}

    class FakeAsrGateway:
        def transcribe(self, media_input: AsrMediaInput) -> AsrTranscription:
            called["asr"] = True
            assert media_input.audio_bytes == b"spoken-bytes"
            assert media_input.content_type == "audio/webm"
            return AsrTranscription(text="冲击钻还有几台", provider="fake-real-asr", confidence=0.88)

    monkeypatch.setattr(v2_voice, "get_default_asr_gateway", lambda: FakeAsrGateway(), raising=False)

    result = asyncio.run(v2_voice.transcribe_audio(b"spoken-bytes", "audio/webm"))

    assert called["asr"] is True
    assert result.text == "冲击钻还有几台"
    assert result.confidence == 0.88


def test_voice_stock_in_extracts_items_from_transcribed_text_not_fixed_stub(db_session, monkeypatch):
    tenant_id, shop_id, account_id = _seed_ai_write_context(db_session)

    async def fake_transcribe_audio(audio_data: bytes, mime_type: str) -> TranscriptionResult:
        return TranscriptionResult(text="进货7个膨胀螺丝，单价2元", confidence=0.99)

    async def fake_parse_intent(text: str) -> IntentParseResult:
        return IntentParseResult(intent_type="stock_in", item_name="膨胀螺丝", confidence=0.98)

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

    extraction_event = next(event for event in events if event.event_type == "extraction")
    confirmation = db_session.scalar(select(V2Confirmation))

    assert extraction_event.data["items"] == [
        {"name": "膨胀螺丝", "quantity": 7.0, "unit": "个", "price": 2.0}
    ]
    assert extraction_event.data["supplier"] is None
    assert confirmation is not None
    assert confirmation.draft_payload["item_name"] == "膨胀螺丝"
    assert confirmation.draft_payload["quantity"] == 7.0
    assert "扳手" not in str([event.data for event in events])


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


def test_photo_stock_query_uses_vision_gateway_not_fixed_stub(db_session, monkeypatch):
    tenant_id, shop_id, _account_id = _seed_ai_write_context(db_session)
    called = {"vision": False}

    class FakeVisionGateway:
        def recognize_product(self, media_input: VisionMediaInput) -> VisionRecognition:
            called["vision"] = True
            assert media_input.image_bytes == b"real-image-bytes"
            return VisionRecognition(
                provider_name="fake-real-vision",
                candidates=[VisionCandidate(item_name="冲击钻", confidence=0.93, packaging_hint="工具")],
                used_fallback=False,
                raw_payload={"source": "test"},
            )

    monkeypatch.setattr(v2_photo, "get_default_vision_gateway", lambda: FakeVisionGateway(), raising=False)

    events = asyncio.run(
        _collect_events(
            process_photo_stock_query(
                db_session,
                tenant_id=tenant_id,
                shop_id=shop_id,
                image_data=b"real-image-bytes",
                mime_type="image/jpeg",
            )
        )
    )

    extraction_event = next(event for event in events if event.event_type == "extraction")
    assert called["vision"] is True
    assert extraction_event.data["provider"] == "fake-real-vision"
    assert extraction_event.data["cleaned_text"] == "冲击钻"
    assert "螺丝刀 十字 JIS标准" not in str([event.data for event in events])


def test_photo_stock_in_uses_ocr_gateway_not_receipt_stub(db_session, monkeypatch):
    tenant_id, shop_id, account_id = _seed_ai_write_context(db_session)
    called = {"ocr": False}

    class FakeOcrGateway:
        def extract_purchase_receipt(self, media_input: OcrMediaInput) -> OcrExtraction:
            called["ocr"] = True
            assert media_input.image_bytes == b"receipt-bytes"
            return OcrExtraction(
                document_type="purchase_receipt",
                provider_name="fake-real-ocr",
                raw_text="冲击钻 3 台 120 元",
                line_items=[OcrExtractedLineItem(item_name="冲击钻", quantity=3, unit="台", price=120.0)],
                total_amount=360.0,
                low_confidence_fields=[],
                used_fallback=False,
                raw_payload={"supplier": "真实供应商"},
            )

    monkeypatch.setattr(v2_photo, "get_default_ocr_gateway", lambda: FakeOcrGateway(), raising=False)

    events = asyncio.run(
        _collect_events(
            process_photo_stock_in(
                db_session,
                tenant_id=tenant_id,
                shop_id=shop_id,
                account_id=account_id,
                image_data=b"receipt-bytes",
                mime_type="image/jpeg",
            )
        )
    )

    confirmation = db_session.scalar(select(V2Confirmation))
    extraction_event = next(event for event in events if event.event_type == "extraction")

    assert called["ocr"] is True
    assert extraction_event.data["provider"] == "fake-real-ocr"
    assert confirmation is not None
    assert confirmation.draft_payload["item_name"] == "冲击钻"
    assert confirmation.draft_payload["quantity"] == 3
    assert confirmation.draft_payload["supplier"] == "真实供应商"
    assert "测试供应商" not in str([event.data for event in events])
