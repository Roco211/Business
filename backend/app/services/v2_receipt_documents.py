from sqlalchemy import select

from app.core.config import get_settings
from app.models import V2ConversationSession, V2TaskRun
from app.services.ocr_gateway import get_default_ocr_gateway
from app.services.ocr_types import OcrMediaInput, OcrProviderError
from app.services.v2_documents import (
    V2DocumentConflictError,
    V2DocumentDependencyNotFoundError,
    create_v2_document,
)
from app.services.v2_media_assets import V2MediaAssetNotReadyError, get_ready_v2_media_asset
from app.services.v2_model_call_logs import append_v2_model_call_log
from app.services.v2_receipt_stock_in_drafts import create_v2_receipt_stock_in_confirmation_from_document

RECEIPT_DOCUMENT_TYPE = "purchase-receipt"
RECEIPT_EXTRACTION_STATUS = "completed"
RECEIPT_PROMPT_VERSION = "receipt-extract@v1"
RECEIPT_SCHEMA_VERSION = "purchase-receipt@v1"
RECEIPT_MEDIA_TYPES = {"receipt-image"}


def extract_v2_receipt_document(
    db_session,
    *,
    tenant_id: str,
    shop_id: str,
    context_session_id: str,
    requested_by_account_id: str,
    media_asset_id: str,
    task_run_id: str | None = None,
    conversation_session_id: str | None = None,
):
    try:
        media_asset = get_ready_v2_media_asset(
            db_session,
            tenant_id=tenant_id,
            shop_id=shop_id,
            media_asset_id=media_asset_id,
            expected_media_types=RECEIPT_MEDIA_TYPES,
        )
    except LookupError as exc:
        raise V2DocumentDependencyNotFoundError("media_asset_not_found") from exc
    except V2MediaAssetNotReadyError as exc:
        raise V2DocumentConflictError(media_asset_id) from exc
    normalized_task_run_id, normalized_conversation_session_id = _resolve_task_affinity(
        db_session,
        tenant_id=tenant_id,
        shop_id=shop_id,
        task_run_id=task_run_id,
        conversation_session_id=conversation_session_id,
    )

    media_input = OcrMediaInput(
        media_id=media_asset.media_asset_id,
        public_url=media_asset.public_url,
        content_type=media_asset.content_type,
        file_name=media_asset.file_name,
    )
    gateway = get_default_ocr_gateway()
    try:
        extraction = gateway.extract_purchase_receipt(media_input)
    except OcrProviderError as exc:
        append_v2_model_call_log(
            db_session,
            tenant_id=tenant_id,
            shop_id=shop_id,
            context_session_id=context_session_id,
            requested_by_account_id=requested_by_account_id,
            media_asset_id=media_asset.media_asset_id,
            task_run_id=normalized_task_run_id,
            conversation_session_id=normalized_conversation_session_id,
            provider_type="ocr",
            provider_key=_resolve_ocr_provider_key(),
            model_name=_resolve_ocr_model_name(fallback_provider_name=None),
            operation_type="document.receipt.extract",
            status="failed",
            request_payload={"media_asset_id": media_asset.media_asset_id, "document_type": RECEIPT_DOCUMENT_TYPE},
            response_payload=None,
            error_code=exc.code,
            latency_ms=None,
            cost_micros=None,
            prompt_version=RECEIPT_PROMPT_VERSION,
            schema_version=RECEIPT_SCHEMA_VERSION,
            confidence_score=None,
            used_fallback=False,
        )
        raise

    confidence_summary = _build_confidence_summary(extraction)
    model_call_log = append_v2_model_call_log(
        db_session,
        tenant_id=tenant_id,
        shop_id=shop_id,
        context_session_id=context_session_id,
        requested_by_account_id=requested_by_account_id,
        media_asset_id=media_asset.media_asset_id,
        task_run_id=normalized_task_run_id,
        conversation_session_id=normalized_conversation_session_id,
        provider_type="ocr",
        provider_key=_resolve_ocr_provider_key(extraction.provider_name),
        model_name=_resolve_ocr_model_name(fallback_provider_name=extraction.provider_name),
        operation_type="document.receipt.extract",
        status="completed",
        request_payload={"media_asset_id": media_asset.media_asset_id, "document_type": RECEIPT_DOCUMENT_TYPE},
        response_payload=extraction.raw_payload,
        error_code=None,
        latency_ms=None,
        cost_micros=None,
        prompt_version=RECEIPT_PROMPT_VERSION,
        schema_version=RECEIPT_SCHEMA_VERSION,
        confidence_score=confidence_summary["overall"],
        used_fallback=extraction.used_fallback,
    )
    document = create_v2_document(
        db_session,
        tenant_id=tenant_id,
        shop_id=shop_id,
        context_session_id=context_session_id,
        created_by_account_id=requested_by_account_id,
        media_asset_id=media_asset.media_asset_id,
        model_call_log_id=model_call_log.model_call_log_id,
        document_type=RECEIPT_DOCUMENT_TYPE,
        extraction_status=RECEIPT_EXTRACTION_STATUS,
        extracted_fields={
            "raw_text": extraction.raw_text,
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
        },
        confidence_summary=confidence_summary,
    )
    if normalized_task_run_id is not None:
        create_v2_receipt_stock_in_confirmation_from_document(
            db_session,
            tenant_id=tenant_id,
            shop_id=shop_id,
            task_run_id=normalized_task_run_id,
            document_id=document.document_id,
            created_by_account_id=requested_by_account_id,
        )
    return document


