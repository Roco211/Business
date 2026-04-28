"""Voice service layer for audio processing, ASR, NLP intent parsing, and SSE streaming."""

from collections.abc import AsyncIterator
from dataclasses import dataclass
import json
import re
from typing import Any

from sqlalchemy.orm import Session

from app.services.v2_ai_confirmation import create_v2_ai_stock_in_confirmation
from app.services.asr_gateway import get_default_asr_gateway
from app.services.asr_types import AsrMediaInput, AsrProviderError
from app.services.v2_inventory import list_v2_inventory_items
from app.services.v2_llm import (
    LLMService,
    ParsedIntent,
    get_llm_service,
    parse_stock_query_intent as llm_parse_intent,
)
from app.services.v2_voice_query import (
    StockQueryIntent,
    parse_stock_query_intent,
    query_inventory_stock,
)


class VoiceASRError(ValueError):
    """Raised when ASR transcription fails."""

    pass


class VoiceIntentParseError(ValueError):
    """Raised when intent parsing fails."""

    pass


class VoiceInventoryQueryError(ValueError):
    """Raised when inventory query fails."""

    pass


@dataclass(frozen=True)
class TranscriptionResult:
    """Result of ASR transcription."""

    text: str
    confidence: float


@dataclass(frozen=True)
class IntentParseResult:
    """Result of NLP intent parsing."""

    intent_type: str
    item_name: str | None
    confidence: float


@dataclass(frozen=True)
class InventoryQueryResult:
    """Result of inventory query."""

    item_id: str | None
    item_name: str | None
    quantity: float | None
    unit: str | None
    found: bool


@dataclass(frozen=True)
class VoiceQueryEvent:
    """SSE event for voice query stream.

    event_type: "transcription" | "intent" | "result" | "complete" | "error"
    data: JSON-serializable data for the event
    """

    event_type: str
    data: dict[str, Any]


def _build_sse_event(event_type: str, data: dict[str, Any]) -> str:
    """Build SSE formatted event string."""
    return f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


async def transcribe_audio(
    audio_data: bytes,
    mime_type: str,
) -> TranscriptionResult:
    """Transcribe uploaded audio through the configured ASR gateway.

    Production defaults to client ASR, so calling this old server-audio path will
    fail closed unless an explicit real server ASR provider is configured.
    """
    if not audio_data:
        raise VoiceASRError("Empty audio data")

    if mime_type not in {"audio/webm", "audio/wav", "audio/mp3", "audio/mpeg", "audio/ogg"}:
        raise VoiceASRError(f"Unsupported mime type: {mime_type}")

    try:
        transcription = get_default_asr_gateway().transcribe(
            AsrMediaInput(
                media_ids=["inline-voice-upload"],
                content_type=mime_type,
                audio_bytes=audio_data,
            )
        )
    except AsrProviderError as exc:
        raise VoiceASRError(exc.message) from exc

    if not transcription.text.strip():
        raise VoiceASRError("ASR returned empty transcription")

    return TranscriptionResult(
        text=transcription.text,
        confidence=transcription.confidence if transcription.confidence is not None else 0.0,
    )


async def parse_intent(text: str) -> IntentParseResult:
    """NLP intent parser using Volcano LLM with rule-based fallback.
    
    Uses the LLM service for intent recognition with automatic fallback
    to rule-based parsing if LLM unavailable.
    
    Args:
        text: Transcribed text from ASR
        
    Returns:
        IntentParseResult with intent type, item name, and confidence
        
    Raises:
        VoiceIntentParseError: If intent parsing fails
    """
    if not text or not text.strip():
        raise VoiceIntentParseError("Empty text input")
    
    # Use LLM service for intent parsing
    parsed = llm_parse_intent(text)
    return IntentParseResult(
        intent_type=parsed.intent_type,
        item_name=parsed.item_name,
        confidence=parsed.confidence,
    )


async def query_stock(
    db_session: Session,
    *,
    tenant_id: str,
    shop_id: str,
    item_name: str | None,
) -> InventoryQueryResult:
    """Query inventory stock for given item name.

    Args:
        db_session: Database session
        tenant_id: Tenant ID for multi-tenant isolation
        shop_id: Shop ID for shop-level stock lookup
        item_name: Item name to query (optional)

    Returns:
        InventoryQueryResult with stock information

    Raises:
        VoiceInventoryQueryError: If query fails
    """
    result = query_inventory_stock(
        db_session,
        tenant_id=tenant_id,
        shop_id=shop_id,
        item_name=item_name,
    )
    return InventoryQueryResult(
        item_id=result.item_id,
        item_name=result.item_name,
        quantity=float(result.quantity) if result.quantity is not None else None,
        unit=result.unit,
        found=result.found,
    )


