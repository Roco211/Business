from __future__ import annotations

import mimetypes
from pathlib import Path
from time import perf_counter
from typing import Callable

from app.services.vision_gateway import VisionGateway, get_default_vision_gateway
from app.services.vision_types import VisionMediaInput


def evaluate_vision_file(
    *,
    file_name: str,
    content_type: str,
    image_bytes: bytes,
    gateway: VisionGateway | None = None,
    timer: Callable[[], float] = perf_counter,
) -> dict[str, object]:
    started_at = timer()
    recognition = (gateway or get_default_vision_gateway()).recognize_product(
        VisionMediaInput(
            media_id=file_name,
            public_url=None,
            content_type=content_type,
            file_name=file_name,
            image_bytes=image_bytes,
        )
    )
    finished_at = timer()
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
        "latency_ms": max(0, round((finished_at - started_at) * 1000)),
    }


def evaluate_vision_path(
    *,
    file_path: str | Path,
    gateway: VisionGateway | None = None,
    timer: Callable[[], float] = perf_counter,
) -> dict[str, object]:
    resolved_file_path = Path(file_path)
    if not resolved_file_path.is_file():
        raise FileNotFoundError(resolved_file_path)
    guessed_content_type, _ = mimetypes.guess_type(resolved_file_path.name)
    return evaluate_vision_file(
        file_name=resolved_file_path.name,
        content_type=guessed_content_type or "application/octet-stream",
        image_bytes=resolved_file_path.read_bytes(),
        gateway=gateway,
        timer=timer,
    )
