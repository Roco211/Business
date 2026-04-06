from __future__ import annotations

from dataclasses import dataclass
from json import JSONDecodeError
from typing import Any

import httpx

from app.services.asr_types import AsrMediaInput, AsrProviderError, AsrTranscription


@dataclass(frozen=True)
class RealAsrProvider:
    api_url: str
    api_key: str
    model: str
    timeout_seconds: float

    def transcribe(self, media_input: AsrMediaInput) -> AsrTranscription:
        try:
            response = httpx.request(
                "POST",
                self.api_url,
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=self.timeout_seconds,
                json={
                    "media_ids": media_input.media_ids,
                    "text_hint": media_input.text_hint,
                    "model": self.model,
                },
            )
            response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise AsrProviderError("asr_timeout", str(exc), retryable=True) from exc
        except httpx.HTTPError as exc:
            raise AsrProviderError("asr_unavailable", str(exc), retryable=True) from exc

        try:
            payload = response.json()
        except JSONDecodeError as exc:
            raise AsrProviderError(
                "asr_unavailable",
                "ASR provider returned an invalid response",
                retryable=False,
            ) from exc

        return self._normalize_transcription(payload)

    def _normalize_transcription(self, payload: object) -> AsrTranscription:
        if not isinstance(payload, dict):
            raise AsrProviderError(
                "asr_unavailable",
                "ASR provider returned an invalid response",
                retryable=False,
            )

        text = self._extract_text(payload)
        if text is None or not text.strip():
            raise AsrProviderError(
                "asr_unavailable",
                "ASR provider response did not include transcript text",
                retryable=False,
            )

        confidence = payload.get("confidence")
        normalized_confidence = confidence if isinstance(confidence, int | float) else None

        provider = payload.get("provider")
        normalized_provider = provider if isinstance(provider, str) and provider.strip() else "real-provider"

        return AsrTranscription(
            text=text.strip(),
            provider=normalized_provider,
            confidence=float(normalized_confidence) if normalized_confidence is not None else None,
        )

    def _extract_text(self, payload: dict[str, Any]) -> str | None:
        for key in ("text", "transcript"):
            value = payload.get(key)
            if isinstance(value, str):
                return value

        result = payload.get("result")
        if isinstance(result, dict):
            for key in ("text", "transcript"):
                nested_value = result.get(key)
                if isinstance(nested_value, str):
                    return nested_value

        return None
