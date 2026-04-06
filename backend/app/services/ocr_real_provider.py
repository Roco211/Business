from __future__ import annotations

from base64 import b64encode
from dataclasses import dataclass
from json import JSONDecodeError
from typing import Any

import httpx

from app.services.ocr_types import (
    OcrExtractedLineItem,
    OcrExtraction,
    OcrMediaInput,
    OcrProviderError,
)

RETRYABLE_HTTP_STATUS_CODES = {408, 429}
PERMANENT_REQUEST_ERRORS = (
    httpx.InvalidURL,
    httpx.UnsupportedProtocol,
    httpx.LocalProtocolError,
)


@dataclass(frozen=True)
class RealOcrProvider:
    api_url: str
    api_key: str
    model: str
    timeout_seconds: float

    def extract_purchase_receipt(self, media_input: OcrMediaInput) -> OcrExtraction:
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
            raise OcrProviderError("ocr_unavailable", str(exc), retryable=False) from exc
        except httpx.TimeoutException as exc:
            raise OcrProviderError("ocr_timeout", str(exc), retryable=True) from exc
        except httpx.HTTPError as exc:
            raise OcrProviderError(
                "ocr_unavailable",
                str(exc),
                retryable=self._is_retryable_http_error(exc),
            ) from exc

        try:
            payload = response.json()
        except JSONDecodeError as exc:
            raise OcrProviderError(
                "ocr_unavailable",
                "OCR provider returned an invalid response",
                retryable=False,
            ) from exc

        return self._normalize_extraction(payload)

    def _build_request_payload(self, media_input: OcrMediaInput) -> dict[str, Any]:
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

    def _normalize_extraction(self, payload: object) -> OcrExtraction:
        if not isinstance(payload, dict):
            raise OcrProviderError(
                "ocr_unavailable",
                "OCR provider returned an invalid response",
                retryable=False,
            )

        fields = payload.get("fields")
        normalized_fields = fields if isinstance(fields, dict) else {}
        raw_line_items = self._extract_line_items(payload, normalized_fields)
        if not isinstance(raw_line_items, list) or not raw_line_items:
            raise OcrProviderError(
                "ocr_unavailable",
                "OCR provider response did not include receipt line items",
                retryable=False,
            )

        line_items = [
            OcrExtractedLineItem(
                item_name=self._as_optional_text(raw_item.get("name") or raw_item.get("item_name")),
                quantity=self._as_float(raw_item.get("quantity")),
                unit=self._as_optional_text(raw_item.get("unit")),
                price=self._as_float(raw_item.get("price")),
            )
            for raw_item in raw_line_items
            if isinstance(raw_item, dict)
        ]
        if not line_items:
            raise OcrProviderError(
                "ocr_unavailable",
                "OCR provider response did not include receipt line items",
                retryable=False,
            )

        low_confidence_fields = payload.get("low_confidence_fields")
        provider_name = self._as_optional_text(
            payload.get("provider") or payload.get("provider_name")
        ) or "real-provider"

        return OcrExtraction(
            document_type=self._as_optional_text(payload.get("document_type")) or "purchase-receipt",
            provider_name=provider_name,
            raw_text=self._as_optional_text(payload.get("raw_text") or payload.get("text")),
            line_items=line_items,
            total_amount=self._as_float(
                normalized_fields.get("total_amount") or payload.get("total_amount")
            ),
            low_confidence_fields=[
                value for value in low_confidence_fields if isinstance(value, str)
            ]
            if isinstance(low_confidence_fields, list)
            else [],
            used_fallback=False,
            raw_payload=payload,
        )

    def _extract_line_items(
        self,
        payload: dict[str, object],
        fields: dict[str, object],
    ) -> object:
        for candidate in (
            fields.get("items"),
            fields.get("line_items"),
            payload.get("items"),
            payload.get("line_items"),
        ):
            if candidate is not None:
                return candidate
        return None

    def _as_optional_text(self, value: object) -> str | None:
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        return None

    def _as_float(self, value: object) -> float | None:
        if isinstance(value, bool):
            return None
        if isinstance(value, int | float):
            return float(value)
        if isinstance(value, str):
            try:
                return float(value)
            except ValueError:
                return None
        return None
