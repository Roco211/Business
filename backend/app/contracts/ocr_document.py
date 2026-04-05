from datetime import datetime
from typing import Any

from pydantic import BaseModel


class CreateOcrDocumentRequest(BaseModel):
    media_id: str
    document_type: str


class CreateOcrDocumentData(BaseModel):
    ocr_document_id: str
    status: str


class OcrDocumentData(BaseModel):
    ocr_document_id: str
    media_id: str
    document_type: str
    status: str
    fields: dict[str, Any] | None
    low_confidence_fields: list[str]
    created_at: datetime
    updated_at: datetime
