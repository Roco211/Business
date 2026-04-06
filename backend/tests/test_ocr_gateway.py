import httpx
from importlib import import_module

import pytest

from app.core.config import Settings
from app.services.ocr_gateway import OcrGateway, build_ocr_gateway, get_default_ocr_gateway
from app.services.ocr_mock_provider import MockOcrProvider
from app.services.ocr_types import (
    OcrExtractedLineItem,
    OcrExtraction,
    OcrMediaInput,
    OcrProviderError,
)


def _build_settings(**overrides: object) -> Settings:
    values = {
        "app_env": "test",
        "app_host": "127.0.0.1",
        "app_port": 8001,
        "redis_url": "redis://localhost:6379/0",
        "database_url": "sqlite:///tmp.db",
        "session_stream_keepalive_seconds": 20.0,
        "ocr_provider": "",
        "ocr_provider_api_url": None,
        "ocr_provider_api_key": None,
        "ocr_provider_model": None,
        "ocr_timeout_seconds": 15.0,
        "ocr_allow_mock_fallback": True,
    }
    values.update(overrides)
    return Settings(**values)


class _StaticProvider:
    def __init__(self, *, result: OcrExtraction | None = None, error: OcrProviderError | None = None) -> None:
        self._result = result
        self._error = error

    def extract_purchase_receipt(self, media_input: OcrMediaInput) -> OcrExtraction:
        del media_input
        if self._error is not None:
            raise self._error
        assert self._result is not None
        return self._result


class _HttpxJsonResponse:
    def __init__(self, payload: object, *, status_code: int = 200) -> None:
        self._payload = payload
        self._status_code = status_code
        self._request = httpx.Request("POST", "https://api.example.com/v1/ocr")

    def raise_for_status(self) -> None:
        if self._status_code >= 400:
            raise httpx.HTTPStatusError(
                "request failed",
                request=self._request,
                response=httpx.Response(self._status_code, request=self._request),
            )

    def json(self) -> object:
        return self._payload


def _build_real_gateway(**overrides: object) -> OcrGateway:
    settings_overrides = {
        "ocr_provider": "real-provider",
        "ocr_provider_api_url": "https://api.example.com/v1/ocr",
        "ocr_provider_api_key": "key",
        "ocr_provider_model": "ocr-1",
        "ocr_allow_mock_fallback": False,
    }
    settings_overrides.update(overrides)
    return build_ocr_gateway(_build_settings(**settings_overrides))


def _get_real_provider_type() -> type[object]:
    module = import_module("app.services.ocr_real_provider")
    return module.RealOcrProvider


def test_build_ocr_gateway_defaults_to_mock_when_fallback_allowed() -> None:
    gateway = build_ocr_gateway(_build_settings())
    assert isinstance(gateway.primary_provider, MockOcrProvider)
    assert gateway.fallback_provider is None


def test_real_ocr_provider_missing_configuration_raises_unavailable() -> None:
    with pytest.raises(OcrProviderError) as excinfo:
        build_ocr_gateway(
            _build_settings(
                ocr_provider="real-provider",
                ocr_provider_api_url=None,
                ocr_provider_api_key=None,
                ocr_provider_model=None,
            )
        )

    assert excinfo.value.code == "ocr_unavailable"
    assert str(excinfo.value) == "missing OCR provider configuration"
    assert excinfo.value.retryable is False


def test_real_ocr_provider_with_credentials_builds_gateway() -> None:
    gateway = _build_real_gateway(ocr_timeout_seconds=21.5)
    real_provider_type = _get_real_provider_type()

    assert isinstance(gateway.primary_provider, real_provider_type)
    assert gateway.primary_provider.api_url == "https://api.example.com/v1/ocr"
    assert gateway.primary_provider.api_key == "key"
    assert gateway.primary_provider.model == "ocr-1"
    assert gateway.primary_provider.timeout_seconds == 21.5
    assert gateway.fallback_provider is None


