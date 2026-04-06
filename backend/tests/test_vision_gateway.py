import pytest

from app.core.config import get_settings
from app.services.vision_gateway import build_vision_gateway
from app.services.vision_mock_provider import MockVisionProvider
from app.services.vision_types import VisionMediaInput, VisionProviderError


def test_build_vision_gateway_defaults_to_mock() -> None:
    gateway = build_vision_gateway(get_settings())
    assert isinstance(gateway.primary_provider, MockVisionProvider)


def test_mock_vision_provider_returns_expected_candidates() -> None:
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


def test_real_vision_gateway_requires_configuration(monkeypatch) -> None:
    monkeypatch.setenv("VISION_PROVIDER", "real-provider")
    monkeypatch.delenv("VISION_PROVIDER_API_URL", raising=False)
    monkeypatch.delenv("VISION_PROVIDER_API_KEY", raising=False)
    monkeypatch.delenv("VISION_PROVIDER_MODEL", raising=False)

    with pytest.raises(VisionProviderError, match="missing vision provider configuration"):
        build_vision_gateway(get_settings())
