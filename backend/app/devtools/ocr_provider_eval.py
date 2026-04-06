from __future__ import annotations

from app.services.ocr_gateway import OcrGateway, get_default_ocr_gateway
from app.services.ocr_types import OcrMediaInput


def evaluate_ocr_file(
    *,
    file_name: str,
    content_type: str,
    image_bytes: bytes,
    gateway: OcrGateway | None = None,
) -> dict[str, object]:
    extraction = (gateway or get_default_ocr_gateway()).extract_purchase_receipt(
        OcrMediaInput(
            media_id=file_name,
            public_url=None,
            content_type=content_type,
            file_name=file_name,
            image_bytes=image_bytes,
        )
    )
    return {
        "provider_name": extraction.provider_name,
        "used_fallback": extraction.used_fallback,
        "total_amount": extraction.total_amount,
        "line_items": [
            {
                "item_name": item.item_name,
                "quantity": item.quantity,
                "unit": item.unit,
                "price": item.price,
            }
            for item in extraction.line_items
        ],
        "low_confidence_fields": list(extraction.low_confidence_fields),
    }
