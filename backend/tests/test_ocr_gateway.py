import pytest

from app.core.config import get_settings
from app.services.ocr_gateway import OcrGateway, build_ocr_gateway
from app.services.ocr_mock_provider import MockOcrProvider
from app.services.ocr_types import OcrMediaInput, OcrProviderError


def _ensure_mock_provider_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OCR_PROVIDER", "mock")
    monkeypatch.delenv("OCR_PROVIDER_API_URL", raising=False)
    monkeypatch.delenv("OCR_PROVIDER_API_KEY", raising=False)
    monkeypatch.delenv("OCR_PROVIDER_MODEL", raising=False)


def test_build_ocr_gateway_defaults_to_mock(monkeypatch) -> None:
    _ensure_mock_provider_env(monkeypatch)

    gateway = build_ocr_gateway(get_settings())
    assert isinstance(gateway.primary_provider, MockOcrProvider)


def test_mock_ocr_provider_extracts_fixture_receipt(monkeypatch) -> None:
    _ensure_mock_provider_env(monkeypatch)

    gateway = build_ocr_gateway(get_settings())
    extraction = gateway.extract_purchase_receipt(
        OcrMediaInput(
            media_id="receipt_demo",
            public_url="https://mock.example/media/receipt_demo",
            content_type="image/jpeg",
            file_name="receipt.jpg",
        )
    )
    assert extraction.provider_name == "mock-ocr-provider"
    assert extraction.total_amount == 147.0
    assert len(extraction.line_items) == 2


def test_real_ocr_gateway_requires_configuration(monkeypatch) -> None:
    monkeypatch.setenv("OCR_PROVIDER", "real-provider")
    monkeypatch.delenv("OCR_PROVIDER_API_URL", raising=False)
    monkeypatch.delenv("OCR_PROVIDER_API_KEY", raising=False)
    monkeypatch.delenv("OCR_PROVIDER_MODEL", raising=False)

    with pytest.raises(OcrProviderError, match="missing OCR provider configuration"):
        build_ocr_gateway(get_settings())


def test_fallback_provider_flagged_after_retryable_failure() -> None:
    class RetryableProvider:
        def extract_purchase_receipt(self, media_input: OcrMediaInput):
            raise OcrProviderError("ocr_temporary", "temporary failure", retryable=True)

    gateway = OcrGateway(
        primary_provider=RetryableProvider(),
        fallback_provider=MockOcrProvider(),
    )
    extraction = gateway.extract_purchase_receipt(
        OcrMediaInput(
            media_id="receipt_demo",
            public_url="https://mock.example/media/receipt_demo",
            content_type="image/jpeg",
            file_name="receipt.jpg",
        )
    )
    assert extraction.used_fallback is True
