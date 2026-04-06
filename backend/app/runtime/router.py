import string

from app.core.config import get_settings
from app.runtime.guardrails import image_route_trial_violation
from app.services.asr_types import AsrTranscription
from app.services.vision_gateway import get_default_vision_gateway
from app.services.vision_types import VisionMediaInput, VisionProviderError
from .tools import MockTranscriptionUnavailable, transcribe_audio_input
from .types import RuntimeMediaRef, RuntimeRouteBlocked, RuntimeRouteDecision, RuntimeTurnContext

PUNCTUATION_TO_SPACE = str.maketrans({char: " " for char in string.punctuation})
STOCK_IN_PHRASES = ("restock", "stock in")
STOCK_OUT_PHRASES = ("stock out",)
STOCK_OUT_WORDS = ("sold", "remove")
QUERY_WORDS = ("check", "left", "remaining")
QUERY_PHRASES = ("how many",)


class RuntimeProviderTelemetryBlocked(RuntimeRouteBlocked):
    def __init__(self, error_code: str, error_message: str, *, telemetry: dict[str, object]):
        super().__init__(error_code, error_message)
        self.telemetry = telemetry


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


def _normalized_provider_mode(provider_name: str | None) -> str:
    normalized = (provider_name or "").strip().lower()
    return normalized or "mock"


def _select_audio_media_refs(ctx: RuntimeTurnContext) -> list[RuntimeMediaRef]:
    return [media_ref for media_ref in ctx.media_refs if media_ref.media_type == "audio"]


def _select_image_media_ref(ctx: RuntimeTurnContext) -> RuntimeMediaRef:
    image_media_refs = [media_ref for media_ref in ctx.media_refs if media_ref.media_type == "image"]
    if not image_media_refs:
        raise RuntimeRouteBlocked(
            "runtime_processing_error",
            "Image recognition failed: no ready image media available",
        )
    return image_media_refs[0]


def _build_voice_provider_telemetry(
    ctx: RuntimeTurnContext,
    transcription: AsrTranscription,
    *,
    task_type: str | None,
) -> dict[str, object]:
    settings = get_settings()
    provider_mode = _normalized_provider_mode(settings.asr_provider)
    provider_label = settings.asr_provider_label.strip() or transcription.provider
    confidence = transcription.confidence
    low_confidence_threshold = ctx.shop_rules.get("low_confidence_threshold")
    low_confidence = (
        confidence is not None
        and isinstance(low_confidence_threshold, (int, float))
        and confidence < float(low_confidence_threshold)
    )
    return {
        "task_type": task_type,
        "capability": "asr",
        "provider_mode": provider_mode,
        "provider_label": provider_label,
        "used_fallback": provider_mode != "mock" and transcription.provider.strip().lower() == "mock",
        "recognized_confidence": confidence,
        "low_confidence": low_confidence,
    }


def _classify_photo_task_type(source_text: str | None) -> tuple[str, str]:
    transcript = (source_text or "").strip()
    transcript_intent = _classify_transcript(transcript) if transcript else "voice-stock-in"
    task_type = "photo-stock-query" if transcript_intent == "voice-stock-query" else "photo-stock-in"
    return transcript, task_type


def _build_image_provider_telemetry(
    ctx: RuntimeTurnContext,
    *,
    provider_name: str,
    used_fallback: bool,
    recognized_confidence: float | None,
    task_type: str,
) -> dict[str, object]:
    settings = get_settings()
    provider_mode = _normalized_provider_mode(settings.vision_provider)
    provider_label = settings.vision_provider_label.strip() or provider_name
    low_confidence_threshold = ctx.shop_rules.get("low_confidence_threshold")
    low_confidence = (
        recognized_confidence is not None
        and isinstance(low_confidence_threshold, (int, float))
        and recognized_confidence < float(low_confidence_threshold)
    )
    return {
        "task_type": task_type,
        "capability": "vision",
        "provider_mode": provider_mode,
        "provider_label": provider_label,
        "used_fallback": used_fallback,
        "recognized_confidence": recognized_confidence,
        "low_confidence": low_confidence,
    }


