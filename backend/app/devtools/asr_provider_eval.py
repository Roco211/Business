from __future__ import annotations

from dataclasses import asdict, dataclass
import mimetypes
from pathlib import Path
from time import perf_counter
from typing import Callable

from app.services.asr_gateway import AsrGateway, get_default_asr_gateway
from app.services.asr_mock_provider import MockAsrProvider
from app.services.asr_types import AsrMediaInput

CONTENT_TYPE_OVERRIDES = {
    ".m4a": "audio/m4a",
    ".mp3": "audio/mpeg",
    ".wav": "audio/wav",
}


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


def _infer_content_type(audio_path: Path) -> str:
    suffix = audio_path.suffix.lower()
    if suffix in CONTENT_TYPE_OVERRIDES:
        return CONTENT_TYPE_OVERRIDES[suffix]
    guessed_content_type, _ = mimetypes.guess_type(audio_path.name)
    return guessed_content_type or "application/octet-stream"


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
    audio_bytes = resolved_audio_path.read_bytes()

    active_gateway = gateway or get_default_asr_gateway()
    started_at = timer()
    transcription = active_gateway.transcribe(
        AsrMediaInput(
            media_ids=[media_id or resolved_audio_path.stem],
            text_hint=text_hint,
            file_name=resolved_audio_path.name,
            content_type=_infer_content_type(resolved_audio_path),
            audio_bytes=audio_bytes,
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


def evaluate_asr_file(
    *,
    audio_path: str | Path,
    media_id: str | None = None,
    text_hint: str | None = None,
    gateway: AsrGateway | None = None,
    timer: Callable[[], float] = perf_counter,
) -> dict[str, object]:
    return evaluate_asr_provider(
        audio_path=audio_path,
        media_id=media_id,
        text_hint=text_hint,
        gateway=gateway,
        timer=timer,
    ).to_dict()
