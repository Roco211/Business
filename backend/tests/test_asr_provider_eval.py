import importlib.util
import json
from pathlib import Path

import pytest

from app.services.asr_gateway import AsrGateway
from app.services.asr_mock_provider import MockAsrProvider
from app.services.asr_types import AsrMediaInput, AsrProviderError, AsrTranscription


class _RecordingProvider:
    def __init__(self, result: AsrTranscription) -> None:
        self.calls: list[AsrMediaInput] = []
        self._result = result

    def transcribe(self, media_input: AsrMediaInput) -> AsrTranscription:
        self.calls.append(media_input)
        return self._result


class _RetryableFailureProvider:
    def transcribe(self, media_input: AsrMediaInput) -> AsrTranscription:
        del media_input
        raise AsrProviderError("asr_timeout", "temporary upstream failure", retryable=True)


def _load_cli_module():
    module_path = Path(__file__).resolve().parents[1] / "scripts" / "evaluate_real_asr.py"
    spec = importlib.util.spec_from_file_location("evaluate_real_asr_script", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _timer(values: list[float]):
    iterator = iter(values)

    def _read() -> float:
        return next(iterator)

    return _read


def test_evaluate_asr_provider_returns_compact_summary_for_mock_gateway(tmp_path) -> None:
    from app.devtools.asr_provider_eval import evaluate_asr_provider

    audio_path = tmp_path / "voice-query.m4a"
    audio_bytes = b"demo audio"
    audio_path.write_bytes(audio_bytes)
    provider = _RecordingProvider(AsrTranscription(text="check stock left for cola", provider="mock"))

    result = evaluate_asr_provider(
        audio_path=audio_path,
        media_id="voice_query_demo",
        gateway=AsrGateway(primary_provider=provider),
        timer=_timer([10.0, 10.125]),
    )

    assert provider.calls == [
        AsrMediaInput(
            media_ids=["voice_query_demo"],
            text_hint=None,
            file_name="voice-query.m4a",
            content_type="audio/m4a",
            audio_bytes=audio_bytes,
        )
    ]
    assert result.to_dict() == {
        "transcript": "check stock left for cola",
        "confidence": None,
        "provider_name": "mock",
        "used_fallback": False,
        "latency_ms": 125,
    }


def test_evaluate_asr_provider_marks_mock_fallback_usage(tmp_path) -> None:
    from app.devtools.asr_provider_eval import evaluate_asr_provider

    audio_path = tmp_path / "voice-stock-in.m4a"
    audio_path.write_bytes(b"demo audio")

    result = evaluate_asr_provider(
        audio_path=audio_path,
        media_id="voice_stock_in_demo",
        gateway=AsrGateway(
            primary_provider=_RetryableFailureProvider(),
            fallback_provider=MockAsrProvider(),
        ),
        timer=_timer([2.0, 2.042]),
    )

    assert result.to_dict() == {
        "transcript": "restock apples today",
        "confidence": None,
        "provider_name": "mock",
        "used_fallback": True,
        "latency_ms": 42,
    }


def test_evaluate_asr_provider_requires_existing_audio_file(tmp_path) -> None:
    from app.devtools.asr_provider_eval import evaluate_asr_provider

    missing_path = tmp_path / "missing-audio.m4a"

    with pytest.raises(FileNotFoundError):
        evaluate_asr_provider(
            audio_path=missing_path,
            media_id="voice_query_demo",
            gateway=AsrGateway(primary_provider=MockAsrProvider()),
        )


def test_cli_prints_compact_json_summary(tmp_path, capsys, monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load_cli_module()
    audio_path = tmp_path / "voice-query.m4a"
    audio_path.write_bytes(b"demo audio")

    expected_payload = {
        "transcript": "check stock left for cola",
        "confidence": 0.98,
        "provider_name": "mock",
        "used_fallback": False,
        "latency_ms": 7,
    }

    def _fake_evaluate_asr_provider(*, audio_path: Path, media_id: str | None, text_hint: str | None):
        assert audio_path == audio_path_arg
        assert media_id == "voice_query_demo"
        assert text_hint is None
        return module.AsrProviderEvalSummary(**expected_payload)

    audio_path_arg = audio_path
    monkeypatch.setattr(module, "evaluate_asr_provider", _fake_evaluate_asr_provider)

    exit_code = module.main([str(audio_path), "--media-id", "voice_query_demo"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert json.loads(captured.out) == expected_payload
    assert captured.err == ""
    assert captured.out.count("\n") == 1
