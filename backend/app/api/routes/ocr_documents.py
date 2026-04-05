from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api.deps.auth import AuthenticatedContext, require_authenticated_context
from app.contracts.common import DataEnvelope, ErrorBody, ErrorEnvelope
from app.contracts.ocr_document import (
    CreateOcrDocumentData,
    CreateOcrDocumentRequest,
    OcrDocumentData,
)
from app.db.session import get_db_session
from app.services.media_uploads import MediaUploadNotReadyError
from app.services.mock_multimodal import MockMultimodalValidationError
from app.services.ocr_documents import create_mock_ocr_document, get_ocr_document

router = APIRouter(prefix="/api/v1/ocr-documents", tags=["ocr-documents"])


def _unauthorized() -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content=ErrorEnvelope(
            error=ErrorBody(code="unauthorized", message="Unauthorized", details=[]),
        ).model_dump(),
    )


def _error_response(status_code: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=ErrorEnvelope(
            error=ErrorBody(code=code, message=message, details=[]),
        ).model_dump(),
    )


def _to_ocr_document_data(document) -> OcrDocumentData:
    return OcrDocumentData(
        ocr_document_id=document.ocr_document_id,
        media_id=document.media_id,
        document_type=document.document_type,
        status=document.status,
        fields=document.extracted_fields,
        low_confidence_fields=list(document.low_confidence_fields),
        created_at=document.created_at,
        updated_at=document.updated_at,
    )


@router.post("", response_model=DataEnvelope[CreateOcrDocumentData])
def post_create_ocr_document(
    payload: CreateOcrDocumentRequest,
    auth: AuthenticatedContext = Depends(require_authenticated_context),
    db_session: Session = Depends(get_db_session),
) -> DataEnvelope[CreateOcrDocumentData] | JSONResponse:
    try:
        result = create_mock_ocr_document(
            db_session,
            shop_id=auth.shop_id,
            media_id=payload.media_id,
            document_type=payload.document_type,
            task_run_id=None,
        )
        db_session.commit()
    except MediaUploadNotReadyError:
        db_session.rollback()
        return _error_response(status.HTTP_404_NOT_FOUND, "media_upload_not_found", "Media upload not found")
    except MockMultimodalValidationError as exc:
        db_session.rollback()
        return _error_response(status.HTTP_422_UNPROCESSABLE_ENTITY, "validation_error", str(exc))

    return JSONResponse(
        status_code=status.HTTP_201_CREATED,
        content=DataEnvelope(
            data=CreateOcrDocumentData(
                ocr_document_id=result.ocr_document.ocr_document_id,
                status=result.response_status,
            )
        ).model_dump(mode="json"),
    )


@router.get("/{ocr_document_id}", response_model=DataEnvelope[OcrDocumentData])
def get_ocr_document_detail(
    ocr_document_id: str,
    auth: AuthenticatedContext = Depends(require_authenticated_context),
    db_session: Session = Depends(get_db_session),
) -> DataEnvelope[OcrDocumentData] | JSONResponse:
    try:
        document = get_ocr_document(
            db_session,
            shop_id=auth.shop_id,
            ocr_document_id=ocr_document_id,
        )
    except LookupError:
        return _error_response(status.HTTP_404_NOT_FOUND, "ocr_document_not_found", "OCR document not found")

    return DataEnvelope(data=_to_ocr_document_data(document))