async def process_voice_stock_query(
    db_session: Session,
    *,
    tenant_id: str,
    shop_id: str,
    audio_data: bytes,
    mime_type: str,
) -> AsyncIterator[VoiceQueryEvent]:
    """Process voice stock query end-to-end.

    Flow:
        1. ASR 转录音频 -> 文本
        2. NLP 解析意图 -> 查询参数
        3. 查询库存快照
        4. 流式返回结果

    Args:
        db_session: Database session
        tenant_id: Tenant ID for multi-tenant isolation
        shop_id: Shop ID for shop-level stock lookup
        audio_data: Binary audio data
        mime_type: Mime type of audio data

    Yields:
        VoiceQueryEvent for SSE streaming:
        - event: transcription, data: {"text": "..."}
        - event: intent, data: {"intent": "stock_query", "item_name": "..."}
        - event: result, data: {"item": {...}, "stock": {"quantity": 45}}
        - event: complete, data: {}

    Raises:
        VoiceASRError: If ASR transcription fails
        VoiceIntentParseError: If intent parsing fails
        VoiceInventoryQueryError: If inventory query fails
    """
    try:
        # Step 1: ASR transcription
        transcription = await transcribe_audio(audio_data, mime_type)
        yield VoiceQueryEvent(
            event_type="transcription",
            data={
                "text": transcription.text,
                "confidence": transcription.confidence,
            },
        )

        # Step 2: Parse intent
        intent_result = await parse_intent(transcription.text)
        yield VoiceQueryEvent(
            event_type="intent",
            data={
                "intent": intent_result.intent_type,
                "item_name": intent_result.item_name,
                "confidence": intent_result.confidence,
            },
        )

        if intent_result.intent_type != "stock_query":
            yield VoiceQueryEvent(
                event_type="error",
                data={
                    "error": "unsupported_intent",
                    "message": f"Intent '{intent_result.intent_type}' is not supported for stock query",
                },
            )
            return

        # Step 3: Query inventory
        inventory_result = await query_stock(
            db_session,
            tenant_id=tenant_id,
            shop_id=shop_id,
            item_name=intent_result.item_name,
        )

        # Step 4: Return result
        yield VoiceQueryEvent(
            event_type="result",
            data={
                "item": {
                    "item_id": inventory_result.item_id,
                    "item_name": inventory_result.item_name,
                } if inventory_result.found else None,
                "stock": {
                    "quantity": float(inventory_result.quantity) if inventory_result.quantity is not None else None,
                    "unit": inventory_result.unit,
                } if inventory_result.found else None,
                "found": inventory_result.found,
            },
        )

        # Step 5: Complete
        yield VoiceQueryEvent(
            event_type="complete",
            data={},
        )

    except VoiceASRError as exc:
        yield VoiceQueryEvent(
            event_type="error",
            data={
                "error": "asr_failed",
                "message": str(exc),
            },
        )
    except VoiceIntentParseError as exc:
        yield VoiceQueryEvent(
            event_type="error",
            data={
                "error": "intent_parse_failed",
                "message": str(exc),
            },
        )
    except VoiceInventoryQueryError as exc:
        yield VoiceQueryEvent(
            event_type="error",
            data={
                "error": "inventory_query_failed",
                "message": str(exc),
            },
        )
    except Exception as exc:
        yield VoiceQueryEvent(
            event_type="error",
            data={
                "error": "unknown_error",
                "message": str(exc),
            },
        )


def events_to_sse_stream(events: list[VoiceQueryEvent]) -> str:
    """Convert list of VoiceQueryEvents to SSE stream string.

    Args:
        events: List of events to stream

    Returns:
        SSE formatted string ready for StreamingResponse
    """
    return "".join(
        _build_sse_event(evt.event_type, evt.data)
        for evt in events
    )


