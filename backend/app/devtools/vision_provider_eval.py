from __future__ import annotations

from app.services.vision_gateway import VisionGateway, get_default_vision_gateway
from app.services.vision_types import VisionMediaInput


def evaluate_vision_file(
    *,
    file_name: str,
    content_type: str,
    image_bytes: bytes,
    gateway: VisionGateway | None = None,
) -> dict[str, object]:
    recognition = (gateway or get_default_vision_gateway()).recognize_product(
        VisionMediaInput(
            media_id=file_name,
            public_url=None,
            content_type=content_type,
            file_name=file_name,
            image_bytes=image_bytes,
        )
    )
    return {
        "provider_name": recognition.provider_name,
        "used_fallback": recognition.used_fallback,
        "candidates": [
            {
                "item_name": candidate.item_name,
                "confidence": candidate.confidence,
                "packaging_hint": candidate.packaging_hint,
            }
            for candidate in recognition.candidates
        ],
    }
