from sqlalchemy import select

from app.core.ids import new_prefixed_id
from app.models import V2ContextSession, V2Document, V2ModelCallLog
from app.services.v2_media_assets import V2MediaAssetNotReadyError, get_ready_v2_media_asset
from app.services.v2_time import utc_now_naive

SUPPORTED_V2_DOCUMENT_TYPES = {"purchase-receipt"}
SUPPORTED_V2_EXTRACTION_STATUSES = {"pending", "completed", "failed"}


class V2DocumentValidationError(ValueError):
    pass


class V2DocumentConflictError(ValueError):
    pass


class V2DocumentNotFoundError(LookupError):
    pass


class V2DocumentDependencyNotFoundError(LookupError):
    def __init__(self, dependency_code: str) -> None:
        super().__init__(dependency_code)
        self.dependency_code = dependency_code


def create_v2_document(
    db_session,
    *,
    tenant_id: str,
    shop_id: str,
    context_session_id: str,
    created_by_account_id: str,
    media_asset_id: str,
    model_call_log_id: str | None,
    document_type: str,
    extraction_status: str,
    extracted_fields: dict[str, object],
    confidence_summary: dict[str, object],
) -> V2Document:
    normalized_document_type = document_type.strip().lower()
    normalized_extraction_status = extraction_status.strip().lower()
    if normalized_document_type not in SUPPORTED_V2_DOCUMENT_TYPES:
        raise V2DocumentValidationError("Unsupported document_type")
    if normalized_extraction_status not in SUPPORTED_V2_EXTRACTION_STATUSES:
        raise V2DocumentValidationError("Unsupported extraction_status")
    if not media_asset_id.strip():
        raise V2DocumentValidationError("media_asset_id is required")
    if not isinstance(extracted_fields, dict):
        raise V2DocumentValidationError("extracted_fields must be an object")
    if not isinstance(confidence_summary, dict):
        raise V2DocumentValidationError("confidence_summary must be an object")

    _require_v2_context(
        db_session,
        tenant_id=tenant_id,
        shop_id=shop_id,
        context_session_id=context_session_id,
        account_id=created_by_account_id,
    )
    try:
        media_asset = get_ready_v2_media_asset(
            db_session,
            tenant_id=tenant_id,
            shop_id=shop_id,
            media_asset_id=media_asset_id,
        )
    except LookupError as exc:
        raise V2DocumentDependencyNotFoundError("media_asset_not_found") from exc
    except V2MediaAssetNotReadyError as exc:
        raise V2DocumentConflictError(media_asset_id) from exc

    normalized_model_call_log_id = model_call_log_id.strip() if isinstance(model_call_log_id, str) else None
    if normalized_model_call_log_id:
        model_call_log = _require_v2_model_call_log(
            db_session,
            tenant_id=tenant_id,
            shop_id=shop_id,
            context_session_id=context_session_id,
            model_call_log_id=normalized_model_call_log_id,
        )
        if model_call_log.media_asset_id != media_asset.media_asset_id:
            raise V2DocumentConflictError(normalized_model_call_log_id)
    else:
        normalized_model_call_log_id = None

    now = utc_now_naive()
    document = V2Document(
        document_id=new_prefixed_id("vdoc"),
        tenant_id=tenant_id,
        shop_id=shop_id,
        context_session_id=context_session_id,
        media_asset_id=media_asset.media_asset_id,
        model_call_log_id=normalized_model_call_log_id,
        created_by_account_id=created_by_account_id,
        document_type=normalized_document_type,
        extraction_status=normalized_extraction_status,
        extracted_fields=extracted_fields,
        confidence_summary=confidence_summary,
        created_at=now,
        updated_at=now,
    )
    db_session.add(document)
    db_session.commit()
    return document


def get_v2_document(
    db_session,
    *,
    tenant_id: str,
    shop_id: str,
    document_id: str,
) -> V2Document:
    document = db_session.scalar(
        select(V2Document).where(
            V2Document.document_id == document_id,
            V2Document.tenant_id == tenant_id,
            V2Document.shop_id == shop_id,
        )
    )
    if document is None:
        raise V2DocumentNotFoundError(document_id)
    return document


def _require_v2_context(
    db_session,
    *,
    tenant_id: str,
    shop_id: str,
    context_session_id: str,
    account_id: str,
) -> None:
    context_session = db_session.scalar(
        select(V2ContextSession).where(
            V2ContextSession.context_session_id == context_session_id,
            V2ContextSession.tenant_id == tenant_id,
            V2ContextSession.shop_id == shop_id,
            V2ContextSession.account_id == account_id,
            V2ContextSession.status == "active",
        )
    )
    if context_session is None:
        raise V2DocumentDependencyNotFoundError("context_session_not_found")


def _require_v2_model_call_log(
    db_session,
    *,
    tenant_id: str,
    shop_id: str,
    context_session_id: str,
    model_call_log_id: str,
) -> V2ModelCallLog:
    model_call_log = db_session.scalar(
        select(V2ModelCallLog).where(
            V2ModelCallLog.model_call_log_id == model_call_log_id,
            V2ModelCallLog.tenant_id == tenant_id,
            V2ModelCallLog.shop_id == shop_id,
            V2ModelCallLog.context_session_id == context_session_id,
        )
    )
    if model_call_log is None:
        raise V2DocumentDependencyNotFoundError("model_call_log_not_found")
    return model_call_log
