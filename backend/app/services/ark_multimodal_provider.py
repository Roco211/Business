from __future__ import annotations

import json
import re
from base64 import b64encode
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import httpx

from app.services.asr_types import AsrMediaInput, AsrProviderError, AsrTranscription
from app.services.ocr_types import OcrExtractedLineItem, OcrExtraction, OcrMediaInput, OcrProviderError
from app.services.vision_types import VisionCandidate, VisionMediaInput, VisionProviderError, VisionRecognition

ARK_CHAT_COMPLETIONS_URL = "https://ark.cn-beijing.volces.com/api/v3/chat/completions"
RETRYABLE_HTTP_STATUS_CODES = {408, 429}
PERMANENT_REQUEST_ERRORS = (
    httpx.InvalidURL,
    httpx.UnsupportedProtocol,
    httpx.LocalProtocolError,
)


def _data_url(content_type: str | None, payload: bytes, default_content_type: str) -> str:
    return f"data:{content_type or default_content_type};base64,{b64encode(payload).decode('ascii')}"


def _extract_json_object(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?\s*", "", stripped)
        stripped = re.sub(r"\s*```$", "", stripped)
    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]*\}", stripped)
        if not match:
            raise
        parsed = json.loads(match.group(0))
    if not isinstance(parsed, dict):
        raise ValueError("assistant content is not a JSON object")
    return parsed


def _as_optional_text(value: object) -> str | None:
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return None


def _as_float(value: object) -> float | None:
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


def _confidence(value: object, default: float = 0.0) -> float:
    parsed = _as_float(value)
    if parsed is None:
        return default
    return max(0.0, min(1.0, parsed))


def _http_error_message(exc: httpx.HTTPError) -> str:
    if isinstance(exc, httpx.HTTPStatusError):
        return f"{exc}; response={exc.response.text[:1000]}"
    return str(exc)


@dataclass(frozen=True)
class _ArkChatClient:
    api_url: str
    api_key: str
    model: str
    timeout_seconds: float

    def complete_json(self, *, system_prompt: str, user_content: str | list[dict[str, Any]], max_tokens: int = 700) -> dict[str, Any]:
        try:
            response = httpx.request(
                "POST",
                self.api_url or ARK_CHAT_COMPLETIONS_URL,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                timeout=self.timeout_seconds,
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_content},
                    ],
                    "temperature": 0.1,
                    "max_tokens": max_tokens,
                },
            )
            response.raise_for_status()
            payload = response.json()
        except PERMANENT_REQUEST_ERRORS:
            raise
        except httpx.HTTPError:
            raise
        except json.JSONDecodeError as exc:
            raise ValueError("Ark provider returned invalid JSON response") from exc

        content = self._assistant_content(payload)
        result = _extract_json_object(content)
        result.setdefault("raw_assistant_content", content)
        result.setdefault("raw_usage", payload.get("usage") if isinstance(payload, dict) else None)
        return result

    def _assistant_content(self, payload: object) -> str:
        if not isinstance(payload, dict):
            raise ValueError("Ark provider returned invalid response")
        choices = payload.get("choices")
        if not isinstance(choices, list) or not choices:
            raise ValueError("Ark provider response did not include choices")
        first = choices[0]
        if not isinstance(first, dict):
            raise ValueError("Ark provider response included invalid choice")
        message = first.get("message")
        if not isinstance(message, dict):
            raise ValueError("Ark provider response did not include message")
        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            raise ValueError("Ark provider response did not include assistant content")
        return content

    def is_retryable_http_error(self, error: httpx.HTTPError) -> bool:
        if not isinstance(error, httpx.HTTPStatusError):
            return True
        status_code = error.response.status_code
        return status_code in RETRYABLE_HTTP_STATUS_CODES or 500 <= status_code < 600


