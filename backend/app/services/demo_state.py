from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.models import (
    Alert,
    AuditLog,
    Confirmation,
    InventoryEvent,
    InventoryItem,
    MediaUpload,
    Message,
    OcrDocument,
    SessionStreamEvent,
    TaskRun,
)
from app.runtime.processor import process_task_run
from app.services.approved_receipt_stock_in_commits import commit_approved_receipt_stock_in_confirmation
from app.services.approved_stock_in_commits import commit_approved_stock_in_confirmation
from app.services.bootstrap import BootstrapContext, ensure_default_context
from app.services.confirmations import get_pending_confirmation_for_task_run
from app.services.inventory_stock_outs import submit_inventory_stock_out
from app.services.media_uploads import create_media_upload, mark_media_upload_complete
from app.services.messages import create_message

DEMO_LOW_STOCK_THRESHOLD = Decimal("5")


@dataclass(frozen=True)
class DemoBootstrapSummary:
    shop_id: str
    session_id: str
    inventory_item_count: int
    inventory_item_names: list[str]
    pending_confirmation_count: int
    pending_confirmation_types: list[str]
    open_low_stock_alert_count: int
    open_low_stock_item_names: list[str]
    message_count: int
    task_run_count: int

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _reset_default_context_state(
    db_session: Session,
    *,
    context: BootstrapContext,
) -> None:
    task_run_ids = select(TaskRun.task_run_id).where(TaskRun.session_id == context.session.session_id)
    now = _now()

    db_session.execute(delete(SessionStreamEvent).where(SessionStreamEvent.session_id == context.session.session_id))
    db_session.execute(delete(Alert).where(Alert.shop_id == context.shop.shop_id))
    db_session.execute(delete(AuditLog).where(AuditLog.shop_id == context.shop.shop_id))
    db_session.execute(delete(Confirmation).where(Confirmation.task_run_id.in_(task_run_ids)))
    db_session.execute(delete(OcrDocument).where(OcrDocument.shop_id == context.shop.shop_id))
    db_session.execute(delete(InventoryEvent).where(InventoryEvent.shop_id == context.shop.shop_id))
    # task_runs.source_message_id references messages.message_id, so task runs must go first.
    db_session.execute(delete(TaskRun).where(TaskRun.session_id == context.session.session_id))
    db_session.execute(delete(Message).where(Message.session_id == context.session.session_id))
    db_session.execute(delete(MediaUpload).where(MediaUpload.shop_id == context.shop.shop_id))
    db_session.execute(delete(InventoryItem).where(InventoryItem.shop_id == context.shop.shop_id))

    context.shop.default_low_stock_threshold = DEMO_LOW_STOCK_THRESHOLD
    context.shop.updated_at = now
    context.session.title = "数字员工工作群"
    context.session.participants = ["xiaoya", "laoli"]
    context.session.last_event_seq = 0
    context.session.last_message_at = None
    context.session.updated_at = now
    db_session.commit()


def _create_owner_message(
    db_session: Session,
    *,
    settings: Settings,
    session_id: str,
    client_request_id: str,
    message_type: str,
    text: str | None,
    media_ids: list[str],
) -> str:
    result = create_message(
        db_session,
        session_id=session_id,
        actor_type="owner",
        actor_id=settings.default_owner_actor_id,
        message_type=message_type,
        text=text,
        media_ids=media_ids,
        client_request_id=client_request_id,
    )
    return result.task_run_id


def _create_completed_media_upload(
    db_session: Session,
    *,
    settings: Settings,
    shop_id: str,
    media_type: str,
    file_name: str,
    content_type: str,
    size_bytes: int,
) -> str:
    create_result = create_media_upload(
        db_session,
        shop_id=shop_id,
        uploader_actor_type="owner",
        uploader_actor_id=settings.default_owner_actor_id,
        media_type=media_type,
        file_name=file_name,
        content_type=content_type,
        size_bytes=size_bytes,
    )
    mark_media_upload_complete(
        db_session,
        media_id=create_result.media_id,
        checksum_sha256=f"{create_result.media_id}-checksum",
        size_bytes=size_bytes,
    )
    return create_result.media_id


