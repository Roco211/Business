import pytest

from app.core.config import get_settings
from app.services.vision_gateway import VisionGateway, build_vision_gateway
from app.services.vision_mock_provider import MockVisionProvider
from app.services.vision_types import (
    VisionCandidate,
    VisionMediaInput,
    VisionProviderError,
    VisionRecognition,
)


def _clear_vision_env(monkeypatch, *, env_app="development") -> None:
    for name in (
        "VISION_PROVIDER",
        "VISION_PROVIDER_API_URL",
        "VISION_PROVIDER_API_KEY",
        "VISION_PROVIDER_MODEL",
        "VISION_ALLOW_MOCK_FALLBACK",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("APP_ENV", env_app)


def test_build_vision_gateway_defaults_to_mock(monkeypatch) -> None:
    _clear_vision_env(monkeypatch)
    gateway = build_vision_gateway(get_settings())
    assert isinstance(gateway.primary_provider, MockVisionProvider)


def test_mock_vision_provider_returns_expected_candidates(monkeypatch) -> None:
    _clear_vision_env(monkeypatch)
    gateway = build_vision_gateway(get_settings())
    recognition = gateway.recognize_product(
        VisionMediaInput(
            media_id="image_query_demo",
            public_url="https://mock.example/media/image_query_demo",
            content_type="image/jpeg",
            file_name="query.jpg",
        )
    )
    assert recognition.provider_name == "mock-vision-provider"
    assert recognition.candidates[0].item_name == "Red Bull 250ml"
    assert recognition.candidates[0].confidence >= 0.9


def test_vision_gateway_marks_used_fallback_when_primary_retryable() -> None:
    class RetryableProvider:
        def recognize_product(self, *_):
            raise VisionProviderError("vision_retry", "transient failure", retryable=True)

    class FallbackProvider:
        def recognize_product(self, media_input, *_):
            return VisionRecognition(
                provider_name="fallback-vision",
                candidates=[
                    VisionCandidate(item_name="Fallback", confidence=0.5, packaging_hint=None)
                ],
                used_fallback=False,
                raw_payload={"media_id": media_input.media_id},
            )

    gateway = VisionGateway(
        primary_provider=RetryableProvider(),
        fallback_provider=FallbackProvider(),
    )
    recognition = gateway.recognize_product(
        VisionMediaInput(
            media_id="image_query_demo",
            public_url=None,
            content_type=None,
            file_name=None,
        )
    )
    assert recognition.used_fallback is True
    assert recognition.provider_name == "fallback-vision"


def test_build_vision_gateway_disallows_mock_when_disabled(monkeypatch) -> None:
    _clear_vision_env(monkeypatch)
    monkeypatch.setenv("VISION_PROVIDER", "mock")
    monkeypatch.setenv("VISION_ALLOW_MOCK_FALLBACK", "0")

    with pytest.raises(VisionProviderError, match="mock vision provider is disabled"):
        build_vision_gateway(get_settings())


def test_build_vision_gateway_requires_configuration_in_production(monkeypatch) -> None:
    _clear_vision_env(monkeypatch, env_app="production")
    with pytest.raises(VisionProviderError, match="vision provider is not configured"):
        build_vision_gateway(get_settings())


def test_real_vision_gateway_requires_configuration(monkeypatch) -> None:
    monkeypatch.setenv("VISION_PROVIDER", "real-provider")
    monkeypatch.delenv("VISION_PROVIDER_API_URL", raising=False)
    monkeypatch.delenv("VISION_PROVIDER_API_KEY", raising=False)
    monkeypatch.delenv("VISION_PROVIDER_MODEL", raising=False)

    with pytest.raises(VisionProviderError, match="missing vision provider configuration"):
        build_vision_gateway(get_settings())
