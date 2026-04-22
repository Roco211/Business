from datetime import datetime, timezone
UTC = timezone.utc
from decimal import Decimal

from sqlalchemy import select

from app.models import Alert, Confirmation, InventoryItem, TaskRun
from app.runtime.processor import process_task_run
from app.services.alerts import list_low_stock_alerts, refresh_low_stock_alert_for_item
from app.services.approved_stock_in_commits import commit_approved_stock_in_confirmation
from app.services.bootstrap import ensure_default_context
from app.services.messages import create_message


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _insert_item(
    db_session,
    *,
    item_id: str,
    name: str,
    stock: Decimal,
    threshold: Decimal | None,
) -> InventoryItem:
    context = ensure_default_context(db_session)
    item = InventoryItem(
        item_id=item_id,
        shop_id=context.shop.shop_id,
        sku=None,
        name=name,
        category=None,
        barcode=None,
        default_unit="box",
        current_stock=stock,
        current_price=Decimal("12.5"),
        low_stock_threshold=threshold,
        image_media_id=None,
        is_active=True,
        created_at=_now(),
        updated_at=_now(),
    )
    db_session.add(item)
    db_session.commit()
    return item


def _create_pending_stock_in_confirmation(db_session, *, client_request_id: str) -> tuple[Confirmation, TaskRun]:
    context = ensure_default_context(db_session)
    message_result = create_message(
        db_session,
        session_id=context.session.session_id,
        actor_type="owner",
        actor_id="owner_default",
        message_type="text",
        text="restock apples today",
        media_ids=[],
        client_request_id=client_request_id,
    )
    runtime_result = process_task_run(db_session, message_result.task_run_id)
    assert runtime_result.status == "awaiting-confirmation"
    confirmation = db_session.scalar(
        select(Confirmation).where(Confirmation.task_run_id == message_result.task_run_id)
    )
    task_run = db_session.get(TaskRun, message_result.task_run_id)
    assert confirmation is not None
    assert task_run is not None
    return confirmation, task_run


def test_refresh_low_stock_alert_creates_open_alert_for_low_stock_item(db_session) -> None:
    item = _insert_item(
        db_session,
        item_id="item_low_alert_open",
        name="Apple",
        stock=Decimal("2"),
        threshold=Decimal("5"),
    )

    alert = refresh_low_stock_alert_for_item(db_session, item=item)
    persisted = db_session.get(Alert, alert.alert_id if alert is not None else None)

    assert alert is not None
    assert persisted is not None
    assert persisted.alert_type == "low-stock"
    assert persisted.status == "open"
    assert persisted.stock == Decimal("2")
    assert persisted.threshold == Decimal("5")


def test_refresh_low_stock_alert_updates_existing_open_alert_without_duplication(db_session) -> None:
    item = _insert_item(
        db_session,
        item_id="item_low_alert_update",
        name="Orange",
        stock=Decimal("1"),
        threshold=Decimal("5"),
    )
    first_alert = refresh_low_stock_alert_for_item(db_session, item=item)

    item.current_stock = Decimal("2")
    item.low_stock_threshold = Decimal("4")
    item.updated_at = _now()
    updated_alert = refresh_low_stock_alert_for_item(db_session, item=item)
    alerts = db_session.scalars(select(Alert).where(Alert.item_id == item.item_id)).all()

    assert first_alert is not None
    assert updated_alert is not None
    assert updated_alert.alert_id == first_alert.alert_id
    assert updated_alert.stock == Decimal("2")
    assert updated_alert.threshold == Decimal("4")
    assert len(alerts) == 1


def test_refresh_low_stock_alert_resolves_open_alert_when_stock_recovers(db_session) -> None:
    item = _insert_item(
        db_session,
        item_id="item_low_alert_resolve",
        name="Banana",
        stock=Decimal("1"),
        threshold=Decimal("5"),
    )
    alert = refresh_low_stock_alert_for_item(db_session, item=item)

    item.current_stock = Decimal("6")
    item.updated_at = _now()
    resolved_alert = refresh_low_stock_alert_for_item(db_session, item=item)
    persisted = db_session.get(Alert, alert.alert_id if alert is not None else None)

    assert resolved_alert is None
    assert persisted is not None
    assert persisted.status == "resolved"
    assert persisted.resolved_at is not None


def test_commit_approved_stock_in_confirmation_refreshes_low_stock_alert_state(db_session) -> None:
    context = ensure_default_context(db_session)
    context.shop.default_low_stock_threshold = Decimal("5")
    db_session.commit()

    confirmation, _ = _create_pending_stock_in_confirmation(
        db_session,
        client_request_id="alerts_commit_integration_open",
    )
    commit_result = commit_approved_stock_in_confirmation(
        db_session,
        confirmation_id=confirmation.confirmation_id,
        payload_fields={"item_name": "Apple", "quantity": 3, "unit": "box", "price": 12.5},
        approved_by_actor_id="owner_default",
    )

    open_alerts = list_low_stock_alerts(db_session, shop_id=context.shop.shop_id, limit=20)
    assert [alert.item_id for alert in open_alerts.items] == [commit_result.inventory_item.item_id]

    confirmation_two, _ = _create_pending_stock_in_confirmation(
        db_session,
        client_request_id="alerts_commit_integration_resolve",
    )
    commit_approved_stock_in_confirmation(
        db_session,
        confirmation_id=confirmation_two.confirmation_id,
        payload_fields={
            "item_id": commit_result.inventory_item.item_id,
            "quantity": 4,
            "unit": "box",
            "price": 12.5,
        },
        approved_by_actor_id="owner_default",
    )

    open_alerts_after = list_low_stock_alerts(db_session, shop_id=context.shop.shop_id, limit=20)

    assert open_alerts_after.items == []
