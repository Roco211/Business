from .tools import transcribe_audio
from .types import RuntimeRouteBlocked, RuntimeRouteDecision, RuntimeTurnContext

QUERY_KEYWORDS = (
    "query",
    "stock",
    "left",
    "remaining",
    "how many",
    "check",
)


def _keyword_in_text(text: str, keyword: str) -> bool:
    lowered = text.lower()
    if " " in keyword:
        return keyword in lowered
    tokens = [token for token in lowered.split() if token]
    return keyword in tokens


def _classify_transcript(transcript: str) -> str:
    if any(_keyword_in_text(transcript, keyword) for keyword in QUERY_KEYWORDS):
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
        transcript = transcribe_audio(media_ids=ctx.media_ids, text_hint=ctx.source_text)
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
