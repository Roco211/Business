import importlib.util
import json
from pathlib import Path

import pytest

from app.services.vision_gateway import VisionGateway
from app.services.vision_mock_provider import MockVisionProvider
from app.services.vision_types import (
    VisionCandidate,
    VisionMediaInput,
    VisionProviderError,
    VisionRecognition,
)


class _RecordingProvider:
    def __init__(self, result: VisionRecognition) -> None:
        self.calls: list[VisionMediaInput] = []
        self._result = result

    def recognize_product(self, media_input: VisionMediaInput) -> VisionRecognition:
        self.calls.append(media_input)
        return self._result


class _RetryableFailureProvider:
    def recognize_product(self, media_input: VisionMediaInput) -> VisionRecognition:
        del media_input
        raise VisionProviderError("vision_timeout", "temporary upstream failure", retryable=True)


def _load_cli_module():
    module_path = Path(__file__).resolve().parents[1] / "scripts" / "evaluate_real_vision.py"
    spec = importlib.util.spec_from_file_location("evaluate_real_vision_script", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_evaluate_vision_file_returns_compact_summary(tmp_path) -> None:
    from app.devtools.vision_provider_eval import evaluate_vision_file

    image_path = tmp_path / "product.jpg"
    image_bytes = b"demo image"
    image_path.write_bytes(image_bytes)
    provider = _RecordingProvider(
        VisionRecognition(
            provider_name="stub-vision",
            candidates=[
                VisionCandidate(item_name="Red Bull 250ml", confidence=0.93, packaging_hint="can")
            ],
            used_fallback=False,
            raw_payload={"provider": "stub-vision"},
        )
    )

    result = evaluate_vision_file(
        file_name=image_path.name,
        content_type="image/jpeg",
        image_bytes=image_bytes,
        gateway=VisionGateway(primary_provider=provider),
        timer=lambda: 20.0,
    )

    assert provider.calls == [
        VisionMediaInput(
            media_id="product.jpg",
            public_url=None,
            content_type="image/jpeg",
            file_name="product.jpg",
            image_bytes=image_bytes,
        )
    ]
    assert result == {
        "provider_name": "stub-vision",
        "used_fallback": False,
        "candidates": [
            {
                "item_name": "Red Bull 250ml",
                "confidence": 0.93,
                "packaging_hint": "can",
            }
        ],
        "latency_ms": 0,
    }


def test_evaluate_vision_file_marks_mock_fallback_usage() -> None:
    from app.devtools.vision_provider_eval import evaluate_vision_file

    result = evaluate_vision_file(
        file_name="product.jpg",
        content_type="image/jpeg",
        image_bytes=b"demo image",
        gateway=VisionGateway(
            primary_provider=_RetryableFailureProvider(),
            fallback_provider=MockVisionProvider(),
        ),
    )

    assert result["provider_name"] == "mock-vision-provider"
    assert result["used_fallback"] is True
    assert "latency_ms" in result


def test_evaluate_vision_path_reads_file_for_batch_runner(tmp_path) -> None:
    from app.devtools.vision_provider_eval import evaluate_vision_path

    image_path = tmp_path / "product.jpg"
    image_bytes = b"demo image"
    image_path.write_bytes(image_bytes)
    provider = _RecordingProvider(
        VisionRecognition(
            provider_name="stub-vision",
            candidates=[VisionCandidate(item_name="Red Bull 250ml", confidence=0.93, packaging_hint="can")],
            used_fallback=False,
            raw_payload={"provider": "stub-vision"},
        )
    )
    timer_values = iter([5.0, 5.044])

    result = evaluate_vision_path(
        file_path=image_path,
        gateway=VisionGateway(primary_provider=provider),
        timer=lambda: next(timer_values),
    )

    assert provider.calls[0].image_bytes == image_bytes
    assert result["latency_ms"] == 44


def test_cli_prints_compact_json_summary(tmp_path, capsys, monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load_cli_module()
    image_path = tmp_path / "product.jpg"
    image_bytes = b"demo image"
    image_path.write_bytes(image_bytes)

    expected_payload = {
        "provider_name": "stub-vision",
        "used_fallback": False,
        "candidates": [
            {
                "item_name": "Red Bull 250ml",
                "confidence": 0.93,
                "packaging_hint": "can",
            }
        ],
    }

    def _fake_evaluate_vision_file(*, file_name: str, content_type: str, image_bytes: bytes):
        assert file_name == "product.jpg"
        assert content_type == "image/jpeg"
        assert image_bytes == image_bytes_arg
        return expected_payload

    image_bytes_arg = image_bytes
    monkeypatch.setattr(module, "evaluate_vision_file", _fake_evaluate_vision_file)

    exit_code = module.main([str(image_path)])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert json.loads(captured.out) == expected_payload
    assert captured.err == ""
    assert captured.out.count("\n") == 1


def test_cli_reports_missing_file(capsys) -> None:
    module = _load_cli_module()
    missing_path = Path("C:/missing/product.jpg")

    exit_code = module.main([str(missing_path)])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "Vision evaluation failed" in captured.err
    assert captured.out == ""
