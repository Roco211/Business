import string

from app.services.mock_multimodal import classify_image_task, extract_receipt, recognize_image
from .tools import MockTranscriptionUnavailable, transcribe_audio_input
from .types import RuntimeMediaRef, RuntimeRouteBlocked, RuntimeRouteDecision, RuntimeTurnContext

PUNCTUATION_TO_SPACE = str.maketrans({char: " " for char in string.punctuation})
STOCK_IN_PHRASES = ("restock", "stock in")
STOCK_OUT_PHRASES = ("stock out",)
STOCK_OUT_WORDS = ("sold", "remove")
QUERY_WORDS = ("check", "left", "remaining")
QUERY_PHRASES = ("how many",)


def _normalize_transcript(transcript: str) -> str:
    return transcript.lower().translate(PUNCTUATION_TO_SPACE)


def _tokens(transcript: str) -> list[str]:
    return [token for token in _normalize_transcript(transcript).split() if token]


def _contains_phrase(transcript: str, phrase: str) -> bool:
    return phrase in _normalize_transcript(transcript)


def _classify_transcript(transcript: str) -> str:
    normalized = _normalize_transcript(transcript)
    tokens = _tokens(transcript)
    if any(phrase in normalized for phrase in STOCK_OUT_PHRASES):
        return "voice-stock-out"
    if any(word in tokens for word in STOCK_OUT_WORDS):
        return "voice-stock-out"
    if any(phrase in normalized for phrase in STOCK_IN_PHRASES):
        return "voice-stock-in"
    if any(_contains_phrase(transcript, phrase) for phrase in QUERY_PHRASES):
        return "voice-stock-query"
    if any(word in tokens for word in QUERY_WORDS):
        return "voice-stock-query"
    return "voice-stock-in"


def _text_or_none(value: str | None) -> str:
    return value or ""


def _select_audio_media_refs(ctx: RuntimeTurnContext) -> list[RuntimeMediaRef]:
    return [media_ref for media_ref in ctx.media_refs if media_ref.media_type == "audio"]


def transcribe_runtime_audio(ctx: RuntimeTurnContext) -> str:
    audio_media_refs = _select_audio_media_refs(ctx)
    if not audio_media_refs:
        raise RuntimeRouteBlocked(
            "runtime_processing_error",
            "Transcription failed: no ready audio media available",
        )

    try:
        transcription = transcribe_audio_input(
            media_ids=[media_ref.media_id for media_ref in audio_media_refs],
            media_urls=[media_ref.public_url for media_ref in audio_media_refs],
            text_hint=ctx.source_text,
        )
    except MockTranscriptionUnavailable as exc:
        raise RuntimeRouteBlocked(
            "runtime_processing_error",
            f"Transcription failed: {exc}",
        ) from exc

    confidence = transcription.confidence
    low_confidence_threshold = ctx.shop_rules.get("low_confidence_threshold")
    if (
        confidence is not None
        and isinstance(low_confidence_threshold, (int, float))
        and confidence < float(low_confidence_threshold)
    ):
        raise RuntimeRouteBlocked(
            "asr_low_confidence",
            f"ASR confidence {confidence:.2f} is below threshold {float(low_confidence_threshold):.2f}",
        )

    return transcription.text


def route_runtime_input(ctx: RuntimeTurnContext) -> RuntimeRouteDecision:
    if ctx.input_kind == "text":
        text = _text_or_none(ctx.source_text).strip()
        if not text:
            raise RuntimeRouteBlocked("runtime_processing_error", "Text message is empty")
        return RuntimeRouteDecision(
            task_type=_classify_transcript(text),
            assigned_employee_id="xiaoya",
            transcript=text,
        )
    if ctx.input_kind == "voice":
        transcript = transcribe_runtime_audio(ctx)
        return RuntimeRouteDecision(
            task_type=_classify_transcript(transcript),
            assigned_employee_id="xiaoya",
            transcript=transcript,
        )
    if ctx.input_kind == "image":
        recognition = recognize_image(media_ids=ctx.media_ids, text_hint=ctx.source_text)
        task_type = classify_image_task(media_ids=ctx.media_ids, text_hint=ctx.source_text)
        return RuntimeRouteDecision(
            task_type=task_type,
            assigned_employee_id="xiaoya",
            transcript=(ctx.source_text or recognition.item_name).strip(),
            payload={
                "item_name": recognition.item_name,
                "confidence": recognition.confidence,
                "quantity": recognition.quantity,
                "unit": recognition.unit,
                "price": recognition.price,
                "image_media_id": ctx.media_ids[0] if ctx.media_ids else None,
            },
        )
    if ctx.input_kind == "receipt-image":
        receipt = extract_receipt(media_ids=ctx.media_ids, text_hint=ctx.source_text)
        return RuntimeRouteDecision(
            task_type="receipt-ocr",
            assigned_employee_id="xiaoya",
            transcript=ctx.source_text,
            payload={
                "document_type": receipt.document_type,
                "provider_name": receipt.provider_name,
                "fields": receipt.extracted_fields,
                "low_confidence_fields": list(receipt.low_confidence_fields),
            },
        )
    raise RuntimeRouteBlocked("runtime_processing_error", "Unsupported input kind")
