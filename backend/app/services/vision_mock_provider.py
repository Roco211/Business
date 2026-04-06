from __future__ import annotations

from typing import Mapping

from app.services.vision_types import VisionCandidate, VisionMediaInput, VisionRecognition

_PROVIDER_NAME = "mock-vision-provider"

_IMAGE_FIXTURES: Mapping[str, Mapping[str, object]] = {
    "image_query_demo": {
        "item_name": "Red Bull 250ml",
        "confidence": 0.93,
        "packaging_hint": "can",
        "quantity": 2,
        "unit": "can",
        "price": 6.5,
    },
    "image_stock_in_demo": {
        "item_name": "Red Bull 250ml",
        "confidence": 0.61,
        "packaging_hint": "can",
        "quantity": 2,
        "unit": "can",
        "price": 6.5,
    },
}


_FIXTURE_MEDIA_IDS = frozenset(_IMAGE_FIXTURES.keys())


def contains_query_intent(text_hint: str | None, media_id: str) -> bool:
    normalized_hint = (text_hint or "").strip().lower()
    if "query" in media_id or "check" in media_id:
        return True
    return any(
        phrase in normalized_hint
        for phrase in ("check", "left", "remaining", "how many", "query")
    )


def _select_fixture(media_id: str) -> Mapping[str, object]:
    return _IMAGE_FIXTURES.get(media_id, _IMAGE_FIXTURES["image_stock_in_demo"])


def select_fixture_media_id(media_id: str, text_hint: str | None) -> str:
    if media_id in _FIXTURE_MEDIA_IDS:
        return media_id
    if contains_query_intent(text_hint, media_id):
        return "image_query_demo"
    return "image_stock_in_demo"


class MockVisionProvider:
    def recognize_product(self, media_input: VisionMediaInput) -> VisionRecognition:
        fixture = _select_fixture(media_input.media_id)
        candidate = VisionCandidate(
            item_name=fixture["item_name"],  # type: ignore[arg-type]
            confidence=float(fixture["confidence"]),  # type: ignore[arg-type]
            packaging_hint=fixture.get("packaging_hint"),  # type: ignore[arg-type]
        )
        return VisionRecognition(
            provider_name=_PROVIDER_NAME,
            candidates=[candidate],
            used_fallback=False,
            raw_payload={"media_id": media_input.media_id, **fixture},
        )
