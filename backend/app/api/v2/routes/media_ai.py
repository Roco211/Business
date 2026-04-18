from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api.deps.v2_context import (
    V2AuthenticatedAccount,
    V2ExecutionContext,
    require_v2_authenticated_account,
    require_v2_execution_context,
)
from app.contracts.v2.common import V2DataEnvelope, V2ErrorBody, V2ErrorEnvelope
from app.contracts.v2.media_ai import (
    V2CompleteMediaAssetData,
    V2CompleteMediaAssetRequest,
    V2CreateMediaAssetData,
    V2CreateMediaAssetRequest,
)
from app.db.session import get_db_session
from app.services.v2_media_assets import (
    V2MediaAssetConflictError,
    V2MediaAssetNotReadyError,
    V2MediaAssetStorageUnavailableError,
    V2MediaAssetValidationError,
    create_v2_media_asset_upload,
    mark_v2_media_asset_uploaded,
)

router = APIRouter(prefix="/api/v2/media-assets", tags=["v2-media-ai"])


def _context_account_mismatch() -> JSONResponse:
    return JSONResponse(
        status_code=403,
        content=V2ErrorEnvelope(
            error=V2ErrorBody(code="context_account_mismatch", message="Context account mismatch")
        ).model_dump(),
    )


@router.post("", response_model=V2DataEnvelope[V2CreateMediaAssetData], status_code=status.HTTP_201_CREATED)
def create_media_asset_v2(
    payload: V2CreateMediaAssetRequest,
    account: V2AuthenticatedAccount = Depends(require_v2_authenticated_account),
    context: V2ExecutionContext = Depends(require_v2_execution_context),
    db_session: Session = Depends(get_db_session),
) -> V2DataEnvelope[V2CreateMediaAssetData] | JSONResponse:
    if account.account_id != context.account_id:
        return _context_account_mismatch()

    try:
        created = create_v2_media_asset_upload(
            db_session,
            tenant_id=context.tenant_id,
            shop_id=context.shop_id,
            context_session_id=context.context_session_id,
            uploaded_by_account_id=account.account_id,
            media_type=payload.media_type,
            file_name=payload.file_name,
            content_type=payload.content_type,
            size_bytes=payload.size_bytes,
        )
    except V2MediaAssetValidationError as exc:
        return JSONResponse(
            status_code=422,
            content=V2ErrorEnvelope(error=V2ErrorBody(code="validation_error", message=str(exc))).model_dump(),
        )
    except V2MediaAssetStorageUnavailableError:
        return JSONResponse(
            status_code=503,
            content=V2ErrorEnvelope(
                error=V2ErrorBody(code="media_storage_unavailable", message="Media storage is unavailable")
            ).model_dump(),
        )

    return V2DataEnvelope(
        data=V2CreateMediaAssetData(
            media_asset_id=created.media_asset_id,
            status=created.status,
            upload_url=created.upload_url,
            public_url=created.public_url,
        )
    )


@router.post("/{media_asset_id}/complete", response_model=V2DataEnvelope[V2CompleteMediaAssetData])
def complete_media_asset_v2(
    media_asset_id: str,
    payload: V2CompleteMediaAssetRequest,
    account: V2AuthenticatedAccount = Depends(require_v2_authenticated_account),
    context: V2ExecutionContext = Depends(require_v2_execution_context),
    db_session: Session = Depends(get_db_session),
) -> V2DataEnvelope[V2CompleteMediaAssetData] | JSONResponse:
    if account.account_id != context.account_id:
        return _context_account_mismatch()

    try:
        completed = mark_v2_media_asset_uploaded(
            db_session,
            tenant_id=context.tenant_id,
            shop_id=context.shop_id,
            media_asset_id=media_asset_id,
            checksum_sha256=payload.checksum_sha256,
            size_bytes=payload.size_bytes,
        )
    except LookupError:
        return JSONResponse(
            status_code=404,
            content=V2ErrorEnvelope(
                error=V2ErrorBody(code="media_asset_not_found", message="Media asset not found")
            ).model_dump(),
        )
    except V2MediaAssetValidationError as exc:
        return JSONResponse(
            status_code=422,
            content=V2ErrorEnvelope(error=V2ErrorBody(code="validation_error", message=str(exc))).model_dump(),
        )
    except (V2MediaAssetConflictError, V2MediaAssetNotReadyError):
        return JSONResponse(
            status_code=409,
            content=V2ErrorEnvelope(
                error=V2ErrorBody(code="media_asset_conflict", message="Media asset conflicts with current state")
            ).model_dump(),
        )
    except V2MediaAssetStorageUnavailableError:
        return JSONResponse(
            status_code=503,
            content=V2ErrorEnvelope(
                error=V2ErrorBody(code="media_storage_unavailable", message="Media storage is unavailable")
            ).model_dump(),
        )

    return V2DataEnvelope(
        data=V2CompleteMediaAssetData(
            media_asset_id=completed.media_asset_id,
            status=completed.status,
        )
    )