def _require_pending_confirmation_id(db_session: Session, *, task_run_id: str) -> str:
    confirmation = get_pending_confirmation_for_task_run(db_session, task_run_id=task_run_id)
    if confirmation is None:
        raise LookupError(f"Pending confirmation missing for task run {task_run_id}")
    return confirmation.confirmation_id


def _require_inventory_item(db_session: Session, *, shop_id: str, item_name: str) -> InventoryItem:
    item = db_session.scalar(
        select(InventoryItem).where(
            InventoryItem.shop_id == shop_id,
            InventoryItem.name == item_name,
            InventoryItem.is_active.is_(True),
        )
    )
    if item is None:
        raise LookupError(item_name)
    return item


def _seed_completed_stock_in_flow(
    db_session: Session,
    *,
    settings: Settings,
    context: BootstrapContext,
) -> InventoryItem:
    task_run_id = _create_owner_message(
        db_session,
        settings=settings,
        session_id=context.session.session_id,
        client_request_id="demo_stock_in_cola",
        message_type="text",
        text="restock cola today",
        media_ids=[],
    )
    process_task_run(db_session, task_run_id)
    confirmation_id = _require_pending_confirmation_id(db_session, task_run_id=task_run_id)
    commit_approved_stock_in_confirmation(
        db_session,
        confirmation_id=confirmation_id,
        payload_fields={
            "item_name": "Cola",
            "quantity": 8,
            "unit": "box",
            "price": 12.5,
        },
        approved_by_actor_id=settings.default_owner_actor_id,
    )
    return _require_inventory_item(
        db_session,
        shop_id=context.shop.shop_id,
        item_name="Cola",
    )


def _seed_approved_receipt_flow(
    db_session: Session,
    *,
    settings: Settings,
    context: BootstrapContext,
) -> None:
    media_id = _create_completed_media_upload(
        db_session,
        settings=settings,
        shop_id=context.shop.shop_id,
        media_type="receipt-image",
        file_name="receipt-approved-demo.jpg",
        content_type="image/jpeg",
        size_bytes=2048,
    )
    task_run_id = _create_owner_message(
        db_session,
        settings=settings,
        session_id=context.session.session_id,
        client_request_id="demo_receipt_approved",
        message_type="receipt-image",
        text=None,
        media_ids=[media_id],
    )
    process_task_run(db_session, task_run_id)
    confirmation_id = _require_pending_confirmation_id(db_session, task_run_id=task_run_id)
    commit_approved_receipt_stock_in_confirmation(
        db_session,
        confirmation_id=confirmation_id,
        payload_fields={
            "items": [
                {
                    "line_id": "line_1",
                    "item_name": "Red Bull 250ml",
                    "quantity": 7,
                    "unit": "can",
                    "price": 41.0,
                },
                {
                    "line_id": "line_2",
                    "item_name": "Coca Cola 500ml",
                    "quantity": 6,
                    "unit": "bottle",
                    "price": 12.0,
                },
            ]
        },
        approved_by_actor_id=settings.default_owner_actor_id,
    )


def _seed_open_low_stock_alert(
    db_session: Session,
    *,
    settings: Settings,
    context: BootstrapContext,
    cola_item: InventoryItem,
) -> None:
    submit_inventory_stock_out(
        db_session,
        shop_id=context.shop.shop_id,
        item_id=cola_item.item_id,
        expected_quantity=Decimal("8"),
        stock_out_quantity=Decimal("4"),
        reason="Walk-in sale",
        actor_id=settings.default_owner_actor_id,
    )


def _seed_pending_stock_out_confirmation(
    db_session: Session,
    *,
    settings: Settings,
    context: BootstrapContext,
) -> None:
    task_run_id = _create_owner_message(
        db_session,
        settings=settings,
        session_id=context.session.session_id,
        client_request_id="demo_stock_out_pending",
        message_type="text",
        text="stock out red bull for breakage",
        media_ids=[],
    )
    process_task_run(db_session, task_run_id)
    _require_pending_confirmation_id(db_session, task_run_id=task_run_id)


