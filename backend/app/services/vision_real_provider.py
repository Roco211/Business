from __future__ import annotations

from base64 import b64encode
from dataclasses import dataclass
from json import JSONDecodeError
from typing import Any

import httpx

from app.services.vision_types import (
    VisionCandidate,
    VisionMediaInput,
    VisionProviderError,
    VisionRecognition,
)

RETRYABLE_HTTP_STATUS_CODES = {408, 429}
PERMANENT_REQUEST_ERRORS = (
    httpx.InvalidURL,
    httpx.UnsupportedProtocol,
    httpx.LocalProtocolError,
)


@dataclass(frozen=True)
class RealVisionProvider:
    api_url: str
    api_key: str
    model: str
    timeout_seconds: float

    def recognize_product(self, media_input: VisionMediaInput) -> VisionRecognition:
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
            raise VisionProviderError("vision_unavailable", str(exc), retryable=False) from exc
        except httpx.TimeoutException as exc:
            raise VisionProviderError("vision_timeout", str(exc), retryable=True) from exc
        except httpx.HTTPError as exc:
            raise VisionProviderError(
                "vision_unavailable",
                str(exc),
                retryable=self._is_retryable_http_error(exc),
            ) from exc

        try:
            payload = response.json()
        except JSONDecodeError as exc:
            raise VisionProviderError(
                "vision_unavailable",
                "Vision provider returned an invalid response",
                retryable=False,
            ) from exc

        return self._normalize_recognition(payload)

    def _build_request_payload(self, media_input: VisionMediaInput) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "media_id": media_input.media_id,
            "content_type": media_input.content_type,
            "file_name": media_input.file_name,
            "model": self.model,
        }
        if media_input.public_url:
            payload["media_url"] = media_input.public_url
        if media_input.image_bytes is not None:
            payload["image"] = {
                "file_name": media_input.file_name,
                "content_type": media_input.content_type,
                "base64_data": b64encode(media_input.image_bytes).decode("ascii"),
            }
        return payload

    def _is_retryable_http_error(self, error: httpx.HTTPError) -> bool:
        if not isinstance(error, httpx.HTTPStatusError):
            return True

        status_code = error.response.status_code
        return status_code in RETRYABLE_HTTP_STATUS_CODES or 500 <= status_code < 600

    def _normalize_recognition(self, payload: object) -> VisionRecognition:
        if not isinstance(payload, dict):
            raise VisionProviderError(
                "vision_unavailable",
                "Vision provider returned an invalid response",
                retryable=False,
            )

        raw_candidates = self._extract_candidates(payload)
        if not isinstance(raw_candidates, list) or not raw_candidates:
            raise VisionProviderError(
                "vision_unavailable",
                "Vision provider response did not include recognition candidates",
                retryable=False,
            )

        candidates = [
            VisionCandidate(
                item_name=self._candidate_name(raw_candidate),
                confidence=self._candidate_confidence(raw_candidate),
                packaging_hint=self._as_optional_text(raw_candidate.get("packaging_hint")),
            )
            for raw_candidate in raw_candidates
            if isinstance(raw_candidate, dict) and self._candidate_name(raw_candidate) is not None
        ]
        if not candidates:
            raise VisionProviderError(
                "vision_unavailable",
                "Vision provider response did not include recognition candidates",
                retryable=False,
            )

        provider_name = self._as_optional_text(
            payload.get("provider") or payload.get("provider_name")
        ) or "real-provider"

        return VisionRecognition(
            provider_name=provider_name,
            candidates=candidates,
            used_fallback=False,
            raw_payload=payload,
        )

    def _extract_candidates(self, payload: dict[str, object]) -> object:
        candidates = payload.get("candidates")
        if candidates is not None and candidates != []:
            return candidates

        result = payload.get("result")
        if isinstance(result, dict):
            nested_candidates = result.get("candidates")
            if nested_candidates is not None and nested_candidates != []:
                return nested_candidates
        return None

    def _candidate_name(self, candidate: dict[str, object]) -> str | None:
        return self._as_optional_text(
            candidate.get("item_name") or candidate.get("name") or candidate.get("label")
        )

    def _candidate_confidence(self, candidate: dict[str, object]) -> float:
        value = candidate.get("confidence")
        if isinstance(value, bool):
            return 0.0
        if isinstance(value, int | float):
            return float(value)
        if isinstance(value, str):
            try:
                return float(value)
            except ValueError:
                return 0.0
        return 0.0

    def _as_optional_text(self, value: object) -> str | None:
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        return None
