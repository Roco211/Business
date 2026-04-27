from __future__ import annotations

import pytest


def _clear_llm_env(monkeypatch):
    for key in (
        "LLM_PROVIDER",
        "LLM_PROVIDER_NAME",
        "LLM_PROVIDER_API_URL",
        "LLM_PROVIDER_API_KEY",
        "LLM_PROVIDER_MODEL",
        "LLM_API_URL",
        "LLM_API_KEY",
        "LLM_MODEL",
        "VOLCANO_API_URL",
        "VOLCANO_API_KEY",
        "VOLCANO_MODEL",
    ):
        monkeypatch.delenv(key, raising=False)


def test_deepseek_official_defaults_are_used_when_provider_selected(monkeypatch):
    from app.services.llm_real_provider import create_llm_provider

    _clear_llm_env(monkeypatch)
    monkeypatch.setenv("LLM_PROVIDER", "deepseek")
    monkeypatch.setenv("LLM_PROVIDER_API_KEY", "test-key-not-real")

    provider = create_llm_provider(timeout_seconds=9, max_tokens=128, temperature=0.1)

    assert provider.provider_name == "deepseek"
    assert provider.api_url == "https://api.deepseek.com/v1/chat/completions"
    assert provider.model == "deepseek-v4-flash"
    assert provider.timeout_seconds == 9
    assert provider.max_tokens == 128
    assert provider.temperature == 0.1


def test_llm_service_requires_real_provider_instead_of_mock_fallback(monkeypatch):
    from app.services import v2_llm

    _clear_llm_env(monkeypatch)
    monkeypatch.setenv("LLM_PROVIDER", "deepseek")
    v2_llm.reset_llm_service()

    with pytest.raises(ValueError, match="LLM API key required"):
        v2_llm.get_llm_service()


def test_llm_service_uses_real_deepseek_provider_when_configured(monkeypatch):
    from app.services import v2_llm

    _clear_llm_env(monkeypatch)
    monkeypatch.setenv("LLM_PROVIDER", "deepseek")
    monkeypatch.setenv("LLM_PROVIDER_API_KEY", "test-key-not-real")
    monkeypatch.setenv("LLM_PROVIDER_MODEL", "deepseek-v4-flash")
    v2_llm.reset_llm_service()

    service = v2_llm.get_llm_service()

    assert service.provider is not None
    assert service.provider.provider_name == "deepseek"
    assert service.provider.model == "deepseek-v4-flash"
