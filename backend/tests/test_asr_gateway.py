import pytest

from app.core.config import Settings
from app.services.asr_gateway import AsrGateway, build_asr_gateway, get_default_asr_gateway
from app.services.asr_mock_provider import MockAsrProvider
from app.services.asr_types import AsrMediaInput, AsrProviderError, AsrTranscription


def _build_settings(**overrides: object) -> Settings:
    values = {
        "app_env": "test",
        "app_host": "127.0.0.1",
        "app_port": 8001,
        "redis_url": "redis://localhost:6379/0",
        "database_url": "sqlite:///tmp.db",
        "session_stream_keepalive_seconds": 20.0,
        "default_shop_id": "shop_default",
        "default_owner_actor_id": "owner_default",
        "default_session_id": "sess_default",
        "seed_owner_email": None,
        "seed_owner_password": None,
        "seed_owner_display_name": "Default Owner",
        "auth_session_ttl_minutes": 120,
        "asr_provider": "mock",
        "asr_provider_api_url": None,
        "asr_provider_api_key": None,
        "asr_provider_model": "mock-default",
        "asr_timeout_seconds": 15.0,
        "asr_allow_mock_fallback": True,
    }
    values.update(overrides)
    return Settings(**values)


def test_mock_provider_prefers_text_hint() -> None:
    provider = MockAsrProvider()
    result = provider.transcribe(
        AsrMediaInput(media_ids=["voice_query_demo"], text_hint="  hello world  ")
    )
    assert result == AsrTranscription(text="hello world", provider="mock")


def test_mock_provider_uses_fixture_media_id() -> None:
    provider = MockAsrProvider()
    result = provider.transcribe(AsrMediaInput(media_ids=["voice_stock_in_demo"], text_hint=None))
    assert result.text == "restock apples today"
    assert result.provider == "mock"


def test_mock_provider_raises_unavailable_when_no_fixture_match() -> None:
    provider = MockAsrProvider()
    with pytest.raises(AsrProviderError) as excinfo:
        provider.transcribe(AsrMediaInput(media_ids=["missing"], text_hint=None))
    assert excinfo.value.code == "asr_unavailable"
    assert excinfo.value.retryable is False


def test_build_asr_gateway_returns_mock_gateway_for_mock_provider() -> None:
    gateway = build_asr_gateway(_build_settings(asr_provider="mock"))
    assert isinstance(gateway, AsrGateway)
    assert isinstance(gateway.primary_provider, MockAsrProvider)
    assert gateway.fallback_provider is None


def test_real_provider_missing_credentials_raises_unavailable() -> None:
    with pytest.raises(AsrProviderError) as excinfo:
        build_asr_gateway(
            _build_settings(
                asr_provider="real-provider",
                asr_provider_api_url=None,
                asr_provider_api_key=None,
                asr_provider_model=None,
            )
        )
    assert excinfo.value.code == "asr_unavailable"
    assert str(excinfo.value) == "missing ASR provider configuration"
    assert excinfo.value.retryable is False


def test_real_provider_with_credentials_raises_not_implemented() -> None:
    with pytest.raises(NotImplementedError, match="real provider is added in Task 4"):
        build_asr_gateway(
            _build_settings(
                asr_provider="real-provider",
                asr_provider_api_url="https://api.example.com",
                asr_provider_api_key="key",
                asr_provider_model="model-a",
            )
        )


def test_get_default_asr_gateway_uses_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ASR_PROVIDER", "mock")
    get_default_asr_gateway.cache_clear()
    one = get_default_asr_gateway()
    two = get_default_asr_gateway()
    assert one is two

