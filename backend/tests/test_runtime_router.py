from backend.app.runtime.router import route_runtime_input
import pytest

from backend.app.runtime.router import RuntimeRouteBlocked, route_runtime_input
from backend.app.runtime.tools import transcribe_audio
from backend.app.runtime.types import RuntimeTurnContext


def test_text_input_routes_to_stock_query():
    ctx = RuntimeTurnContext(
        input_type="text",
        source_text="  what's the price of jade?  ",
        text_hint="",
        media_ids=[],
    )
    decision = route_runtime_input(ctx)
    assert decision.task_type == "voice-stock-query"
    assert decision.assigned_employee_id == "xiaoya"
    assert decision.text == "what's the price of jade?"


def test_transcribe_audio_prefers_text_hint():
    assert transcribe_audio(text_hint="price clue", media_ids=["fixture-query"]) == "price clue"


def test_transcribe_audio_reads_fixture_media_id():
    assert transcribe_audio(text_hint="", media_ids=["fixture-query"]) == "how much is jade today?"


def test_voice_input_routes_to_query_task():
    ctx = RuntimeTurnContext(
        input_type="voice",
        source_text="",
        text_hint="what's the current price?",
        media_ids=["fixture-query"],
    )
    decision = route_runtime_input(ctx)
    assert decision.task_type == "voice-stock-query"
    assert decision.assigned_employee_id == "xiaoya"
    assert "price" in decision.text


def test_receipt_image_blocked():
    ctx = RuntimeTurnContext(input_type="receipt-image", source_text="", text_hint="", media_ids=[])
    with pytest.raises(RuntimeRouteBlocked) as excinfo:
        route_runtime_input(ctx)
    assert excinfo.value.error_code == "runtime_input_not_supported"
