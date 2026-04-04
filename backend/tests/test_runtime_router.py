import pytest

from backend.app.runtime.router import RuntimeRouteBlocked, route_runtime_input
from backend.app.runtime.tools import MockTranscriptionUnavailable, transcribe_audio
from backend.app.runtime.types import RuntimeTurnContext


def _build_context(
    *,
    input_kind: str,
    source_text: str | None,
    media_ids: list[str] | None,
) -> RuntimeTurnContext:
    return RuntimeTurnContext(
        shop_id="shop",
        session_id="session",
        source_message_id="msg",
        task_run_id="task",
        input_kind=input_kind,
        source_text=source_text,
        media_ids=media_ids or [],
        locale="en-US",
        timezone="UTC",
        shop_rules={},
        recent_messages=[],
        pending_confirmation_id=None,
    )


def test_transcribe_audio_prefers_text_hint():
    assert transcribe_audio(media_ids=["voice_query_demo"], text_hint="  fallback text  ") == "fallback text"


def test_transcribe_audio_uses_voice_query_fixture():
    assert transcribe_audio(media_ids=["voice_query_demo"], text_hint=None) == "check stock left for cola"


def test_transcribe_audio_uses_voice_stock_in_fixture():
    assert transcribe_audio(media_ids=["voice_stock_in_demo"], text_hint=None) == "restock apples today"


def test_transcribe_audio_raises_when_missing_fixture():
    with pytest.raises(MockTranscriptionUnavailable):
        transcribe_audio(media_ids=["unknown"], text_hint=None)


def test_text_input_routes_to_stock_query():
    ctx = _build_context(input_kind="text", source_text="  check stock left for cola  ", media_ids=[])
    decision = route_runtime_input(ctx)
    assert decision.task_type == "voice-stock-query"
    assert decision.assigned_employee_id == "xiaoya"
    assert decision.transcript == "check stock left for cola"


def test_text_input_blocks_empty_message():
    ctx = _build_context(input_kind="text", source_text="     ", media_ids=[])
    with pytest.raises(RuntimeRouteBlocked) as excinfo:
        route_runtime_input(ctx)
    assert excinfo.value.error_code == "runtime_processing_error"
    assert "empty" in excinfo.value.error_message.lower()


def test_voice_input_routes_to_query_task():
    ctx = _build_context(input_kind="voice", source_text=None, media_ids=["voice_query_demo"])
    decision = route_runtime_input(ctx)
    assert decision.task_type == "voice-stock-query"
    assert decision.transcript == "check stock left for cola"


def test_voice_input_routes_to_stock_in_task():
    ctx = _build_context(input_kind="voice", source_text=None, media_ids=["voice_stock_in_demo"])
    decision = route_runtime_input(ctx)
    assert decision.task_type == "voice-stock-in"
    assert decision.transcript == "restock apples today"


@pytest.mark.parametrize(
    "kind",
    ["image", "receipt-image"],
)
def test_image_inputs_are_blocked(kind: str):
    ctx = _build_context(input_kind=kind, source_text=None, media_ids=[])
    with pytest.raises(RuntimeRouteBlocked) as excinfo:
        route_runtime_input(ctx)
    assert excinfo.value.error_code == "runtime_input_not_supported"
    assert kind in excinfo.value.error_message.lower()
