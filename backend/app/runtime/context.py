from decimal import Decimal

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session, aliased

from app.models import Confirmation, Message, SessionRecord, Shop, TaskRun
from app.runtime.types import RuntimeMediaRef, RuntimeTurnContext
from app.services.media_uploads import MediaUploadNotReadyError, get_ready_media_upload


def _require_record(record, record_id: str):
    if record is None:
        raise LookupError(record_id)
    return record


def _decimal_to_float(value: Decimal | None) -> float | None:
    if value is None:
        return None
    return float(value)


def _resolve_runtime_media_refs(
    db_session: Session,
    *,
    shop_id: str,
    media_ids: list[str],
) -> list[RuntimeMediaRef]:
    media_refs: list[RuntimeMediaRef] = []
    for media_id in media_ids:
        try:
            media_upload = get_ready_media_upload(
                db_session,
                shop_id=shop_id,
                media_id=media_id,
            )
        except MediaUploadNotReadyError:
            continue
        media_refs.append(
            RuntimeMediaRef(
                media_id=media_upload.media_id,
                media_type=media_upload.media_type,
                content_type=media_upload.content_type,
                file_name=media_upload.file_name,
                public_url=media_upload.public_url,
            )
        )
    return media_refs


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
    related_task_run = aliased(TaskRun)

    recent_records = list(
        db_session.scalars(
            select(Message)
            .outerjoin(related_task_run, Message.task_run_id == related_task_run.task_run_id)
            .where(
                Message.session_id == session_record.session_id,
                or_(
                    Message.created_at < source_message.created_at,
                    Message.message_id == source_message.message_id,
                    and_(
                        Message.created_at == source_message.created_at,
                        or_(
                            related_task_run.created_at < task_run.created_at,
                            and_(
                                related_task_run.created_at == task_run.created_at,
                                Message.message_id < source_message.message_id,
                            ),
                        ),
                    ),
                ),
            )
            .order_by(
                Message.created_at.desc(),
                related_task_run.created_at.desc(),
                Message.message_id.desc(),
            )
            .limit(10)
        )
    )
    pending_confirmation = db_session.scalar(
        select(Confirmation).where(
            Confirmation.task_run_id == task_run.task_run_id,
            Confirmation.status == "pending",
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
        media_refs=_resolve_runtime_media_refs(
            db_session,
            shop_id=shop.shop_id,
            media_ids=list(source_message.media_ids),
        ),
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
        pending_confirmation_id=None if pending_confirmation is None else pending_confirmation.confirmation_id,
    )
