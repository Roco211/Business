from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import InventoryItem
from app.services.ocr_mock_provider import MockOcrProvider
from app.services.ocr_types import OcrMediaInput


class MockMultimodalValidationError(ValueError):
    pass


@dataclass(frozen=True)
class MockImageRecognition:
    item_name: str
    confidence: float
    quantity: int
    unit: str
    price: float


@dataclass(frozen=True)
class MockInventoryQueryResult:
    item_id: str | None
    item_name: str
    confidence: float
    stock: Decimal | None
    unit: str | None
    is_low_stock: bool | None


@dataclass(frozen=True)
class MockReceiptExtraction:
    document_type: str
    provider_name: str
    raw_text: str
    extracted_fields: dict[str, Any]
    low_confidence_fields: list[str]


_IMAGE_FIXTURES: dict[str, MockImageRecognition] = {
    "image_query_demo": MockImageRecognition(
        item_name="Red Bull 250ml",
        confidence=0.93,
        quantity=2,
        unit="can",
        price=6.5,
    ),
    "image_stock_in_demo": MockImageRecognition(
        item_name="Red Bull 250ml",
        confidence=0.61,
        quantity=2,
        unit="can",
        price=6.5,
    ),
}


def _contains_query_intent(text_hint: str | None, media_id: str) -> bool:
    normalized = (text_hint or "").strip().lower()
    if "query" in media_id or "check" in media_id:
        return True
    return any(phrase in normalized for phrase in ("check", "left", "remaining", "how many", "query"))


def classify_image_task(*, media_ids: list[str], text_hint: str | None) -> str:
    media_id = media_ids[0] if media_ids else ""
    return "photo-stock-query" if _contains_query_intent(text_hint, media_id) else "photo-stock-in"


def recognize_image(*, media_ids: list[str], text_hint: str | None) -> MockImageRecognition:
    if not media_ids:
        raise MockMultimodalValidationError("image media is required")
    media_id = media_ids[0]
    if media_id in _IMAGE_FIXTURES:
        return _IMAGE_FIXTURES[media_id]
    if _contains_query_intent(text_hint, media_id):
        return _IMAGE_FIXTURES["image_query_demo"]
    return _IMAGE_FIXTURES["image_stock_in_demo"]


def recognize_and_query_inventory(
    db_session: Session,
    *,
    shop_id: str,
    media_ids: list[str],
    text_hint: str | None,
) -> MockInventoryQueryResult:
    recognition = recognize_image(media_ids=media_ids, text_hint=text_hint)
    item = db_session.scalar(
        select(InventoryItem).where(
            InventoryItem.shop_id == shop_id,
            InventoryItem.name == recognition.item_name,
            InventoryItem.is_active.is_(True),
        )
    )
    if item is None:
        return MockInventoryQueryResult(
            item_id=None,
            item_name=recognition.item_name,
            confidence=recognition.confidence,
            stock=None,
            unit=None,
            is_low_stock=None,
        )

    is_low_stock = (
        item.low_stock_threshold is not None
        and item.current_stock <= item.low_stock_threshold
    )
    return MockInventoryQueryResult(
        item_id=item.item_id,
        item_name=recognition.item_name,
        confidence=recognition.confidence,
        stock=item.current_stock,
        unit=item.default_unit,
        is_low_stock=is_low_stock,
    )


def extract_receipt(*, media_ids: list[str], text_hint: str | None) -> MockReceiptExtraction:
    del text_hint
    if not media_ids:
        raise MockMultimodalValidationError("receipt media is required")
    media_id = media_ids[0]
    extraction = MockOcrProvider().extract_purchase_receipt(
        OcrMediaInput(
            media_id=media_id,
            public_url=None,
            content_type=None,
            file_name=None,
        )
    )
    return MockReceiptExtraction(
        document_type=extraction.document_type,
        provider_name=extraction.provider_name,
        raw_text=extraction.raw_text or "",
        extracted_fields=dict(extraction.raw_payload),
        low_confidence_fields=list(extraction.low_confidence_fields),
    )
