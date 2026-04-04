from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Message, SessionRecord, Shop, TaskRun
from app.runtime.types import RuntimeTurnContext


def _require_record(record, record_id: str):
    if record is None:
        raise LookupError(record_id)
    return record


def _decimal_to_float(value: Decimal | None) -> float | None:
    if value is None:
        return None
    return float(value)


def build_runtime_turn_context(
    db_session: Session,
    *,
    task_run_id: str,
) -> RuntimeTurnContext:
    task_run = _require_record(db_session.get(TaskRun, task_run_id), task_run_id)
    source_message = _require_record(
        db_session.get(Message, task_run.source_message_id),
        task_run.source_message_id,
    )
    session_record = _require_record(
        db_session.get(SessionRecord, task_run.session_id),
        task_run.session_id,
    )
    shop = _require_record(db_session.get(Shop, session_record.shop_id), session_record.shop_id)

    recent_records = list(
        db_session.scalars(
            select(Message)
            .where(Message.session_id == session_record.session_id)
            .order_by(Message.created_at.desc(), Message.message_id.desc())
            .limit(10)
        )
    )

    return RuntimeTurnContext(
        shop_id=shop.shop_id,
        session_id=session_record.session_id,
        source_message_id=source_message.message_id,
        task_run_id=task_run.task_run_id,
        input_kind=source_message.message_type,
        source_text=source_message.text,
        media_ids=list(source_message.media_ids),
        locale=shop.locale,
        timezone=shop.timezone,
        shop_rules={
            "low_confidence_threshold": float(shop.low_confidence_threshold),
            "default_low_stock_threshold": _decimal_to_float(shop.default_low_stock_threshold),
            "require_price_confirmation": shop.require_price_confirmation,
            "require_new_item_confirmation": shop.require_new_item_confirmation,
        },
        recent_messages=[
            {
                "message_id": record.message_id,
                "actor_type": record.actor_type,
                "actor_id": record.actor_id,
                "message_type": record.message_type,
                "text": record.text,
                "media_ids": list(record.media_ids),
                "task_run_id": record.task_run_id,
                "created_at": record.created_at,
            }
            for record in recent_records
        ],
        pending_confirmation_id=None,
    )
