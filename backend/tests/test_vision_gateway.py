import httpx
from importlib import import_module

import pytest

from app.core.config import Settings
from app.services.vision_gateway import VisionGateway, build_vision_gateway, get_default_vision_gateway
from app.services.vision_mock_provider import MockVisionProvider
from app.services.vision_types import (
    VisionCandidate,
    VisionMediaInput,
    VisionProviderError,
    VisionRecognition,
)


def _build_settings(**overrides: object) -> Settings:
    values = {
        "app_env": "test",
        "app_host": "127.0.0.1",
        "app_port": 8001,
        "redis_url": "redis://localhost:6379/0",
        "database_url": "sqlite:///tmp.db",
        "session_stream_keepalive_seconds": 20.0,
        "vision_provider": "",
        "vision_provider_api_url": None,
        "vision_provider_api_key": None,
        "vision_provider_model": None,
        "vision_timeout_seconds": 15.0,
        "vision_allow_mock_fallback": True,
    }
    values.update(overrides)
    return Settings(**values)


class _StaticProvider:
    def __init__(self, *, result: VisionRecognition | None = None, error: VisionProviderError | None = None) -> None:
        self._result = result
        self._error = error

    def recognize_product(self, media_input: VisionMediaInput) -> VisionRecognition:
        del media_input
        if self._error is not None:
            raise self._error
        assert self._result is not None
        return self._result


class _HttpxJsonResponse:
    def __init__(self, payload: object, *, status_code: int = 200) -> None:
        self._payload = payload
        self._status_code = status_code
        self._request = httpx.Request("POST", "https://api.example.com/v1/vision")

    def raise_for_status(self) -> None:
        if self._status_code >= 400:
            raise httpx.HTTPStatusError(
                "request failed",
                request=self._request,
                response=httpx.Response(self._status_code, request=self._request),
            )

    def json(self) -> object:
        return self._payload


def _build_real_gateway(**overrides: object) -> VisionGateway:
    settings_overrides = {
        "vision_provider": "real-provider",
        "vision_provider_api_url": "https://api.example.com/v1/vision",
        "vision_provider_api_key": "key",
        "vision_provider_model": "vision-1",
        "vision_allow_mock_fallback": False,
    }
    settings_overrides.update(overrides)
    return build_vision_gateway(_build_settings(**settings_overrides))


def _get_real_provider_type() -> type[object]:
    module = import_module("app.services.vision_real_provider")
    return module.RealVisionProvider


def test_build_vision_gateway_defaults_to_mock_when_fallback_allowed() -> None:
    gateway = build_vision_gateway(_build_settings())
    assert isinstance(gateway.primary_provider, MockVisionProvider)
    assert gateway.fallback_provider is None


def test_trial_mode_rejects_mock_vision_provider() -> None:
    with pytest.raises(VisionProviderError) as excinfo:
        build_vision_gateway(
            _build_settings(
                app_runtime_mode="trial",
                vision_provider="mock",
                vision_allow_mock_fallback=True,
            )
        )

    assert excinfo.value.code == "vision_unavailable"
    assert "trial" in str(excinfo.value).lower()
    assert excinfo.value.retryable is False


def test_trial_mode_rejects_real_vision_provider_when_mock_fallback_enabled() -> None:
    with pytest.raises(VisionProviderError) as excinfo:
        build_vision_gateway(
            _build_settings(
                app_runtime_mode="trial",
                vision_provider="real-provider",
                vision_provider_api_url="https://api.example.com/v1/vision",
                vision_provider_api_key="key",
                vision_provider_model="vision-1",
                vision_allow_mock_fallback=True,
            )
        )

    assert excinfo.value.code == "vision_unavailable"
    assert "fallback" in str(excinfo.value).lower()
    assert excinfo.value.retryable is False


def test_real_vision_provider_missing_configuration_raises_unavailable() -> None:
    with pytest.raises(VisionProviderError) as excinfo:
        build_vision_gateway(
            _build_settings(
                vision_provider="real-provider",
                vision_provider_api_url=None,
                vision_provider_api_key=None,
                vision_provider_model=None,
            )
        )

    assert excinfo.value.code == "vision_unavailable"
    assert str(excinfo.value) == "missing vision provider configuration"
    assert excinfo.value.retryable is False


def test_real_vision_provider_with_credentials_builds_gateway() -> None:
    gateway = _build_real_gateway(vision_timeout_seconds=21.5)
    real_provider_type = _get_real_provider_type()

    assert isinstance(gateway.primary_provider, real_provider_type)
    assert gateway.primary_provider.api_url == "https://api.example.com/v1/vision"
    assert gateway.primary_provider.api_key == "key"
    assert gateway.primary_provider.model == "vision-1"
    assert gateway.primary_provider.timeout_seconds == 21.5
    assert gateway.fallback_provider is None