@dataclass(frozen=True)
class ArkOcrProvider:
    api_url: str
    api_key: str
    model: str
    timeout_seconds: float

    def extract_purchase_receipt(self, media_input: OcrMediaInput) -> OcrExtraction:
        client = _ArkChatClient(self.api_url, self.api_key, self.model, self.timeout_seconds)
        try:
            payload = client.complete_json(
                system_prompt=(
                    "你是五金店进货单OCR引擎。识别图片中的采购/进货单文字和明细。"
                    "只返回JSON，不要解释。格式："
                    '{"document_type":"purchase-receipt","raw_text":"...",'
                    '"items":[{"name":"商品名","quantity":1,"unit":"个","price":1.0}],'
                    '"total_amount":1.0,"low_confidence_fields":[],"confidence":0.9}'
                ),
                user_content=self._build_user_content(media_input),
            )
        except PERMANENT_REQUEST_ERRORS as exc:
            raise OcrProviderError("ocr_unavailable", str(exc), retryable=False) from exc
        except httpx.TimeoutException as exc:
            raise OcrProviderError("ocr_timeout", str(exc), retryable=True) from exc
        except httpx.HTTPError as exc:
            raise OcrProviderError(
                "ocr_unavailable",
                _http_error_message(exc),
                retryable=client.is_retryable_http_error(exc),
            ) from exc
        except (ValueError, json.JSONDecodeError) as exc:
            raise OcrProviderError("ocr_unavailable", str(exc), retryable=False) from exc

        items = payload.get("items") or payload.get("line_items")
        if not isinstance(items, list) or not items:
            raise OcrProviderError("ocr_unavailable", "Ark OCR response did not include receipt line items", retryable=False)
        line_items = [
            OcrExtractedLineItem(
                item_name=_as_optional_text(item.get("name") or item.get("item_name")),
                quantity=_as_float(item.get("quantity")),
                unit=_as_optional_text(item.get("unit")),
                price=_as_float(item.get("price")),
            )
            for item in items
            if isinstance(item, dict)
        ]
        if not line_items:
            raise OcrProviderError("ocr_unavailable", "Ark OCR response did not include valid receipt line items", retryable=False)
        low_confidence_fields = payload.get("low_confidence_fields")
        return OcrExtraction(
            document_type=_as_optional_text(payload.get("document_type")) or "purchase-receipt",
            provider_name="ark-doubao",
            raw_text=_as_optional_text(payload.get("raw_text") or payload.get("text")),
            line_items=line_items,
            total_amount=_as_float(payload.get("total_amount")),
            low_confidence_fields=[v for v in low_confidence_fields if isinstance(v, str)] if isinstance(low_confidence_fields, list) else [],
            used_fallback=False,
            raw_payload={"provider": "ark-doubao", **payload},
        )

    def _build_user_content(self, media_input: OcrMediaInput) -> list[dict[str, Any]]:
        content: list[dict[str, Any]] = [{"type": "text", "text": "请OCR识别这张五金店进货/采购单，抽取商品明细、数量、单位、单价和总金额。"}]
        image_url = media_input.public_url
        if media_input.image_bytes is not None:
            image_url = _data_url(media_input.content_type, media_input.image_bytes, "image/jpeg")
        if not image_url:
            raise OcrProviderError("ocr_unavailable", "OCR media input does not include image bytes or public URL", retryable=False)
        content.append({"type": "image_url", "image_url": {"url": image_url}})
        return content


@dataclass(frozen=True)
class ArkVisionProvider:
    api_url: str
    api_key: str
    model: str
    timeout_seconds: float

    def recognize_product(self, media_input: VisionMediaInput) -> VisionRecognition:
        client = _ArkChatClient(self.api_url, self.api_key, self.model, self.timeout_seconds)
        try:
            payload = client.complete_json(
                system_prompt=(
                    "你是五金店商品视觉识别引擎。识别图片中的商品、包装规格和置信度。"
                    "只返回JSON，不要解释。格式："
                    '{"candidates":[{"name":"商品名","confidence":0.9,"packaging_hint":"包装/规格"}]}'
                ),
                user_content=self._build_user_content(media_input),
            )
        except PERMANENT_REQUEST_ERRORS as exc:
            raise VisionProviderError("vision_unavailable", str(exc), retryable=False) from exc
        except httpx.TimeoutException as exc:
            raise VisionProviderError("vision_timeout", str(exc), retryable=True) from exc
        except httpx.HTTPError as exc:
            raise VisionProviderError(
                "vision_unavailable",
                _http_error_message(exc),
                retryable=client.is_retryable_http_error(exc),
            ) from exc
        except (ValueError, json.JSONDecodeError) as exc:
            raise VisionProviderError("vision_unavailable", str(exc), retryable=False) from exc

        raw_candidates = payload.get("candidates")
        if not isinstance(raw_candidates, list) or not raw_candidates:
            raise VisionProviderError("vision_unavailable", "Ark Vision response did not include candidates", retryable=False)
        candidates = [
            VisionCandidate(
                item_name=_as_optional_text(candidate.get("name") or candidate.get("item_name") or candidate.get("label")) or "未知商品",
                confidence=_confidence(candidate.get("confidence")),
                packaging_hint=_as_optional_text(candidate.get("packaging_hint") or candidate.get("spec")),
            )
            for candidate in raw_candidates
            if isinstance(candidate, dict)
        ]
        if not candidates:
            raise VisionProviderError("vision_unavailable", "Ark Vision response did not include valid candidates", retryable=False)
        return VisionRecognition(
            provider_name="ark-doubao",
            candidates=candidates,
            used_fallback=False,
            raw_payload={"provider": "ark-doubao", **payload},
        )

    def _build_user_content(self, media_input: VisionMediaInput) -> list[dict[str, Any]]:
        content: list[dict[str, Any]] = [{"type": "text", "text": "请识别图片中的五金/零售商品，给出候选商品名、规格包装提示和0到1置信度。"}]
        image_url = media_input.public_url
        if media_input.image_bytes is not None:
            image_url = _data_url(media_input.content_type, media_input.image_bytes, "image/jpeg")
        if not image_url:
            raise VisionProviderError("vision_unavailable", "Vision media input does not include image bytes or public URL", retryable=False)
        content.append({"type": "image_url", "image_url": {"url": image_url}})
        return content


