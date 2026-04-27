from __future__ import annotations

import json


def test_provider_trial_preflight_reports_missing_config_without_secrets(monkeypatch):
    from app.devtools.provider_trial_preflight import run_provider_trial_preflight

    for key in (
        "LLM_PROVIDER",
        "LLM_PROVIDER_API_URL",
        "LLM_PROVIDER_API_KEY",
        "LLM_PROVIDER_MODEL",
        "LLM_API_URL",
        "LLM_API_KEY",
        "LLM_MODEL",
        "VOLCANO_API_URL",
        "VOLCANO_API_KEY",
        "VOLCANO_MODEL",
        "RUN_REAL_PROVIDER_TRIAL",
    ):
        monkeypatch.delenv(key, raising=False)

    result = run_provider_trial_preflight(environ={})
    payload = result.to_dict()

    assert payload["overall_status"] == "degraded"
    assert payload["network_trial"] == "skipped"
    assert "missing_api_key" in payload["reasons"]
    assert "missing_model" not in payload["reasons"]
    assert payload["config"]["provider"] == "deepseek"
    assert payload["config"]["model"] == "deepseek-v4-flash"
    assert "api_key_present" in payload["config"]
    dumped = json.dumps(payload, ensure_ascii=False)
    assert "sk-" not in dumped
    assert "secret" not in dumped.lower()


def test_provider_trial_preflight_redacts_config_and_runs_only_when_explicitly_enabled():
    from app.devtools.provider_trial_preflight import run_provider_trial_preflight

    secret_key = "dummy-provider-token-value-that-must-not-appear"
    environ = {
        "LLM_PROVIDER": "volcano",
        "LLM_PROVIDER_API_URL": "https://ark.cn-beijing.volces.com/api/v3/chat/completions",
        "LLM_PROVIDER_API_KEY": secret_key,
        "LLM_PROVIDER_MODEL": "ep-20260416043519-v4vzq",
        "LLM_TIMEOUT_SECONDS": "12",
        "LLM_MAX_TOKENS": "64",
        "LLM_TEMPERATURE": "0.2",
    }

    dry_run = run_provider_trial_preflight(environ=environ)
    dry_payload = dry_run.to_dict()
    assert dry_payload["overall_status"] == "ready"
    assert dry_payload["network_trial"] == "skipped"
    assert dry_payload["config"]["api_key_present"] == "yes"
    assert secret_key not in json.dumps(dry_payload, ensure_ascii=False)

    calls: list[dict[str, object]] = []

    def fake_chat_probe(**kwargs):
        calls.append(kwargs)
        assert kwargs["api_key"] == secret_key
        return {"ok": True, "latency_ms": 123.4, "content_length": 2}

    live_payload = run_provider_trial_preflight(
        environ={**environ, "RUN_REAL_PROVIDER_TRIAL": "1"},
        chat_probe=fake_chat_probe,
    ).to_dict()

    assert live_payload["overall_status"] == "ready"
    assert live_payload["network_trial"] == "passed"
    assert live_payload["probe"]["latency_ms"] == 123.4
    assert calls and calls[0]["model"] == "ep-20260416043519-v4vzq"
    assert secret_key not in json.dumps(live_payload, ensure_ascii=False)
