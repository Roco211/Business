import base64

import httpx

from app.core.config import Settings
from app.services.ark_multimodal_provider import ArkAsrProvider, ArkOcrProvider, ArkVisionProvider
from app.services.asr_gateway import build_asr_gateway
from app.services.asr_types import AsrMediaInput, AsrTranscription
from app.services.ocr_gateway import build_ocr_gateway
from app.services.ocr_types import OcrExtractedLineItem, OcrMediaInput
from app.services.vision_gateway import build_vision_gateway
from app.services.vision_types import VisionCandidate, VisionMediaInput


def _settings(**overrides: object) -> Settings:
    values = {
        "app_env": "test",
        "app_host": "127.0.0.1",
        "app_port": 8001,
        "redis_url": "redis://localhost:6379/0",
        "database_url": "sqlite:///tmp.db",
        "session_stream_keepalive_seconds": 20.0,
        "ocr_allow_mock_fallback": False,
        "vision_allow_mock_fallback": False,
        "asr_allow_mock_fallback": False,
    }
    values.update(overrides)
    return Settings(**values)


class _JsonResponse:
    def __init__(self, assistant_content: str, *, status_code: int = 200) -> None:
        self._payload = {
            "choices": [{"message": {"content": assistant_content}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
        }
        self._status_code = status_code
        self._request = httpx.Request("POST", "https://ark.example.com/chat/completions")

    def raise_for_status(self) -> None:
        if self._status_code >= 400:
            raise httpx.HTTPStatusError(
                "request failed",
                request=self._request,
                response=httpx.Response(self._status_code, request=self._request),
            )

    def json(self) -> object:
        return self._payload


def test_volcano_ocr_gateway_builds_ark_provider() -> None:
    gateway = build_ocr_gateway(
        _settings(
            ocr_provider="volcano",
            ocr_provider_api_url="https://ark.example.com/chat/completions",
            ocr_provider_api_key="key",
            ocr_provider_model="doubao-seed-2-0-pro-260215",
        )
    )

    assert isinstance(gateway.primary_provider, ArkOcrProvider)
    assert gateway.primary_provider.model == "doubao-seed-2-0-pro-260215"
    assert gateway.fallback_provider is None


def test_volcano_vision_gateway_builds_ark_provider() -> None:
    gateway = build_vision_gateway(
        _settings(
            vision_provider="doubao",
            vision_provider_api_key="key",
            vision_provider_model="doubao-seed-2-0-pro-260215",
        )
    )

    assert isinstance(gateway.primary_provider, ArkVisionProvider)
    assert gateway.primary_provider.api_url.endswith("/chat/completions")


def test_volcano_asr_gateway_builds_ark_provider() -> None:
    gateway = build_asr_gateway(
        _settings(
            asr_provider="ark",
            asr_provider_api_key="key",
            asr_provider_model="doubao-seed-2-0-pro-260215",
        )
    )

    assert isinstance(gateway.primary_provider, ArkAsrProvider)
    assert gateway.primary_provider.api_url.endswith("/chat/completions")


def test_ark_ocr_provider_uses_image_url_payload_and_normalizes_response(monkeypatch) -> None:
    calls = []

    def fake_request(method: str, url: str, **kwargs: object) -> _JsonResponse:
        calls.append((method, url, kwargs))
        return _JsonResponse(
            '{"document_type":"purchase-receipt","raw_text":"M8 screw 20 box",'
            '"items":[{"name":"M8螺丝","quantity":20,"unit":"盒","price":8.5}],'
            '"total_amount":170,"low_confidence_fields":[],"confidence":0.96}'
        )

    monkeypatch.setattr(httpx, "request", fake_request)
    provider = ArkOcrProvider("https://ark.example.com/chat/completions", "key", "doubao", 12)

    result = provider.extract_purchase_receipt(
        OcrMediaInput("receipt1", "https://example.com/receipt.jpg", "image/jpeg", "receipt.jpg")
    )

    assert result.provider_name == "ark-doubao"
    assert result.line_items == [OcrExtractedLineItem("M8螺丝", 20.0, "盒", 8.5)]
    assert result.total_amount == 170.0
    request_json = calls[0][2]["json"]
    assert request_json["model"] == "doubao"
    assert request_json["messages"][1]["content"][1] == {
        "type": "image_url",
        "image_url": {"url": "https://example.com/receipt.jpg"},
    }


def test_ark_vision_provider_uses_inline_image_data_url(monkeypatch) -> None:
    calls = []

    def fake_request(method: str, url: str, **kwargs: object) -> _JsonResponse:
        calls.append((method, url, kwargs))
        return _JsonResponse(
            '{"candidates":[{"name":"十字螺丝刀","confidence":0.94,"packaging_hint":"红色手柄"}]}'
        )

    monkeypatch.setattr(httpx, "request", fake_request)
    provider = ArkVisionProvider("https://ark.example.com/chat/completions", "key", "doubao", 12)

    result = provider.recognize_product(
        VisionMediaInput("image1", None, "image/png", "tool.png", image_bytes=b"png-bytes")
    )

    assert result.candidates == [VisionCandidate("十字螺丝刀", 0.94, "红色手柄")]
    image_url = calls[0][2]["json"]["messages"][1]["content"][1]["image_url"]["url"]
    assert image_url == "data:image/png;base64," + base64.b64encode(b"png-bytes").decode("ascii")


def test_ark_asr_provider_uses_input_audio_payload_and_normalizes_response(monkeypatch) -> None:
    calls = []

    def fake_request(method: str, url: str, **kwargs: object) -> _JsonResponse:
        calls.append((method, url, kwargs))
        return _JsonResponse('{"text":"今天卖出两把锤子","confidence":0.91}')

    monkeypatch.setattr(httpx, "request", fake_request)
    provider = ArkAsrProvider("https://ark.example.com/chat/completions", "key", "doubao", 12)

    result = provider.transcribe(
        AsrMediaInput(
            media_ids=["voice1"],
            file_name="voice.wav",
            content_type="audio/wav",
            audio_bytes=b"wav-bytes",
        )
    )

    assert result == AsrTranscription("今天卖出两把锤子", "ark-doubao", 0.91)
    input_audio = calls[0][2]["json"]["messages"][1]["content"][1]
    assert input_audio["type"] == "input_audio"
    assert input_audio["input_audio"] == {
        "data": base64.b64encode(b"wav-bytes").decode("ascii"),
        "format": "wav",
    }
