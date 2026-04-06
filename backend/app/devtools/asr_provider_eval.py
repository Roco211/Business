from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from time import perf_counter
from typing import Callable

from app.services.asr_gateway import AsrGateway, get_default_asr_gateway
from app.services.asr_mock_provider import MockAsrProvider
from app.services.asr_types import AsrMediaInput


@dataclass(frozen=True)
class AsrProviderEvalSummary:
    transcript: str
    confidence: float | None
    provider_name: str
    used_fallback: bool
    latency_ms: int

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _did_use_fallback(*, gateway: AsrGateway, provider_name: str) -> bool:
    if gateway.fallback_provider is None:
        return False

    # The current controlled fallback policy only routes retryable failures to the mock provider.
    return provider_name == "mock" and not isinstance(gateway.primary_provider, MockAsrProvider)


def evaluate_asr_provider(
    *,
    audio_path: str | Path,
    media_id: str | None = None,
    text_hint: str | None = None,
    gateway: AsrGateway | None = None,
    timer: Callable[[], float] = perf_counter,
) -> AsrProviderEvalSummary:
    resolved_audio_path = Path(audio_path)
    if not resolved_audio_path.is_file():
        raise FileNotFoundError(resolved_audio_path)

    active_gateway = gateway or get_default_asr_gateway()
    started_at = timer()
    transcription = active_gateway.transcribe(
        AsrMediaInput(
            media_ids=[media_id or resolved_audio_path.stem],
            text_hint=text_hint,
        )
    )
    finished_at = timer()

    return AsrProviderEvalSummary(
        transcript=transcription.text,
        confidence=transcription.confidence,
        provider_name=transcription.provider,
        used_fallback=_did_use_fallback(
            gateway=active_gateway,
            provider_name=transcription.provider,
        ),
        latency_ms=max(0, round((finished_at - started_at) * 1000)),
    )
