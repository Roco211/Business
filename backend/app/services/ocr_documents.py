from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.core.ids import new_prefixed_id
from app.models import OcrDocument
from app.services.ocr_gateway import get_default_ocr_gateway
from app.services.ocr_types import OcrMediaInput
from app.services.media_uploads import get_ready_media_upload
from app.services.mock_multimodal import MockMultimodalValidationError

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
    # Backward-compatible shim: callers still using the legacy mock entrypoint
    # should transparently benefit from gateway-backed durable OCR documents.
    return create_ocr_document(
        db_session,
        shop_id=shop_id,
        media_id=media_id,
        document_type=document_type,
        task_run_id=task_run_id,
    )


def create_ocr_document(
    db_session: Session,
    *,
    shop_id: str,
    media_id: str,
    document_type: str,
    task_run_id: str | None,
) -> OcrDocumentCreateResult:
    if document_type not in SUPPORTED_DOCUMENT_TYPES:
        raise MockMultimodalValidationError("Unsupported document_type")

    media_upload = get_ready_media_upload(
        db_session,
        shop_id=shop_id,
        media_id=media_id,
        expected_media_types={"receipt-image"},
    )
    media_input = OcrMediaInput(
        media_id=media_upload.media_id,
        public_url=media_upload.public_url,
        content_type=media_upload.content_type,
        file_name=media_upload.file_name,
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

    extraction = get_default_ocr_gateway().extract_purchase_receipt(media_input)
    document.status = COMPLETED_STATUS
    document.provider_name = extraction.provider_name
    document.raw_text = extraction.raw_text
    document.extracted_fields = {
        "items": [
            {
                "name": item.item_name,
                "quantity": item.quantity,
                "unit": item.unit,
                "price": item.price,
            }
            for item in extraction.line_items
        ],
        "total_amount": extraction.total_amount,
    }
    document.low_confidence_fields = list(extraction.low_confidence_fields)
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
