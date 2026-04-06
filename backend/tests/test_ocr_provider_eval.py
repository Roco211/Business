import importlib.util
import json
from pathlib import Path

import pytest

from app.services.ocr_gateway import OcrGateway
from app.services.ocr_mock_provider import MockOcrProvider
from app.services.ocr_types import (
    OcrExtractedLineItem,
    OcrExtraction,
    OcrMediaInput,
    OcrProviderError,
)


class _RecordingProvider:
    def __init__(self, result: OcrExtraction) -> None:
        self.calls: list[OcrMediaInput] = []
        self._result = result

    def extract_purchase_receipt(self, media_input: OcrMediaInput) -> OcrExtraction:
        self.calls.append(media_input)
        return self._result


class _RetryableFailureProvider:
    def extract_purchase_receipt(self, media_input: OcrMediaInput) -> OcrExtraction:
        del media_input
        raise OcrProviderError("ocr_timeout", "temporary upstream failure", retryable=True)


def _load_cli_module():
    module_path = Path(__file__).resolve().parents[1] / "scripts" / "evaluate_real_ocr.py"
    spec = importlib.util.spec_from_file_location("evaluate_real_ocr_script", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_evaluate_ocr_file_returns_compact_summary(tmp_path) -> None:
    from app.devtools.ocr_provider_eval import evaluate_ocr_file

    image_path = tmp_path / "receipt.jpg"
    image_bytes = b"demo image"
    image_path.write_bytes(image_bytes)
    provider = _RecordingProvider(
        OcrExtraction(
            document_type="purchase-receipt",
            provider_name="stub-ocr",
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
            raw_payload={"provider": "stub-ocr"},
        )
    )

    result = evaluate_ocr_file(
        file_name=image_path.name,
        content_type="image/jpeg",
        image_bytes=image_bytes,
        gateway=OcrGateway(primary_provider=provider),
    )

    assert provider.calls == [
        OcrMediaInput(
            media_id="receipt.jpg",
            public_url=None,
            content_type="image/jpeg",
            file_name="receipt.jpg",
            image_bytes=image_bytes,
        )
    ]
    assert result == {
        "provider_name": "stub-ocr",
        "used_fallback": False,
        "total_amount": 13.0,
        "line_items": [
            {
                "item_name": "Red Bull 250ml",
                "quantity": 2.0,
                "unit": "can",
                "price": 6.5,
            }
        ],
        "low_confidence_fields": ["items[0].price"],
    }


def test_evaluate_ocr_file_marks_mock_fallback_usage() -> None:
    from app.devtools.ocr_provider_eval import evaluate_ocr_file

    result = evaluate_ocr_file(
        file_name="receipt.jpg",
        content_type="image/jpeg",
        image_bytes=b"demo image",
        gateway=OcrGateway(
            primary_provider=_RetryableFailureProvider(),
            fallback_provider=MockOcrProvider(),
        ),
    )

    assert result["provider_name"] == "mock-ocr-provider"
    assert result["used_fallback"] is True


def test_cli_prints_compact_json_summary(tmp_path, capsys, monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load_cli_module()
    image_path = tmp_path / "receipt.jpg"
    image_bytes = b"demo image"
    image_path.write_bytes(image_bytes)

    expected_payload = {
        "provider_name": "stub-ocr",
        "used_fallback": False,
        "total_amount": 13.0,
        "line_items": [{"item_name": "Red Bull 250ml", "quantity": 2.0, "unit": "can", "price": 6.5}],
        "low_confidence_fields": [],
    }

    def _fake_evaluate_ocr_file(*, file_name: str, content_type: str, image_bytes: bytes):
        assert file_name == "receipt.jpg"
        assert content_type == "image/jpeg"
        assert image_bytes == image_bytes_arg
        return expected_payload

    image_bytes_arg = image_bytes
    monkeypatch.setattr(module, "evaluate_ocr_file", _fake_evaluate_ocr_file)

    exit_code = module.main([str(image_path)])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert json.loads(captured.out) == expected_payload
    assert captured.err == ""
    assert captured.out.count("\n") == 1


def test_cli_reports_missing_file(capsys) -> None:
    module = _load_cli_module()
    missing_path = Path("C:/missing/receipt.jpg")

    exit_code = module.main([str(missing_path)])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "OCR evaluation failed" in captured.err
    assert captured.out == ""
