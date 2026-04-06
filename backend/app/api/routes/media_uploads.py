from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api.deps.auth import AuthenticatedContext, require_authenticated_context
from app.contracts.common import DataEnvelope, ErrorBody, ErrorEnvelope
from app.contracts.media_upload import (
    CompleteMediaUploadData,
    CompleteMediaUploadRequest,
    CreateMediaUploadData,
    CreateMediaUploadRequest,
)
from app.db.session import get_db_session
from app.models import MediaUpload
from app.services.media_uploads import (
    MediaUploadConflictError,
    MediaUploadNotReadyError,
    MediaUploadStorageUnavailableError,
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
    auth: AuthenticatedContext = Depends(require_authenticated_context),
    db_session: Session = Depends(get_db_session),
) -> DataEnvelope[CreateMediaUploadData] | JSONResponse:
    try:
        result = create_media_upload(
            db_session,
            shop_id=auth.shop_id,
            uploader_actor_type="owner",
            uploader_actor_id=auth.actor_id,
            media_type=payload.media_type,
            file_name=payload.file_name,
            content_type=payload.content_type,
            size_bytes=payload.size_bytes,
        )
    except MediaUploadValidationError as exc:
        return _error_response(status.HTTP_422_UNPROCESSABLE_ENTITY, "validation_error", str(exc))
    except MediaUploadStorageUnavailableError:
        return _error_response(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "storage_unavailable",
            "Object storage is unavailable",
        )

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
    auth: AuthenticatedContext = Depends(require_authenticated_context),
    db_session: Session = Depends(get_db_session),
) -> DataEnvelope[CompleteMediaUploadData] | JSONResponse:
    media_upload = db_session.get(MediaUpload, media_id)
    if media_upload is None or media_upload.shop_id != auth.shop_id:
        return _error_response(status.HTTP_404_NOT_FOUND, "media_upload_not_found", "Media upload not found")

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
    except MediaUploadNotReadyError:
        return _error_response(
            status.HTTP_409_CONFLICT,
            "media_upload_conflict",
            "Media upload is not ready for completion",
        )
    except MediaUploadStorageUnavailableError:
        return _error_response(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "storage_unavailable",
            "Object storage is unavailable",
        )
    except MediaUploadValidationError as exc:
        return _error_response(status.HTTP_422_UNPROCESSABLE_ENTITY, "validation_error", str(exc))

    return DataEnvelope(
        data=CompleteMediaUploadData(
            media_id=result.media_id,
            status=result.status,
        )
    )
