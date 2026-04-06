import pytest

from app.runtime import tools as runtime_tools
from app.runtime.router import RuntimeRouteBlocked, route_runtime_input, transcribe_runtime_audio
from app.runtime.tools import MockTranscriptionUnavailable, transcribe_audio
from app.runtime.types import RuntimeMediaRef, RuntimeTurnContext
from app.services.asr_types import AsrTranscription


def _build_context(
    *,
    input_kind: str,
    source_text: str | None,
    media_ids: list[str] | None,
    media_refs: list[RuntimeMediaRef] | None = None,
    shop_rules: dict[str, object] | None = None,
) -> RuntimeTurnContext:
    return RuntimeTurnContext(
        shop_id="shop",
        session_id="session",
        source_message_id="msg",
        task_run_id="task",
        input_kind=input_kind,
        source_text=source_text,
        media_ids=media_ids or [],
        media_refs=media_refs or [],
        locale="en-US",
        timezone="UTC",
        shop_rules=shop_rules or {},
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


def test_text_input_with_punctuation_is_query():
    ctx = _build_context(input_kind="text", source_text="check?", media_ids=[])
    decision = route_runtime_input(ctx)
    assert decision.task_type == "voice-stock-query"


def test_text_input_stock_in_phrase_routes_to_stock_in():
    ctx = _build_context(input_kind="text", source_text="stock in apples", media_ids=[])
    decision = route_runtime_input(ctx)
    assert decision.task_type == "voice-stock-in"


def test_text_input_stock_out_phrase_routes_to_stock_out():
    ctx = _build_context(input_kind="text", source_text="stock out cola today", media_ids=[])
    decision = route_runtime_input(ctx)
    assert decision.task_type == "voice-stock-out"


def test_text_input_how_many_phrase_routes_to_query():
    ctx = _build_context(input_kind="text", source_text="how-many apples", media_ids=[])
    decision = route_runtime_input(ctx)
    assert decision.task_type == "voice-stock-query"


def test_text_input_blocks_empty_message():
    ctx = _build_context(input_kind="text", source_text="     ", media_ids=[])
    with pytest.raises(RuntimeRouteBlocked) as excinfo:
        route_runtime_input(ctx)
    assert excinfo.value.error_code == "runtime_processing_error"
    assert "empty" in excinfo.value.error_message.lower()


def test_voice_input_routes_to_query_task():
    ctx = _build_context(
        input_kind="voice",
        source_text=None,
        media_ids=["unknown"],
        media_refs=[
            RuntimeMediaRef(
                media_id="voice_query_demo",
                media_type="audio",
                content_type="audio/m4a",
                file_name="voice.m4a",
                public_url="https://mock.example/media/voice_query_demo",
            )
        ],
    )
    decision = route_runtime_input(ctx)
    assert decision.task_type == "voice-stock-query"
    assert decision.transcript == "check stock left for cola"


def test_voice_input_routes_to_stock_in_task():
    ctx = _build_context(
        input_kind="voice",
        source_text=None,
        media_ids=["voice_stock_in_demo"],
        media_refs=[
            RuntimeMediaRef(
                media_id="voice_stock_in_demo",
                media_type="audio",
                content_type="audio/m4a",
                file_name="voice.m4a",
                public_url="https://mock.example/media/voice_stock_in_demo",
            )
        ],
    )
    decision = route_runtime_input(ctx)
    assert decision.task_type == "voice-stock-in"
    assert decision.transcript == "restock apples today"


def test_voice_input_routes_to_stock_out_task():
    ctx = _build_context(
        input_kind="voice",
        source_text=None,
        media_ids=["voice_stock_out_demo"],
        media_refs=[
            RuntimeMediaRef(
                media_id="voice_stock_out_demo",
                media_type="audio",
                content_type="audio/m4a",
                file_name="voice.m4a",
                public_url="https://mock.example/media/voice_stock_out_demo",
            )
        ],
    )
    decision = route_runtime_input(ctx)
    assert decision.task_type == "voice-stock-out"
    assert decision.transcript == "stock out cola for walk in sale"


def test_voice_input_transcription_failures_block():
    ctx = _build_context(
        input_kind="voice",
        source_text=None,
        media_ids=["unknown"],
        media_refs=[
            RuntimeMediaRef(
                media_id="unknown",
                media_type="audio",
                content_type="audio/m4a",
                file_name="voice.m4a",
                public_url="https://mock.example/media/unknown",
            )
        ],
    )
    with pytest.raises(RuntimeRouteBlocked) as excinfo:
        route_runtime_input(ctx)
    assert excinfo.value.error_code == "runtime_processing_error"
    assert "transcription" in excinfo.value.error_message.lower()


def test_transcribe_runtime_audio_preserves_all_ready_audio_media_refs():
    ctx = _build_context(
        input_kind="voice",
        source_text=None,
        media_ids=["unknown", "voice_query_demo"],
        media_refs=[
            RuntimeMediaRef(
                media_id="unknown",
                media_type="audio",
                content_type="audio/m4a",
                file_name="unknown.m4a",
                public_url="https://mock.example/media/unknown",
            ),
            RuntimeMediaRef(
                media_id="voice_query_demo",
                media_type="audio",
                content_type="audio/m4a",
                file_name="voice_query_demo.m4a",
                public_url="https://mock.example/media/voice_query_demo",
            ),
        ],
    )

    assert transcribe_runtime_audio(ctx) == "check stock left for cola"


def test_transcribe_runtime_audio_blocks_when_no_audio_media_ref_exists():
    ctx = _build_context(
        input_kind="voice",
        source_text=None,
        media_ids=["voice_query_demo"],
        media_refs=[],
    )

    with pytest.raises(RuntimeRouteBlocked) as excinfo:
        transcribe_runtime_audio(ctx)

    assert excinfo.value.error_code == "runtime_processing_error"
    assert "transcription" in excinfo.value.error_message.lower()


def test_transcribe_runtime_audio_blocks_low_confidence_transcription(monkeypatch: pytest.MonkeyPatch):
    ctx = _build_context(
        input_kind="voice",
        source_text=None,
        media_ids=["voice_query_demo"],
        media_refs=[
            RuntimeMediaRef(
                media_id="voice_query_demo",
                media_type="audio",
                content_type="audio/m4a",
                file_name="voice.m4a",
                public_url="https://mock.example/media/voice_query_demo",
            )
        ],
        shop_rules={"low_confidence_threshold": 0.85},
    )

    class _LowConfidenceGateway:
        def transcribe(self, media_input):
            assert media_input.media_ids == ["voice_query_demo"]
            assert media_input.text_hint is None
            return AsrTranscription(text="check stock left for cola", provider="mock", confidence=0.42)

    monkeypatch.setattr(runtime_tools, "get_default_asr_gateway", lambda: _LowConfidenceGateway())

    with pytest.raises(RuntimeRouteBlocked) as excinfo:
        transcribe_runtime_audio(ctx)

    assert excinfo.value.error_code == "asr_low_confidence"
    assert "confidence" in excinfo.value.error_message.lower()


def test_image_input_routes_to_photo_stock_query():
    ctx = _build_context(
        input_kind="image",
        source_text="check shelf stock for red bull",
        media_ids=["image_query_demo"],
    )
    decision = route_runtime_input(ctx)
    assert decision.task_type == "photo-stock-query"
    assert decision.assigned_employee_id == "xiaoya"


def test_image_input_routes_to_photo_stock_in():
    ctx = _build_context(
        input_kind="image",
        source_text="restock red bull cans",
        media_ids=["image_stock_in_demo"],
    )
    decision = route_runtime_input(ctx)
    assert decision.task_type == "photo-stock-in"
    assert decision.assigned_employee_id == "xiaoya"


def test_receipt_image_routes_to_receipt_ocr():
    ctx = _build_context(
        input_kind="receipt-image",
        source_text=None,
        media_ids=["receipt_demo"],
    )
    decision = route_runtime_input(ctx)
    assert decision.task_type == "receipt-ocr"
    assert decision.assigned_employee_id == "xiaoya"