def _build_confidence_summary(extraction) -> dict[str, object]:
    overall = 0.95
    if extraction.low_confidence_fields:
        overall -= 0.25
    if extraction.used_fallback:
        overall -= 0.1
    if overall < 0.1:
        overall = 0.1
    return {
        "overall": overall,
        "low_confidence_fields": list(extraction.low_confidence_fields),
        "used_fallback": extraction.used_fallback,
    }


def _resolve_ocr_provider_key(provider_name: str | None = None) -> str:
    configured = get_settings().ocr_provider.strip().lower()
    if configured:
        return configured
    normalized_provider_name = provider_name.strip().lower() if isinstance(provider_name, str) and provider_name.strip() else ""
    return normalized_provider_name or "mock"


def _resolve_ocr_model_name(*, fallback_provider_name: str | None) -> str:
    configured_model = get_settings().ocr_provider_model
    if isinstance(configured_model, str) and configured_model.strip():
        return configured_model.strip()
    if isinstance(fallback_provider_name, str) and fallback_provider_name.strip():
        return fallback_provider_name.strip()
    return "mock-ocr"


def _resolve_task_affinity(
    db_session,
    *,
    tenant_id: str,
    shop_id: str,
    task_run_id: str | None,
    conversation_session_id: str | None,
) -> tuple[str | None, str | None]:
    normalized_task_run_id = task_run_id.strip() if isinstance(task_run_id, str) and task_run_id.strip() else None
    normalized_conversation_session_id = (
        conversation_session_id.strip()
        if isinstance(conversation_session_id, str) and conversation_session_id.strip()
        else None
    )

    if normalized_conversation_session_id is not None:
        session = db_session.scalar(
            select(V2ConversationSession).where(
                V2ConversationSession.session_id == normalized_conversation_session_id,
                V2ConversationSession.tenant_id == tenant_id,
                V2ConversationSession.shop_id == shop_id,
            )
        )
        if session is None:
            raise V2DocumentDependencyNotFoundError("conversation_session_not_found")

    if normalized_task_run_id is not None:
        task_run = db_session.scalar(
            select(V2TaskRun).where(
                V2TaskRun.task_run_id == normalized_task_run_id,
                V2TaskRun.tenant_id == tenant_id,
                V2TaskRun.shop_id == shop_id,
            )
        )
        if task_run is None:
            raise V2DocumentDependencyNotFoundError("task_run_not_found")
        if normalized_conversation_session_id is not None and task_run.session_id != normalized_conversation_session_id:
            raise V2DocumentConflictError(normalized_task_run_id)
        if normalized_conversation_session_id is None:
            normalized_conversation_session_id = task_run.session_id

    return normalized_task_run_id, normalized_conversation_session_id