async def process_voice_stock_in(
    db_session: Session,
    *,
    tenant_id: str,
    shop_id: str,
    account_id: str,
    audio_data: bytes,
    mime_type: str,
) -> AsyncIterator[VoiceQueryEvent]:
    """Process voice stock in (receipt/intent).

    Flow:
    1. ASR transcribe audio
    2. Parse intent (stock_in)
    3. Extract items/supplier
    4. Create draft
    5. Stream results
    """
    try:
        # Step 1: ASR
        yield VoiceQueryEvent(
            event_type="processing",
            data={"stage": "asr", "message": "正在识别语音..."},
        )
        
        transcription = await transcribe_audio(audio_data, mime_type)
        
        yield VoiceQueryEvent(
            event_type="transcription",
            data={"text": transcription.text, "confidence": transcription.confidence},
        )

        # Step 2: Parse intent
        yield VoiceQueryEvent(
            event_type="processing",
            data={"stage": "intent_parsing", "message": "正在理解意图..."},
        )
        
        intent_result = await parse_intent(transcription.text)
        
        yield VoiceQueryEvent(
            event_type="intent",
            data={
                "intent": intent_result.intent_type,
                "item_name": intent_result.item_name,
                "confidence": intent_result.confidence,
            },
        )

        if intent_result.intent_type != "stock_in":
            yield VoiceQueryEvent(
                event_type="error",
                data={
                    "error": "unsupported_intent",
                    "message": f"Intent '{intent_result.intent_type}' is not stock_in",
                },
            )
            return

        # Step 3: Extract stock-in items from the transcribed text.
        yield VoiceQueryEvent(
            event_type="processing",
            data={"stage": "extraction", "message": "正在提取商品信息..."},
        )

        items = _extract_stock_in_items_from_text(
            transcription.text,
            item_name=intent_result.item_name,
        )
        if not items:
            yield VoiceQueryEvent(
                event_type="error",
                data={"error": "no_items_found", "message": "未能从语音文字中识别出入库商品"},
            )
            return
        supplier = _extract_supplier_from_text(transcription.text)

        yield VoiceQueryEvent(
            event_type="extraction",
            data={"items": items, "supplier": supplier, "found_count": len(items)},
        )

        # Step 4: Create a real pending confirmation. AI-derived stock-in writes
        # must not mutate inventory until the confirmation is approved.
        first_item = items[0]
        draft_payload = {
            "item_name": first_item["name"],
            "quantity": first_item["quantity"],
            "unit": first_item["unit"],
            "price": first_item["price"],
            "supplier": supplier,
        }
        created_confirmation = create_v2_ai_stock_in_confirmation(
            db_session,
            tenant_id=tenant_id,
            shop_id=shop_id,
            account_id=account_id,
            source_type="voice",
            source_text=transcription.text,
            draft_payload=draft_payload,
        )
        confirmation_id = created_confirmation.confirmation.confirmation_id
        task_run_id = created_confirmation.task_run.task_run_id
        
        yield VoiceQueryEvent(
            event_type="draft_created",
            data={
                "draft_id": confirmation_id,
                "confirmation_id": confirmation_id,
                "task_run_id": task_run_id,
                "item_count": len(items),
            },
        )

        # Step 5: Await confirmation
        yield VoiceQueryEvent(
            event_type="awaiting_confirmation",
            data={
                "message": "请确认入库信息",
                "confirmation_id": confirmation_id,
                "task_run_id": task_run_id,
            },
        )
        
        yield VoiceQueryEvent(
            event_type="complete",
            data={
                "draft_id": confirmation_id,
                "confirmation_id": confirmation_id,
                "task_run_id": task_run_id,
                "status": "awaiting_confirmation",
            },
        )

    except VoiceASRError as exc:
        yield VoiceQueryEvent(
            event_type="error",
            data={"error": "asr_failed", "message": str(exc)},
        )
    except Exception as exc:
        yield VoiceQueryEvent(
            event_type="error",
            data={"error": "processing_failed", "message": str(exc)},
        )


def _extract_stock_in_items_from_text(text: str, *, item_name: str | None) -> list[dict[str, float | str]]:
    normalized_text = text.strip()
    normalized_item_name = item_name.strip() if isinstance(item_name, str) and item_name.strip() else ""
    if not normalized_text or not normalized_item_name:
        return []

    quantity = _extract_number_before_unit(normalized_text, default=1.0)
    unit = _extract_unit(normalized_text) or "件"
    price = _extract_price(normalized_text)
    return [
        {
            "name": normalized_item_name,
            "quantity": quantity,
            "unit": unit,
            "price": price,
        }
    ]


def _extract_number_before_unit(text: str, *, default: float) -> float:
    match = re.search(r"(\d+(?:\.\d+)?)\s*(把|个|件|箱|瓶|袋|盒|套|双|副|台|支|米|公斤|kg|KG)", text)
    if not match:
        return default
    return float(match.group(1))


def _extract_unit(text: str) -> str | None:
    match = re.search(r"\d+(?:\.\d+)?\s*(把|个|件|箱|瓶|袋|盒|套|双|副|台|支|米|公斤|kg|KG)", text)
    if not match:
        return None
    unit = match.group(1)
    return "公斤" if unit.lower() == "kg" else unit


def _extract_price(text: str) -> float:
    match = re.search(r"(?:单价|价格|每(?:个|件|台|把)?|￥|¥)\s*(\d+(?:\.\d+)?)\s*(?:元|块)?", text)
    if not match:
        return 0.0
    return float(match.group(1))


def _extract_supplier_from_text(text: str) -> str | None:
    match = re.search(r"(?:供应商|从)\s*([\u4e00-\u9fa5A-Za-z0-9_-]{2,24})", text)
    if not match:
        return None
    supplier = match.group(1).strip("，,。；;：:")
    return supplier or None