def _seed_pending_receipt_confirmation(
    db_session: Session,
    *,
    settings: Settings,
    context: BootstrapContext,
) -> None:
    media_id = _create_completed_media_upload(
        db_session,
        settings=settings,
        shop_id=context.shop.shop_id,
        media_type="receipt-image",
        file_name="receipt-pending-demo.jpg",
        content_type="image/jpeg",
        size_bytes=1024,
    )
    task_run_id = _create_owner_message(
        db_session,
        settings=settings,
        session_id=context.session.session_id,
        client_request_id="demo_receipt_pending",
        message_type="receipt-image",
        text=None,
        media_ids=[media_id],
    )
    process_task_run(db_session, task_run_id)
    _require_pending_confirmation_id(db_session, task_run_id=task_run_id)


def _build_summary(
    db_session: Session,
    *,
    context: BootstrapContext,
) -> DemoBootstrapSummary:
    inventory_item_names = list(
        db_session.scalars(
            select(InventoryItem.name)
            .where(
                InventoryItem.shop_id == context.shop.shop_id,
                InventoryItem.is_active.is_(True),
            )
            .order_by(InventoryItem.name.asc())
        )
    )
    pending_confirmation_types = list(
        db_session.scalars(
            select(Confirmation.confirmation_type)
            .join(TaskRun, TaskRun.task_run_id == Confirmation.task_run_id)
            .where(
                TaskRun.session_id == context.session.session_id,
                Confirmation.status == "pending",
            )
            .order_by(Confirmation.confirmation_type.asc(), Confirmation.confirmation_id.asc())
        )
    )
    open_low_stock_item_names = list(
        db_session.scalars(
            select(InventoryItem.name)
            .join(Alert, Alert.item_id == InventoryItem.item_id)
            .where(
                Alert.shop_id == context.shop.shop_id,
                Alert.status == "open",
            )
            .order_by(InventoryItem.name.asc(), Alert.alert_id.asc())
        )
    )
    message_count = int(
        db_session.scalar(
            select(func.count())
            .select_from(Message)
            .where(Message.session_id == context.session.session_id)
        )
        or 0
    )
    task_run_count = int(
        db_session.scalar(
            select(func.count())
            .select_from(TaskRun)
            .where(TaskRun.session_id == context.session.session_id)
        )
        or 0
    )

    return DemoBootstrapSummary(
        shop_id=context.shop.shop_id,
        session_id=context.session.session_id,
        inventory_item_count=len(inventory_item_names),
        inventory_item_names=inventory_item_names,
        pending_confirmation_count=len(pending_confirmation_types),
        pending_confirmation_types=pending_confirmation_types,
        open_low_stock_alert_count=len(open_low_stock_item_names),
        open_low_stock_item_names=open_low_stock_item_names,
        message_count=message_count,
        task_run_count=task_run_count,
    )


def bootstrap_demo_state(db_session: Session) -> DemoBootstrapSummary:
    settings = get_settings()
    context = ensure_default_context(db_session)
    _reset_default_context_state(
        db_session,
        context=context,
    )
    context = ensure_default_context(db_session)

    cola_item = _seed_completed_stock_in_flow(
        db_session,
        settings=settings,
        context=context,
    )
    _seed_approved_receipt_flow(
        db_session,
        settings=settings,
        context=context,
    )
    _seed_open_low_stock_alert(
        db_session,
        settings=settings,
        context=context,
        cola_item=cola_item,
    )
    _seed_pending_stock_out_confirmation(
        db_session,
        settings=settings,
        context=context,
    )
    _seed_pending_receipt_confirmation(
        db_session,
        settings=settings,
        context=context,
    )

    db_session.commit()
    db_session.expire_all()
    context = ensure_default_context(db_session)
    return _build_summary(db_session, context=context)