@dataclass(frozen=True)
class ArkAsrProvider:
    api_url: str
    api_key: str
    model: str
    timeout_seconds: float

    def transcribe(self, media_input: AsrMediaInput) -> AsrTranscription:
        client = _ArkChatClient(self.api_url, self.api_key, self.model, self.timeout_seconds)
        try:
            payload = client.complete_json(
                system_prompt=(
                    "你是五金店语音转写引擎。转写音频中的中文/中英混合口语。"
                    "只返回JSON，不要解释。格式：{\"text\":\"转写内容\",\"confidence\":0.9}"
                ),
                user_content=self._build_user_content(media_input),
                max_tokens=400,
            )
        except PERMANENT_REQUEST_ERRORS as exc:
            raise AsrProviderError("asr_unavailable", str(exc), retryable=False) from exc
        except httpx.TimeoutException as exc:
            raise AsrProviderError("asr_timeout", str(exc), retryable=True) from exc
        except httpx.HTTPError as exc:
            raise AsrProviderError(
                "asr_unavailable",
                _http_error_message(exc),
                retryable=client.is_retryable_http_error(exc),
            ) from exc
        except (ValueError, json.JSONDecodeError) as exc:
            raise AsrProviderError("asr_unavailable", str(exc), retryable=False) from exc

        text = _as_optional_text(payload.get("text") or payload.get("transcript"))
        if not text:
            raise AsrProviderError("asr_unavailable", "Ark ASR response did not include transcript text", retryable=False)
        return AsrTranscription(text=text, provider="ark-doubao", confidence=_confidence(payload.get("confidence")))

    def _build_user_content(self, media_input: AsrMediaInput) -> list[dict[str, Any]]:
        content: list[dict[str, Any]] = [{"type": "text", "text": media_input.text_hint or "请转写这段音频。"}]
        audio_bytes = media_input.audio_bytes
        if audio_bytes is None and media_input.media_urls:
            audio_bytes = self._download_audio(media_input.media_urls[0])
        if audio_bytes is None:
            raise AsrProviderError("asr_unavailable", "ASR media input does not include audio bytes or downloadable URL", retryable=False)
        content.append(
            {
                "type": "input_audio",
                "input_audio": {
                    "data": b64encode(audio_bytes).decode("ascii"),
                    "format": self._audio_format(media_input.file_name, media_input.content_type),
                },
            }
        )
        return content

    def _download_audio(self, url: str) -> bytes:
        try:
            response = httpx.get(url, timeout=min(self.timeout_seconds, 30.0))
            response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise AsrProviderError("asr_timeout", str(exc), retryable=True) from exc
        except httpx.HTTPError as exc:
            retryable = True
            if isinstance(exc, httpx.HTTPStatusError):
                status_code = exc.response.status_code
                retryable = status_code in RETRYABLE_HTTP_STATUS_CODES or 500 <= status_code < 600
            raise AsrProviderError("asr_unavailable", str(exc), retryable=retryable) from exc
        return response.content

    def _audio_format(self, file_name: str | None, content_type: str | None) -> str:
        if content_type:
            lowered = content_type.lower()
            if "wav" in lowered:
                return "wav"
            if "mpeg" in lowered or "mp3" in lowered:
                return "mp3"
            if "m4a" in lowered or "mp4" in lowered:
                return "mp4"
        suffix = Path(file_name or "").suffix.lower().lstrip(".")
        if suffix in {"wav", "mp3", "mp4", "m4a"}:
            return "mp4" if suffix == "m4a" else suffix
        return "wav"