def _transcribe_runtime_audio_result(ctx: RuntimeTurnContext) -> AsrTranscription:
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
        settings = get_settings()
        raise RuntimeProviderTelemetryBlocked(
            "runtime_processing_error",
            f"Transcription failed: {exc}",
            telemetry={
                "task_type": None,
                "capability": "asr",
                "provider_mode": _normalized_provider_mode(settings.asr_provider),
                "provider_label": settings.asr_provider_label.strip()
                or _normalized_provider_mode(settings.asr_provider),
                "used_fallback": False,
                "recognized_confidence": None,
                "low_confidence": False,
            },
        ) from exc

    telemetry = _build_voice_provider_telemetry(
        ctx,
        transcription,
        task_type=_classify_transcript(transcription.text),
    )
    if bool(telemetry["low_confidence"]):
        raise RuntimeProviderTelemetryBlocked(
            "asr_low_confidence",
            "ASR confidence "
            f"{float(telemetry['recognized_confidence']):.2f} is below threshold "
            f"{float(ctx.shop_rules.get('low_confidence_threshold')):.2f}",
            telemetry=telemetry,
        )

    return transcription


def transcribe_runtime_audio(ctx: RuntimeTurnContext) -> str:
    return _transcribe_runtime_audio_result(ctx).text


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
        transcription = _transcribe_runtime_audio_result(ctx)
        transcript = transcription.text
        task_type = _classify_transcript(transcript)
        return RuntimeRouteDecision(
            task_type=task_type,
            assigned_employee_id="xiaoya",
            transcript=transcript,
            payload=_build_voice_provider_telemetry(
                ctx,
                transcription,
                task_type=task_type,
            ),
        )
    if ctx.input_kind == "image":
        media_ref = _select_image_media_ref(ctx)
        transcript, task_type = _classify_photo_task_type(ctx.source_text)
        try:
            recognition = get_default_vision_gateway().recognize_product(
                VisionMediaInput(
                    media_id=media_ref.media_id,
                    public_url=media_ref.public_url,
                    content_type=media_ref.content_type,
                    file_name=media_ref.file_name,
                )
            )
        except VisionProviderError as exc:
            raise RuntimeProviderTelemetryBlocked(
                exc.code,
                f"Image recognition failed: {exc.message}",
                telemetry=_build_image_provider_telemetry(
                    ctx,
                    provider_name=_normalized_provider_mode(get_settings().vision_provider),
                    used_fallback=False,
                    recognized_confidence=None,
                    task_type=task_type,
                ),
            ) from exc
        if not recognition.candidates:
            raise RuntimeProviderTelemetryBlocked(
                "runtime_processing_error",
                "Image recognition failed: no candidates returned",
                telemetry=_build_image_provider_telemetry(
                    ctx,
                    provider_name=recognition.provider_name,
                    used_fallback=recognition.used_fallback,
                    recognized_confidence=None,
                    task_type=task_type,
                ),
            )

        top_candidate = max(recognition.candidates, key=lambda candidate: candidate.confidence)
        telemetry = _build_image_provider_telemetry(
            ctx,
            provider_name=recognition.provider_name,
            used_fallback=recognition.used_fallback,
            recognized_confidence=top_candidate.confidence,
            task_type=task_type,
        )
        trial_violation = image_route_trial_violation(
            settings=get_settings(),
            used_fallback=recognition.used_fallback,
            confidence=top_candidate.confidence,
            low_confidence_threshold=ctx.shop_rules.get("low_confidence_threshold"),
        )
        if trial_violation is not None:
            raise RuntimeProviderTelemetryBlocked(
                "runtime_processing_error",
                f"Image recognition blocked: {trial_violation}",
                telemetry=telemetry,
            )

        transcript = (ctx.source_text or top_candidate.item_name).strip()
        transcript_intent = _classify_transcript(transcript) if transcript else "voice-stock-in"
        task_type = "photo-stock-query" if transcript_intent == "voice-stock-query" else "photo-stock-in"
        return RuntimeRouteDecision(
            task_type=task_type,
            assigned_employee_id="xiaoya",
            transcript=transcript,
            payload={
                "item_name": top_candidate.item_name,
                "confidence": top_candidate.confidence,
                "packaging_hint": top_candidate.packaging_hint,
                "provider_name": recognition.provider_name,
                "used_fallback": recognition.used_fallback,
                "image_media_id": media_ref.media_id,
                **telemetry,
            },
        )
    if ctx.input_kind == "receipt-image":
        return RuntimeRouteDecision(
            task_type="receipt-ocr",
            assigned_employee_id="xiaoya",
            transcript=ctx.source_text,
            payload={
                # Receipt OCR is persisted as an OcrDocument by the runtime processor.
                "document_type": "purchase-receipt",
            },
        )
    raise RuntimeRouteBlocked("runtime_processing_error", "Unsupported input kind")
