from fastapi import APIRouter, Depends, Header, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.contracts.common import DataEnvelope, ErrorBody, ErrorEnvelope
from app.contracts.media_upload import (
    CompleteMediaUploadData,
    CompleteMediaUploadRequest,
    CreateMediaUploadData,
    CreateMediaUploadRequest,
)
from app.db.session import get_db_session
from app.services.bootstrap import ensure_default_context
from app.services.media_uploads import (
    MediaUploadConflictError,
    MediaUploadValidationError,
    create_media_upload,
    mark_media_upload_complete,
)

router = APIRouter(prefix="/api/v1/media-uploads", tags=["media-uploads"])


def _unauthorized() -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content=ErrorEnvelope(
            error=ErrorBody(code="unauthorized", message="Unauthorized", details=[])
        ).model_dump(),
    )


def _error_response(status_code: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=ErrorEnvelope(
            error=ErrorBody(code=code, message=message, details=[])
        ).model_dump(),
    )


@router.post("", response_model=DataEnvelope[CreateMediaUploadData])
def post_create_media_upload(
    payload: CreateMediaUploadRequest,
    authorization: str | None = Header(default=None),
    db_session: Session = Depends(get_db_session),
) -> DataEnvelope[CreateMediaUploadData] | JSONResponse:
    if authorization != "Bearer mock_owner_token":
        return _unauthorized()

    context = ensure_default_context(db_session)

    try:
        result = create_media_upload(
            db_session,
            shop_id=context.shop.shop_id,
            uploader_actor_type="owner",
            uploader_actor_id="owner_default",
            media_type=payload.media_type,
            file_name=payload.file_name,
            content_type=payload.content_type,
            size_bytes=payload.size_bytes,
        )
    except MediaUploadValidationError as exc:
        return _error_response(status.HTTP_422_UNPROCESSABLE_ENTITY, "validation_error", str(exc))

    return JSONResponse(
        status_code=status.HTTP_201_CREATED,
        content=DataEnvelope(
            data=CreateMediaUploadData(
                media_id=result.media_id,
                upload_url=result.upload_url,
                public_url=result.public_url,
            )
        ).model_dump(mode="json"),
    )


@router.post("/{media_id}/complete", response_model=DataEnvelope[CompleteMediaUploadData])
def post_complete_media_upload(
    media_id: str,
    payload: CompleteMediaUploadRequest,
    authorization: str | None = Header(default=None),
    db_session: Session = Depends(get_db_session),
) -> DataEnvelope[CompleteMediaUploadData] | JSONResponse:
    if authorization != "Bearer mock_owner_token":
        return _unauthorized()

    ensure_default_context(db_session)

    try:
        result = mark_media_upload_complete(
            db_session,
            media_id=media_id,
            checksum_sha256=payload.checksum_sha256,
            size_bytes=payload.size_bytes,
        )
    except LookupError:
        return _error_response(status.HTTP_404_NOT_FOUND, "media_upload_not_found", "Media upload not found")
    except MediaUploadConflictError:
        return _error_response(
            status.HTTP_409_CONFLICT,
            "media_upload_conflict",
            "Media upload cannot transition from its current status",
        )
    except MediaUploadValidationError as exc:
        return _error_response(status.HTTP_422_UNPROCESSABLE_ENTITY, "validation_error", str(exc))

    return DataEnvelope(
        data=CompleteMediaUploadData(
            media_id=result.media_id,
            status=result.status,
        )
    )
