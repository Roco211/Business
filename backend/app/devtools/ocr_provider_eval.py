from __future__ import annotations

import mimetypes
from pathlib import Path
from time import perf_counter
from typing import Callable

from app.services.ocr_gateway import OcrGateway, get_default_ocr_gateway
from app.services.ocr_types import OcrMediaInput


def evaluate_ocr_file(
    *,
    file_name: str,
    content_type: str,
    image_bytes: bytes,
    gateway: OcrGateway | None = None,
    timer: Callable[[], float] = perf_counter,
) -> dict[str, object]:
    started_at = timer()
    extraction = (gateway or get_default_ocr_gateway()).extract_purchase_receipt(
        OcrMediaInput(
            media_id=file_name,
            public_url=None,
            content_type=content_type,
            file_name=file_name,
            image_bytes=image_bytes,
        )
    )
    finished_at = timer()
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
        "latency_ms": max(0, round((finished_at - started_at) * 1000)),
    }


def evaluate_ocr_path(
    *,
    file_path: str | Path,
    gateway: OcrGateway | None = None,
    timer: Callable[[], float] = perf_counter,
) -> dict[str, object]:
    resolved_file_path = Path(file_path)
    if not resolved_file_path.is_file():
        raise FileNotFoundError(resolved_file_path)
    guessed_content_type, _ = mimetypes.guess_type(resolved_file_path.name)
    return evaluate_ocr_file(
        file_name=resolved_file_path.name,
        content_type=guessed_content_type or "application/octet-stream",
        image_bytes=resolved_file_path.read_bytes(),
        gateway=gateway,
        timer=timer,
    )