def test_real_ocr_provider_extract_normalizes_http_response(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, str, dict[str, object]]] = []

    def _fake_request(method: str, url: str, **kwargs: object) -> _HttpxJsonResponse:
        calls.append((method, url, dict(kwargs)))
        return _HttpxJsonResponse(
            {
                "provider": "vendor-ocr",
                "document_type": "purchase-receipt",
                "raw_text": "Red Bull x 2",
                "fields": {
                    "items": [
                        {"name": "Red Bull 250ml", "quantity": 2, "unit": "can", "price": 6.5}
                    ],
                    "total_amount": 13.0,
                },
                "low_confidence_fields": ["items[0].price"],
            }
        )

    monkeypatch.setattr(httpx, "request", _fake_request)

    gateway = _build_real_gateway(ocr_timeout_seconds=9.25)

    result = gateway.primary_provider.extract_purchase_receipt(
        OcrMediaInput(
            media_id="receipt_demo",
            public_url="https://example.com/receipt.jpg",
            content_type="image/jpeg",
            file_name="receipt.jpg",
        )
    )

    assert result == OcrExtraction(
        document_type="purchase-receipt",
        provider_name="vendor-ocr",
        raw_text="Red Bull x 2",
        line_items=[
            OcrExtractedLineItem(
                item_name="Red Bull 250ml",
                quantity=2.0,
                unit="can",
                price=6.5,
            )
        ],
        total_amount=13.0,
        low_confidence_fields=["items[0].price"],
        used_fallback=False,
        raw_payload={
            "provider": "vendor-ocr",
            "document_type": "purchase-receipt",
            "raw_text": "Red Bull x 2",
            "fields": {
                "items": [
                    {"name": "Red Bull 250ml", "quantity": 2, "unit": "can", "price": 6.5}
                ],
                "total_amount": 13.0,
            },
            "low_confidence_fields": ["items[0].price"],
        },
    )
    assert calls == [
        (
            "POST",
            "https://api.example.com/v1/ocr",
            {
                "headers": {"Authorization": "Bearer key"},
                "timeout": 9.25,
                "json": {
                    "media_id": "receipt_demo",
                    "media_url": "https://example.com/receipt.jpg",
                    "content_type": "image/jpeg",
                    "file_name": "receipt.jpg",
                    "model": "ocr-1",
                },
            },
        )
    ]


def test_real_ocr_provider_preserves_zero_total_amount(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        httpx,
        "request",
        lambda *args, **kwargs: _HttpxJsonResponse(
            {
                "fields": {
                    "items": [
                        {"name": "Promo Item", "quantity": 1, "unit": "bag", "price": 0}
                    ],
                    "total_amount": 0,
                },
                "total_amount": 42.0,
            }
        ),
    )
    gateway = _build_real_gateway()

    result = gateway.primary_provider.extract_purchase_receipt(
        OcrMediaInput("receipt_zero_total", "https://example.com/r.jpg", "image/jpeg", "r.jpg")
    )

    assert result.total_amount == 0.0


def test_real_ocr_provider_falls_through_empty_items_aliases(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        httpx,
        "request",
        lambda *args, **kwargs: _HttpxJsonResponse(
            {
                "fields": {
                    "items": [],
                    "line_items": [
                        {"name": "Fallback Item", "quantity": 2, "unit": "box", "price": 5.5}
                    ],
                    "total_amount": 11.0,
                }
            }
        ),
    )
    gateway = _build_real_gateway()

    result = gateway.primary_provider.extract_purchase_receipt(
        OcrMediaInput("receipt_alias_fallthrough", "https://example.com/r.jpg", "image/jpeg", "r.jpg")
    )

    assert result.line_items == [
        OcrExtractedLineItem(
            item_name="Fallback Item",
            quantity=2.0,
            unit="box",
            price=5.5,
        )
    ]
    assert result.total_amount == 11.0


def test_real_ocr_provider_extract_includes_inline_image_payload_when_present(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, str, dict[str, object]]] = []

    def _fake_request(method: str, url: str, **kwargs: object) -> _HttpxJsonResponse:
        calls.append((method, url, dict(kwargs)))
        return _HttpxJsonResponse(
            {
                "fields": {
                    "items": [
                        {"name": "Coca Cola 500ml", "quantity": 1, "unit": "bottle", "price": 4.0}
                    ],
                    "total_amount": 4.0,
                }
            }
        )

    monkeypatch.setattr(httpx, "request", _fake_request)

    gateway = _build_real_gateway()

    result = gateway.primary_provider.extract_purchase_receipt(
        OcrMediaInput(
            media_id="receipt_eval",
            public_url=None,
            content_type="image/png",
            file_name="receipt.png",
            image_bytes=b"\x89PNGdemo",
        )
    )

    assert result.total_amount == 4.0
    assert calls == [
        (
            "POST",
            "https://api.example.com/v1/ocr",
            {
                "headers": {"Authorization": "Bearer key"},
                "timeout": 15.0,
                "json": {
                    "media_id": "receipt_eval",
                    "content_type": "image/png",
                    "file_name": "receipt.png",
                    "model": "ocr-1",
                    "image": {
                        "file_name": "receipt.png",
                        "content_type": "image/png",
                        "base64_data": "iVBOR2RlbW8=",
                    },
                },
            },
        )
    ]


def test_real_ocr_provider_maps_timeout_to_retryable_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        httpx,
        "request",
        lambda *args, **kwargs: (_ for _ in ()).throw(httpx.TimeoutException("slow")),
    )
    gateway = _build_real_gateway()

    with pytest.raises(OcrProviderError, match="slow") as excinfo:
        gateway.primary_provider.extract_purchase_receipt(
            OcrMediaInput("receipt_demo", "https://example.com/r.jpg", "image/jpeg", "r.jpg")
        )

    assert excinfo.value.code == "ocr_timeout"
    assert excinfo.value.retryable is True