def test_real_vision_provider_recognize_normalizes_http_response(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, str, dict[str, object]]] = []

    def _fake_request(method: str, url: str, **kwargs: object) -> _HttpxJsonResponse:
        calls.append((method, url, dict(kwargs)))
        return _HttpxJsonResponse(
            {
                "provider": "vendor-vision",
                "candidates": [
                    {"name": "Red Bull 250ml", "confidence": 0.93, "packaging_hint": "can"},
                    {"name": "Fanta 330ml", "confidence": 0.52, "packaging_hint": "can"},
                ]
            }
        )

    monkeypatch.setattr(httpx, "request", _fake_request)

    gateway = _build_real_gateway(vision_timeout_seconds=7.5)

    result = gateway.primary_provider.recognize_product(
        VisionMediaInput(
            media_id="image_query_demo",
            public_url="https://example.com/product.jpg",
            content_type="image/jpeg",
            file_name="product.jpg",
        )
    )

    assert result == VisionRecognition(
        provider_name="vendor-vision",
        candidates=[
            VisionCandidate(item_name="Red Bull 250ml", confidence=0.93, packaging_hint="can"),
            VisionCandidate(item_name="Fanta 330ml", confidence=0.52, packaging_hint="can"),
        ],
        used_fallback=False,
        raw_payload={
            "provider": "vendor-vision",
            "candidates": [
                {"name": "Red Bull 250ml", "confidence": 0.93, "packaging_hint": "can"},
                {"name": "Fanta 330ml", "confidence": 0.52, "packaging_hint": "can"},
            ],
        },
    )
    assert calls == [
        (
            "POST",
            "https://api.example.com/v1/vision",
            {
                "headers": {"Authorization": "Bearer key"},
                "timeout": 7.5,
                "json": {
                    "media_id": "image_query_demo",
                    "media_url": "https://example.com/product.jpg",
                    "content_type": "image/jpeg",
                    "file_name": "product.jpg",
                    "model": "vision-1",
                },
            },
        )
    ]


def test_real_vision_provider_falls_through_empty_candidates_alias(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        httpx,
        "request",
        lambda *args, **kwargs: _HttpxJsonResponse(
            {
                "candidates": [],
                "result": {
                    "candidates": [
                        {"item_name": "Nested Candidate", "confidence": 0.73, "packaging_hint": "bottle"}
                    ]
                },
            }
        ),
    )
    gateway = _build_real_gateway()

    result = gateway.primary_provider.recognize_product(
        VisionMediaInput("image_alias_fallthrough", "https://example.com/i.jpg", "image/jpeg", "i.jpg")
    )

    assert result.candidates == [
        VisionCandidate(item_name="Nested Candidate", confidence=0.73, packaging_hint="bottle")
    ]


def test_real_vision_provider_recognize_includes_inline_image_payload_when_present(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, str, dict[str, object]]] = []

    def _fake_request(method: str, url: str, **kwargs: object) -> _HttpxJsonResponse:
        calls.append((method, url, dict(kwargs)))
        return _HttpxJsonResponse({"candidates": [{"item_name": "Sprite 500ml", "confidence": 0.61}]})

    monkeypatch.setattr(httpx, "request", _fake_request)

    gateway = _build_real_gateway()

    result = gateway.primary_provider.recognize_product(
        VisionMediaInput(
            media_id="image_eval",
            public_url=None,
            content_type="image/png",
            file_name="product.png",
            image_bytes=b"\x89PNGdemo",
        )
    )

    assert result.candidates[0].item_name == "Sprite 500ml"
    assert calls == [
        (
            "POST",
            "https://api.example.com/v1/vision",
            {
                "headers": {"Authorization": "Bearer key"},
                "timeout": 15.0,
                "json": {
                    "media_id": "image_eval",
                    "content_type": "image/png",
                    "file_name": "product.png",
                    "model": "vision-1",
                    "image": {
                        "file_name": "product.png",
                        "content_type": "image/png",
                        "base64_data": "iVBOR2RlbW8=",
                    },
                },
            },
        )
    ]


