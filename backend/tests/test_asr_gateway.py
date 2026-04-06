import httpx
from importlib import import_module
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


class _StaticProvider:
    def __init__(self, *, result: AsrTranscription | None = None, error: AsrProviderError | None = None) -> None:
        self._result = result
        self._error = error

    def transcribe(self, media_input: AsrMediaInput) -> AsrTranscription:
        del media_input
        if self._error is not None:
            raise self._error
        assert self._result is not None
        return self._result


class _HttpxJsonResponse:
    def __init__(self, payload: object, *, status_code: int = 200) -> None:
        self._payload = payload
        self._status_code = status_code
        self._request = httpx.Request("POST", "https://api.example.com/v1/transcriptions")

    def raise_for_status(self) -> None:
        if self._status_code >= 400:
            raise httpx.HTTPStatusError(
                "request failed",
                request=self._request,
                response=httpx.Response(self._status_code, request=self._request),
            )

    def json(self) -> object:
        return self._payload


def _build_real_gateway(**overrides: object) -> AsrGateway:
    settings_overrides = {
        "asr_provider": "real-provider",
        "asr_provider_api_url": "https://api.example.com/v1/transcriptions",
        "asr_provider_api_key": "key",
        "asr_provider_model": "model-a",
        "asr_allow_mock_fallback": False,
    }
    settings_overrides.update(overrides)
    try:
        return build_asr_gateway(
            _build_settings(**settings_overrides)
        )
    except NotImplementedError as exc:  # pragma: no cover - red phase guard for Task 4
        pytest.fail(f"configured real providers should not raise NotImplementedError: {exc}")


def _get_real_provider_type() -> type[object]:
    try:
        module = import_module("app.services.asr_real_provider")
    except ModuleNotFoundError as exc:  # pragma: no cover - red phase guard for Task 4
        pytest.fail(f"expected app.services.asr_real_provider to exist: {exc}")
    return module.RealAsrProvider


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


def test_real_provider_with_credentials_builds_gateway() -> None:
    gateway = _build_real_gateway(asr_timeout_seconds=21.5)
    real_provider_type = _get_real_provider_type()

    assert isinstance(gateway.primary_provider, real_provider_type)
    assert gateway.primary_provider.api_url == "https://api.example.com/v1/transcriptions"
    assert gateway.primary_provider.api_key == "key"
    assert gateway.primary_provider.model == "model-a"
    assert gateway.primary_provider.timeout_seconds == 21.5
    assert gateway.fallback_provider is None


def test_real_provider_transcribe_normalizes_http_response(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, str, dict[str, object]]] = []

    def _fake_request(method: str, url: str, **kwargs: object) -> _HttpxJsonResponse:
        calls.append((method, url, dict(kwargs)))
        return _HttpxJsonResponse({"text": "decoded speech", "confidence": 0.87})

    monkeypatch.setattr(httpx, "request", _fake_request)

    gateway = _build_real_gateway(asr_timeout_seconds=9.25)

    result = gateway.primary_provider.transcribe(
        AsrMediaInput(media_ids=["voice_query_demo"], text_hint="spoken question")
    )

    assert result == AsrTranscription(
        text="decoded speech",
        provider="real-provider",
        confidence=0.87,
    )
    assert calls == [
        (
            "POST",
            "https://api.example.com/v1/transcriptions",
            {
                "headers": {"Authorization": "Bearer key"},
                "timeout": 9.25,
                "json": {
                    "media_ids": ["voice_query_demo"],
                    "text_hint": "spoken question",
                    "model": "model-a",
                },
            },
        )
    ]


def test_real_provider_timeout_maps_to_retryable_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    def _fake_request(method: str, url: str, **kwargs: object) -> _HttpxJsonResponse:
        del method, url, kwargs
        raise httpx.TimeoutException("request timed out")

    monkeypatch.setattr(httpx, "request", _fake_request)

    gateway = _build_real_gateway()

    with pytest.raises(AsrProviderError) as excinfo:
        gateway.primary_provider.transcribe(AsrMediaInput(media_ids=["voice_query_demo"], text_hint=None))

    assert excinfo.value.code == "asr_timeout"
    assert str(excinfo.value) == "request timed out"
    assert excinfo.value.retryable is True


def test_real_provider_uses_mock_fallback_when_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    def _fake_request(method: str, url: str, **kwargs: object) -> _HttpxJsonResponse:
        del method, url, kwargs
        raise httpx.TimeoutException("request timed out")

    monkeypatch.setattr(httpx, "request", _fake_request)

    gateway = _build_real_gateway(asr_allow_mock_fallback=True)
    real_provider_type = _get_real_provider_type()

    assert isinstance(gateway.primary_provider, real_provider_type)
    assert isinstance(gateway.fallback_provider, MockAsrProvider)

    result = gateway.transcribe(AsrMediaInput(media_ids=["voice_stock_in_demo"], text_hint=None))

    assert result == AsrTranscription(text="restock apples today", provider="mock")


def test_get_default_asr_gateway_uses_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ASR_PROVIDER", "mock")
    get_default_asr_gateway.cache_clear()
    one = get_default_asr_gateway()
    two = get_default_asr_gateway()
    assert one is two


def test_gateway_returns_primary_provider_success() -> None:
    expected = AsrTranscription(text="ok", provider="primary")
    gateway = AsrGateway(primary_provider=_StaticProvider(result=expected))
    actual = gateway.transcribe(AsrMediaInput(media_ids=["a"], text_hint=None))
    assert actual == expected


def test_gateway_uses_fallback_when_primary_raises_provider_error() -> None:
    primary = _StaticProvider(
        error=AsrProviderError("asr_unavailable", "primary down", retryable=True)
    )
    fallback = _StaticProvider(result=AsrTranscription(text="fallback", provider="mock"))
    gateway = AsrGateway(primary_provider=primary, fallback_provider=fallback)

    actual = gateway.transcribe(AsrMediaInput(media_ids=["a"], text_hint=None))
    assert actual == AsrTranscription(text="fallback", provider="mock")


def test_gateway_reraises_provider_error_when_no_fallback() -> None:
    expected = AsrProviderError("asr_unavailable", "primary down", retryable=False)
    gateway = AsrGateway(primary_provider=_StaticProvider(error=expected))

    with pytest.raises(AsrProviderError) as excinfo:
        gateway.transcribe(AsrMediaInput(media_ids=["a"], text_hint=None))
    assert excinfo.value is expected
