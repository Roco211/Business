import string

from .tools import MockTranscriptionUnavailable, transcribe_audio
from .types import RuntimeRouteBlocked, RuntimeRouteDecision, RuntimeTurnContext

PUNCTUATION_TO_SPACE = str.maketrans({char: " " for char in string.punctuation})
STOCK_IN_PHRASES = ("restock", "stock in")
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
    if any(phrase in normalized for phrase in STOCK_IN_PHRASES):
        return "voice-stock-in"
    if any(_contains_phrase(transcript, phrase) for phrase in QUERY_PHRASES):
        return "voice-stock-query"
    if any(word in tokens for word in QUERY_WORDS):
        return "voice-stock-query"
    return "voice-stock-in"


def _text_or_none(value: str | None) -> str:
    return value or ""


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
        try:
            transcript = transcribe_audio(media_ids=ctx.media_ids, text_hint=ctx.source_text)
        except MockTranscriptionUnavailable as exc:
            raise RuntimeRouteBlocked(
                "runtime_processing_error",
                f"Transcription failed: {exc}",
            ) from exc
        return RuntimeRouteDecision(
            task_type=_classify_transcript(transcript),
            assigned_employee_id="xiaoya",
            transcript=transcript,
        )
    if ctx.input_kind in ("image", "receipt-image"):
        raise RuntimeRouteBlocked(
            "runtime_input_not_supported",
            f"{ctx.input_kind} inputs are not supported yet",
        )
    raise RuntimeRouteBlocked("runtime_processing_error", "Unsupported input kind")