def test_real_ocr_provider_rejects_invalid_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        httpx,
        "request",
        lambda *args, **kwargs: _HttpxJsonResponse({"fields": {"items": []}}),
    )
    gateway = _build_real_gateway()

    with pytest.raises(OcrProviderError, match="did not include receipt line items") as excinfo:
        gateway.primary_provider.extract_purchase_receipt(
            OcrMediaInput("receipt_demo", "https://example.com/r.jpg", "image/jpeg", "r.jpg")
        )

    assert excinfo.value.code == "ocr_unavailable"
    assert excinfo.value.retryable is False


def test_real_ocr_provider_retryable_http_status_uses_mock_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        httpx,
        "request",
        lambda *args, **kwargs: _HttpxJsonResponse({"detail": "server error"}, status_code=503),
    )
    gateway = _build_real_gateway(ocr_allow_mock_fallback=True)

    result = gateway.extract_purchase_receipt(
        OcrMediaInput(
            media_id="receipt_demo",
            public_url="https://example.com/receipt.jpg",
            content_type="image/jpeg",
            file_name="receipt.jpg",
        )
    )

    assert result.provider_name == "mock-ocr-provider"
    assert result.used_fallback is True


def test_real_ocr_provider_permanent_adapter_error_does_not_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        httpx,
        "request",
        lambda *args, **kwargs: _HttpxJsonResponse({"fields": {"items": []}}),
    )
    gateway = _build_real_gateway(ocr_allow_mock_fallback=True)

    with pytest.raises(OcrProviderError) as excinfo:
        gateway.extract_purchase_receipt(
            OcrMediaInput(
                media_id="receipt_demo",
                public_url="https://example.com/receipt.jpg",
                content_type="image/jpeg",
                file_name="receipt.jpg",
            )
        )

    assert excinfo.value.code == "ocr_unavailable"
    assert excinfo.value.retryable is False


def test_get_default_ocr_gateway_uses_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.delenv("OCR_PROVIDER", raising=False)
    monkeypatch.delenv("OCR_ALLOW_MOCK_FALLBACK", raising=False)
    get_default_ocr_gateway.cache_clear()
    one = get_default_ocr_gateway()
    two = get_default_ocr_gateway()
    assert one is two


def test_gateway_returns_primary_provider_success() -> None:
    expected = OcrExtraction(
        document_type="purchase-receipt",
        provider_name="primary",
        raw_text="ok",
        line_items=[],
        total_amount=None,
        low_confidence_fields=[],
        used_fallback=False,
        raw_payload={},
    )
    gateway = OcrGateway(primary_provider=_StaticProvider(result=expected))

    actual = gateway.extract_purchase_receipt(
        OcrMediaInput("receipt_demo", "https://example.com/receipt.jpg", "image/jpeg", "receipt.jpg")
    )

    assert actual == expected


def test_gateway_uses_fallback_when_primary_raises_retryable_provider_error() -> None:
    primary = _StaticProvider(
        error=OcrProviderError("ocr_unavailable", "primary down", retryable=True)
    )
    fallback = _StaticProvider(
        result=OcrExtraction(
            document_type="purchase-receipt",
            provider_name="mock-ocr-provider",
            raw_text="fallback",
            line_items=[],
            total_amount=10.0,
            low_confidence_fields=[],
            used_fallback=False,
            raw_payload={},
        )
    )
    gateway = OcrGateway(primary_provider=primary, fallback_provider=fallback)

    actual = gateway.extract_purchase_receipt(
        OcrMediaInput("receipt_demo", "https://example.com/receipt.jpg", "image/jpeg", "receipt.jpg")
    )

    assert actual.used_fallback is True
    assert actual.provider_name == "mock-ocr-provider"


def test_gateway_does_not_use_fallback_for_non_retryable_provider_error() -> None:
    expected = OcrProviderError("ocr_unavailable", "primary malformed", retryable=False)
    fallback = _StaticProvider(
        result=OcrExtraction(
            document_type="purchase-receipt",
            provider_name="mock-ocr-provider",
            raw_text="fallback",
            line_items=[],
            total_amount=10.0,
            low_confidence_fields=[],
            used_fallback=False,
            raw_payload={},
        )
    )
    gateway = OcrGateway(primary_provider=_StaticProvider(error=expected), fallback_provider=fallback)

    with pytest.raises(OcrProviderError) as excinfo:
        gateway.extract_purchase_receipt(
            OcrMediaInput("receipt_demo", "https://example.com/receipt.jpg", "image/jpeg", "receipt.jpg")
        )

    assert excinfo.value is expected