def test_real_vision_provider_maps_timeout_to_retryable_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        httpx,
        "request",
        lambda *args, **kwargs: (_ for _ in ()).throw(httpx.TimeoutException("slow")),
    )
    gateway = _build_real_gateway()

    with pytest.raises(VisionProviderError, match="slow") as excinfo:
        gateway.primary_provider.recognize_product(
            VisionMediaInput("image_query_demo", "https://example.com/i.jpg", "image/jpeg", "i.jpg")
        )

    assert excinfo.value.code == "vision_timeout"
    assert excinfo.value.retryable is True


def test_real_vision_provider_rejects_invalid_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        httpx,
        "request",
        lambda *args, **kwargs: _HttpxJsonResponse({"candidates": []}),
    )
    gateway = _build_real_gateway()

    with pytest.raises(VisionProviderError, match="did not include recognition candidates") as excinfo:
        gateway.primary_provider.recognize_product(
            VisionMediaInput("image_query_demo", "https://example.com/i.jpg", "image/jpeg", "i.jpg")
        )

    assert excinfo.value.code == "vision_unavailable"
    assert excinfo.value.retryable is False


def test_real_vision_provider_retryable_http_status_uses_mock_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        httpx,
        "request",
        lambda *args, **kwargs: _HttpxJsonResponse({"detail": "server error"}, status_code=503),
    )
    gateway = _build_real_gateway(vision_allow_mock_fallback=True)

    result = gateway.recognize_product(
        VisionMediaInput(
            media_id="image_query_demo",
            public_url="https://example.com/product.jpg",
            content_type="image/jpeg",
            file_name="product.jpg",
        )
    )

    assert result.provider_name == "mock-vision-provider"
    assert result.used_fallback is True


def test_real_vision_provider_permanent_adapter_error_does_not_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        httpx,
        "request",
        lambda *args, **kwargs: _HttpxJsonResponse({"candidates": []}),
    )
    gateway = _build_real_gateway(vision_allow_mock_fallback=True)

    with pytest.raises(VisionProviderError) as excinfo:
        gateway.recognize_product(
            VisionMediaInput(
                media_id="image_query_demo",
                public_url="https://example.com/product.jpg",
                content_type="image/jpeg",
                file_name="product.jpg",
            )
        )

    assert excinfo.value.code == "vision_unavailable"
    assert excinfo.value.retryable is False


def test_get_default_vision_gateway_uses_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.delenv("VISION_PROVIDER", raising=False)
    monkeypatch.delenv("VISION_ALLOW_MOCK_FALLBACK", raising=False)
    get_default_vision_gateway.cache_clear()
    one = get_default_vision_gateway()
    two = get_default_vision_gateway()
    assert one is two


def test_gateway_returns_primary_provider_success() -> None:
    expected = VisionRecognition(
        provider_name="primary",
        candidates=[VisionCandidate(item_name="Primary", confidence=0.9, packaging_hint=None)],
        used_fallback=False,
        raw_payload={},
    )
    gateway = VisionGateway(primary_provider=_StaticProvider(result=expected))

    actual = gateway.recognize_product(
        VisionMediaInput("image_query_demo", "https://example.com/product.jpg", "image/jpeg", "product.jpg")
    )

    assert actual == expected


def test_gateway_uses_fallback_when_primary_raises_retryable_provider_error() -> None:
    primary = _StaticProvider(
        error=VisionProviderError("vision_unavailable", "primary down", retryable=True)
    )
    fallback = _StaticProvider(
        result=VisionRecognition(
            provider_name="mock-vision-provider",
            candidates=[VisionCandidate(item_name="Fallback", confidence=0.5, packaging_hint=None)],
            used_fallback=False,
            raw_payload={},
        )
    )
    gateway = VisionGateway(primary_provider=primary, fallback_provider=fallback)

    actual = gateway.recognize_product(
        VisionMediaInput("image_query_demo", "https://example.com/product.jpg", "image/jpeg", "product.jpg")
    )

    assert actual.used_fallback is True
    assert actual.provider_name == "mock-vision-provider"


def test_gateway_does_not_use_fallback_for_non_retryable_provider_error() -> None:
    expected = VisionProviderError("vision_unavailable", "primary malformed", retryable=False)
    fallback = _StaticProvider(
        result=VisionRecognition(
            provider_name="mock-vision-provider",
            candidates=[VisionCandidate(item_name="Fallback", confidence=0.5, packaging_hint=None)],
            used_fallback=False,
            raw_payload={},
        )
    )
    gateway = VisionGateway(primary_provider=_StaticProvider(error=expected), fallback_provider=fallback)

    with pytest.raises(VisionProviderError) as excinfo:
        gateway.recognize_product(
            VisionMediaInput("image_query_demo", "https://example.com/product.jpg", "image/jpeg", "product.jpg")
        )

    assert excinfo.value is expected
