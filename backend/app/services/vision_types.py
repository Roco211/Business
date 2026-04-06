from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class VisionMediaInput:
    media_id: str
    public_url: str | None
    content_type: str | None
    file_name: str | None
    image_bytes: bytes | None = None


@dataclass(frozen=True)
class VisionCandidate:
    item_name: str
    confidence: float
    packaging_hint: str | None


@dataclass(frozen=True)
class VisionRecognition:
    provider_name: str
    candidates: list[VisionCandidate]
    used_fallback: bool
    raw_payload: dict[str, object]


class VisionProviderError(Exception):
    def __init__(self, code: str, message: str, *, retryable: bool) -> None:
        self.code = code
        self.message = message
        self.retryable = retryable
        super().__init__(message)


class VisionProvider(Protocol):
    def recognize_product(self, media_input: VisionMediaInput) -> VisionRecognition:
        ...
