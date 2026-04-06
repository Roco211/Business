import pytest

from app.core.config import get_settings
from app.services.ocr_gateway import build_ocr_gateway
from app.services.ocr_mock_provider import MockOcrProvider
from app.services.ocr_types import OcrMediaInput, OcrProviderError


def test_build_ocr_gateway_defaults_to_mock() -> None:
    gateway = build_ocr_gateway(get_settings())
    assert isinstance(gateway.primary_provider, MockOcrProvider)


def test_mock_ocr_provider_extracts_fixture_receipt() -> None:
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
