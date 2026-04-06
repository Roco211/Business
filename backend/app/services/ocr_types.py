from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class OcrMediaInput:
    media_id: str
    public_url: str | None
    content_type: str | None
    file_name: str | None
    image_bytes: bytes | None = None


@dataclass(frozen=True)
class OcrExtractedLineItem:
    item_name: str | None
    quantity: float | None
    unit: str | None
    price: float | None


@dataclass(frozen=True)
class OcrExtraction:
    document_type: str
    provider_name: str
    raw_text: str | None
    line_items: list[OcrExtractedLineItem]
    total_amount: float | None
    low_confidence_fields: list[str]
    used_fallback: bool
    raw_payload: dict[str, object]


class OcrProviderError(Exception):
    def __init__(self, code: str, message: str, *, retryable: bool) -> None:
        self.code = code
        self.message = message
        self.retryable = retryable
        super().__init__(message)


class OcrProvider(Protocol):
    def extract_purchase_receipt(self, media_input: OcrMediaInput) -> OcrExtraction:
        ...
