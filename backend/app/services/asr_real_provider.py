from __future__ import annotations

from base64 import b64encode
from dataclasses import dataclass
from json import JSONDecodeError
from typing import Any

import httpx

from app.services.asr_types import AsrMediaInput, AsrProviderError, AsrTranscription

RETRYABLE_HTTP_STATUS_CODES = {408, 429}
PERMANENT_REQUEST_ERRORS = (
    httpx.InvalidURL,
    httpx.UnsupportedProtocol,
    httpx.LocalProtocolError,
)


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
                json=self._build_request_payload(media_input),
            )
            response.raise_for_status()
        except PERMANENT_REQUEST_ERRORS as exc:
            raise AsrProviderError("asr_unavailable", str(exc), retryable=False) from exc
        except httpx.TimeoutException as exc:
            raise AsrProviderError("asr_timeout", str(exc), retryable=True) from exc
        except httpx.HTTPError as exc:
            raise AsrProviderError(
                "asr_unavailable",
                str(exc),
                retryable=self._is_retryable_http_error(exc),
            ) from exc

        try:
            payload = response.json()
        except JSONDecodeError as exc:
            raise AsrProviderError(
                "asr_unavailable",
                "ASR provider returned an invalid response",
                retryable=False,
            ) from exc

        return self._normalize_transcription(payload)

    def _build_request_payload(self, media_input: AsrMediaInput) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "media_ids": media_input.media_ids,
            "text_hint": media_input.text_hint,
            "model": self.model,
        }
        if media_input.audio_bytes is not None:
            payload["audio"] = {
                "file_name": media_input.file_name,
                "content_type": media_input.content_type,
                "base64_data": b64encode(media_input.audio_bytes).decode("ascii"),
            }
        return payload

    def _is_retryable_http_error(self, error: httpx.HTTPError) -> bool:
        if not isinstance(error, httpx.HTTPStatusError):
            return True

        status_code = error.response.status_code
        return status_code in RETRYABLE_HTTP_STATUS_CODES or 500 <= status_code < 600

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
