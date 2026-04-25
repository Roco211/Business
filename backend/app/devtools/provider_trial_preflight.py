from __future__ import annotations

from dataclasses import asdict, dataclass, field
import os
import time
from typing import Callable, Mapping, Any

from app.services.llm_real_provider import LLMProviderError, OpenAILLMProvider, _ensure_chat_completions_url

READY_STATUS = "ready"
DEGRADED_STATUS = "degraded"
SKIPPED_STATUS = "skipped"
PASSED_STATUS = "passed"
FAILED_STATUS = "failed"

ProviderProbe = Callable[..., dict[str, object]]


@dataclass(frozen=True)
class ProviderTrialPreflightSummary:
    overall_status: str
    provider: str
    network_trial: str
    config: dict[str, str]
    reasons: list[str] = field(default_factory=list)
    probe: dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _env(environ: Mapping[str, str], *names: str) -> str:
    for name in names:
        value = environ.get(name)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _truthy(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _safe_url_label(url: str) -> str:
    if not url:
        return "missing"
    return _ensure_chat_completions_url(url)


def _default_chat_probe(**kwargs: object) -> dict[str, object]:
    provider = OpenAILLMProvider(
        api_url=str(kwargs["api_url"]),
        api_key=str(kwargs["api_key"]),
        model=str(kwargs["model"]),
        provider_name=str(kwargs["provider"]),
        timeout_seconds=float(kwargs["timeout_seconds"]),
        max_tokens=int(kwargs["max_tokens"]),
        temperature=float(kwargs["temperature"]),
    )
    try:
        started = time.monotonic()
        response = provider.chat(
            [
                {"role": "system", "content": "你是库存助手。只回复OK。"},
                {"role": "user", "content": "请回复OK"},
            ],
            stream=False,
        )
        latency_ms = round((time.monotonic() - started) * 1000, 2)
        return {
            "ok": True,
            "latency_ms": latency_ms,
            "content_length": len(response.content or ""),
            "tokens_prompt": response.stats.tokens_prompt if response.stats else 0,
            "tokens_completion": response.stats.tokens_completion if response.stats else 0,
        }
    finally:
        provider.close()


def run_provider_trial_preflight(
    *,
    environ: Mapping[str, str] | None = None,
    chat_probe: ProviderProbe | None = None,
) -> ProviderTrialPreflightSummary:
    """Check real LLM provider readiness without exposing credentials.

    This function intentionally reads only the supplied mapping or os.environ. It does not
    import app.core.config and therefore does not load backend/.env implicitly.
    """
    source = environ if environ is not None else os.environ
    provider = _env(source, "LLM_PROVIDER", "LLM_PROVIDER_NAME") or "mock"
    api_url = _env(source, "LLM_PROVIDER_API_URL", "LLM_API_URL", "VOLCANO_API_URL")
    api_key = _env(source, "LLM_PROVIDER_API_KEY", "LLM_API_KEY", "VOLCANO_API_KEY")
    model = _env(source, "LLM_PROVIDER_MODEL", "LLM_MODEL", "VOLCANO_MODEL")
    timeout_seconds = float(_env(source, "LLM_TIMEOUT_SECONDS") or "30")
    max_tokens = int(_env(source, "LLM_MAX_TOKENS") or "128")
    temperature = float(_env(source, "LLM_TEMPERATURE") or "0.2")
    network_enabled = _truthy(_env(source, "RUN_REAL_PROVIDER_TRIAL"))

    reasons: list[str] = []
    if provider.strip().lower() == "mock":
        reasons.append("mock_provider_selected")
    if not api_key:
        reasons.append("missing_api_key")
    if not model:
        reasons.append("missing_model")

    normalized_url = _safe_url_label(api_url)
    config = {
        "provider": provider,
        "api_url": normalized_url,
        "api_key_present": "yes" if api_key else "no",
        "model": model or "missing",
        "timeout_seconds": str(timeout_seconds).rstrip("0").rstrip("."),
        "max_tokens": str(max_tokens),
        "temperature": str(temperature).rstrip("0").rstrip("."),
    }

    if reasons:
        return ProviderTrialPreflightSummary(
            overall_status=DEGRADED_STATUS,
            provider=provider,
            network_trial=SKIPPED_STATUS,
            config=config,
            reasons=reasons,
        )

    if not network_enabled:
        return ProviderTrialPreflightSummary(
            overall_status=READY_STATUS,
            provider=provider,
            network_trial=SKIPPED_STATUS,
            config=config,
            reasons=[],
        )

    probe = chat_probe or _default_chat_probe
    try:
        probe_result = probe(
            provider=provider,
            api_url=normalized_url,
            api_key=api_key,
            model=model,
            timeout_seconds=timeout_seconds,
            max_tokens=max_tokens,
            temperature=temperature,
        )
    except (LLMProviderError, ValueError, OSError, RuntimeError) as exc:
        return ProviderTrialPreflightSummary(
            overall_status=DEGRADED_STATUS,
            provider=provider,
            network_trial=FAILED_STATUS,
            config=config,
            reasons=["provider_probe_failed"],
            probe={"error_type": exc.__class__.__name__},
        )

    safe_probe = {
        key: value
        for key, value in probe_result.items()
        if key not in {"api_key", "authorization", "headers", "request_body", "response_body"}
    }
    return ProviderTrialPreflightSummary(
        overall_status=READY_STATUS,
        provider=provider,
        network_trial=PASSED_STATUS,
        config=config,
        reasons=[],
        probe=safe_probe,
    )
