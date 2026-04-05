from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.core.ids import new_prefixed_id
from app.models import OcrDocument
from app.services.media_uploads import get_ready_media_upload
from app.services.mock_multimodal import (
    MockMultimodalValidationError,
    extract_receipt,
)

PROCESSING_STATUS = "processing"
COMPLETED_STATUS = "completed"
SUPPORTED_DOCUMENT_TYPES = {"purchase-receipt"}


@dataclass(frozen=True)
class OcrDocumentCreateResult:
    ocr_document: OcrDocument
    response_status: str


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def create_mock_ocr_document(
    db_session: Session,
    *,
    shop_id: str,
    media_id: str,
    document_type: str,
    task_run_id: str | None,
) -> OcrDocumentCreateResult:
    if document_type not in SUPPORTED_DOCUMENT_TYPES:
        raise MockMultimodalValidationError("Unsupported document_type")

    get_ready_media_upload(
        db_session,
        shop_id=shop_id,
        media_id=media_id,
        expected_media_types={"receipt-image"},
    )

    now = _now()
    document = OcrDocument(
        ocr_document_id=new_prefixed_id("ocr"),
        shop_id=shop_id,
        task_run_id=task_run_id,
        media_id=media_id,
        document_type=document_type,
        status=PROCESSING_STATUS,
        provider_name=None,
        raw_text=None,
        extracted_fields=None,
        low_confidence_fields=[],
        created_at=now,
        updated_at=now,
    )
    db_session.add(document)
    db_session.flush()

    extracted = extract_receipt(media_ids=[media_id], text_hint=None)
    document.status = COMPLETED_STATUS
    document.provider_name = extracted.provider_name
    document.raw_text = extracted.raw_text
    document.extracted_fields = extracted.extracted_fields
    document.low_confidence_fields = list(extracted.low_confidence_fields)
    document.updated_at = _now()
    db_session.flush()

    return OcrDocumentCreateResult(
        ocr_document=document,
        response_status=PROCESSING_STATUS,
    )


def get_ocr_document(
    db_session: Session,
    *,
    shop_id: str,
    ocr_document_id: str,
) -> OcrDocument:
    document = db_session.get(OcrDocument, ocr_document_id)
    if document is None or document.shop_id != shop_id:
        raise LookupError(ocr_document_id)
    return document
