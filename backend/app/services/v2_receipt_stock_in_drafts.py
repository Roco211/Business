from sqlalchemy.orm import Session

from app.services.v2_conversation import (
    append_v2_system_result_message,
    get_v2_task_run,
    request_v2_confirmation_from_task_draft,
    upsert_v2_task_draft,
)
from app.services.v2_documents import get_v2_document

RECEIPT_DOCUMENT_TYPE = "purchase-receipt"
COMPLETED_EXTRACTION_STATUS = "completed"
RECEIPT_STOCK_IN_DRAFT_TYPE = "inventory.stock_in"


class V2ReceiptStockInDraftValidationError(ValueError):
    pass


def create_v2_receipt_stock_in_draft_from_document(
    db_session: Session,
    *,
    tenant_id: str,
    shop_id: str,
    task_run_id: str,
    document_id: str,
    created_by_account_id: str,
):
    document = get_v2_document(
        db_session,
        tenant_id=tenant_id,
        shop_id=shop_id,
        document_id=document_id,
    )
    if document.document_type != RECEIPT_DOCUMENT_TYPE:
        raise V2ReceiptStockInDraftValidationError("document_type must be purchase-receipt")
    if document.extraction_status != COMPLETED_EXTRACTION_STATUS:
        raise V2ReceiptStockInDraftValidationError("document extraction is not completed")

    first_item = _require_first_receipt_item(document.extracted_fields)
    draft_payload = {
        "item_name": _normalize_required_string(first_item.get("name"), field_name="items[0].name"),
        "quantity": first_item.get("quantity"),
        "unit": _normalize_required_string(first_item.get("unit"), field_name="items[0].unit"),
        "price": first_item.get("price"),
        "source_type": "receipt-document",
        "source_document_id": document.document_id,
        "source_media_asset_id": document.media_asset_id,
    }

    return upsert_v2_task_draft(
        db_session,
        tenant_id=tenant_id,
        shop_id=shop_id,
        task_run_id=task_run_id,
        draft_type=RECEIPT_STOCK_IN_DRAFT_TYPE,
        draft_payload=draft_payload,
        created_by_account_id=created_by_account_id,
    )


def create_v2_receipt_stock_in_confirmation_from_document(
    db_session: Session,
    *,
    tenant_id: str,
    shop_id: str,
    task_run_id: str,
    document_id: str,
    created_by_account_id: str,
):
    create_v2_receipt_stock_in_draft_from_document(
        db_session,
        tenant_id=tenant_id,
        shop_id=shop_id,
        task_run_id=task_run_id,
        document_id=document_id,
        created_by_account_id=created_by_account_id,
    )
    confirmation = request_v2_confirmation_from_task_draft(
        db_session,
        tenant_id=tenant_id,
        shop_id=shop_id,
        task_run_id=task_run_id,
        confirmation_type=RECEIPT_STOCK_IN_DRAFT_TYPE,
    )
    task_run = get_v2_task_run(
        db_session,
        tenant_id=tenant_id,
        shop_id=shop_id,
        task_run_id=task_run_id,
    )
    if task_run is not None:
        append_v2_system_result_message(
            db_session,
            task_run=task_run,
            confirmation=confirmation,
            text="Receipt stock-in draft is ready for confirmation.",
        )
        db_session.commit()
    return confirmation


def _require_first_receipt_item(extracted_fields: dict[str, object]) -> dict[str, object]:
    raw_items = extracted_fields.get("items")
    if not isinstance(raw_items, list) or not raw_items:
        raise V2ReceiptStockInDraftValidationError("receipt items are required")

    first_item = raw_items[0]
    if not isinstance(first_item, dict):
        raise V2ReceiptStockInDraftValidationError("receipt item must be an object")
    return first_item


def _normalize_required_string(value: object, *, field_name: str) -> str:
    normalized = value.strip() if isinstance(value, str) else ""
    if not normalized:
        raise V2ReceiptStockInDraftValidationError(f"{field_name} is required")
    return normalized
