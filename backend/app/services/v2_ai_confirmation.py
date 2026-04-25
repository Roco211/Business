from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.models import V2Confirmation, V2TaskRun
from app.services.v2_conversation import (
    create_v2_confirmation,
    create_v2_message_and_task_run,
    create_v2_session,
)


@dataclass(frozen=True)
class CreatedV2AIStockConfirmation:
    confirmation: V2Confirmation
    task_run: V2TaskRun
    session_id: str


def create_v2_ai_stock_in_confirmation(
    db_session: Session,
    *,
    tenant_id: str,
    shop_id: str,
    account_id: str,
    source_type: str,
    source_text: str | None,
    draft_payload: dict[str, Any],
) -> CreatedV2AIStockConfirmation:
    """Create a real pending confirmation for AI-derived stock-in writes.

    Voice/photo AI extraction is not allowed to commit inventory directly. This helper
    persists a conversation session, source message, task run, and V2Confirmation so
    the only later mutation path is approval of the confirmation.
    """
    session = create_v2_session(
        db_session,
        tenant_id=tenant_id,
        shop_id=shop_id,
        initiated_by_account_id=account_id,
        session_type=source_type,
        title=_build_ai_stock_in_title(source_type, draft_payload),
    )
    message_task = create_v2_message_and_task_run(
        db_session,
        tenant_id=tenant_id,
        shop_id=shop_id,
        session_id=session.session_id,
        actor_id=account_id,
        message_kind=f"{source_type}-stock-in",
        payload_json={
            "source_type": source_type,
            "source_text": source_text,
            "draft_fields": dict(draft_payload),
        },
        client_request_id=None,
        intent_type="inventory.stock_in",
    )
    if message_task is None:
        raise LookupError(session.session_id)
    _message, task_run = message_task
    confirmation = create_v2_confirmation(
        db_session,
        tenant_id=tenant_id,
        shop_id=shop_id,
        task_run_id=task_run.task_run_id,
        confirmation_type="inventory.stock_in",
        draft_payload={**dict(draft_payload), "source_type": source_type, "source_text": source_text},
    )
    return CreatedV2AIStockConfirmation(
        confirmation=confirmation,
        task_run=task_run,
        session_id=session.session_id,
    )


def _build_ai_stock_in_title(source_type: str, draft_payload: dict[str, Any]) -> str:
    item_name = str(draft_payload.get("item_name") or "").strip()
    if item_name:
        return f"{source_type} stock-in: {item_name}"
    return f"{source_type} stock-in confirmation"
