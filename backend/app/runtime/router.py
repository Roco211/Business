from .tools import transcribe_audio
from .types import RuntimeRouteBlocked, RuntimeRouteDecision, RuntimeTurnContext

QUERY_KEYWORDS = ("price", "quote", "how", "what")


def _is_query_transcription(transcript: str) -> bool:
    lowered = transcript.lower()
    return "?" in transcript or any(keyword in lowered for keyword in QUERY_KEYWORDS)


def route_runtime_input(ctx: RuntimeTurnContext) -> RuntimeRouteDecision:
    if ctx.input_type == "text":
        text = ctx.source_text.strip()
        if not text:
            raise RuntimeRouteBlocked("runtime_processing_error")
        return RuntimeRouteDecision(
            task_type="voice-stock-query",
            assigned_employee_id="xiaoya",
            text=text,
        )
    if ctx.input_type == "voice":
        transcript = transcribe_audio(ctx.text_hint, ctx.media_ids)
        task_type = "voice-stock-query" if _is_query_transcription(transcript) else "voice-stock-in"
        return RuntimeRouteDecision(
            task_type=task_type,
            assigned_employee_id="xiaoya",
            text=transcript,
        )
    if ctx.input_type in ("image", "receipt-image"):
        raise RuntimeRouteBlocked("runtime_input_not_supported")
    raise RuntimeRouteBlocked("runtime_processing_error")
