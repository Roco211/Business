from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import InventoryItem
from app.services.ocr_mock_provider import MockOcrProvider
from app.services.ocr_types import OcrMediaInput
from app.services.vision_mock_provider import (
    MockVisionProvider,
    contains_query_intent,
    select_fixture_media_id,
)
from app.services.vision_types import VisionMediaInput


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


def classify_image_task(*, media_ids: list[str], text_hint: str | None) -> str:
    media_id = media_ids[0] if media_ids else ""
    return "photo-stock-query" if contains_query_intent(text_hint, media_id) else "photo-stock-in"


def recognize_image(*, media_ids: list[str], text_hint: str | None) -> MockImageRecognition:
    if not media_ids:
        raise MockMultimodalValidationError("image media is required")
    media_id = media_ids[0]
    fixture_media_id = select_fixture_media_id(media_id, text_hint)
    recognition = MockVisionProvider().recognize_product(
        VisionMediaInput(
            media_id=fixture_media_id,
            public_url=None,
            content_type=None,
            file_name=None,
        )
    )
    candidate = recognition.candidates[0]
    payload = recognition.raw_payload
    return MockImageRecognition(
        item_name=candidate.item_name,
        confidence=candidate.confidence,
        quantity=int(payload.get("quantity", 1)),
        unit=payload.get("unit") or candidate.packaging_hint or "",
        price=float(payload.get("price", 0.0)),
    )


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
