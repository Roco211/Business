from datetime import datetime, timezone
UTC = timezone.utc
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models import AuditLog, InventoryEvent, InventoryItem, SessionStreamEvent
from app.services.alerts import list_low_stock_alerts
from app.services.bootstrap import ensure_default_context
from app.services.inventory_corrections import (
    InventoryCorrectionConflictError,
    InventoryCorrectionValidationError,
    submit_inventory_correction,
)


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _insert_item(
    db_session,
    *,
    item_id: str,
    name: str,
    stock: Decimal,
    threshold: Decimal | None,
    is_active: bool = True,
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
        current_price=Decimal("12.50"),
        low_stock_threshold=threshold,
        image_media_id=None,
        is_active=is_active,
        created_at=_now(),
        updated_at=_now(),
    )
    db_session.add(item)
    db_session.commit()
    return item


def test_submit_inventory_correction_writes_event_audit_and_resolves_alert(db_session) -> None:
    context = ensure_default_context(db_session)
    item = _insert_item(
        db_session,
        item_id="item_correction_success",
        name="Apple",
        stock=Decimal("2"),
        threshold=Decimal("5"),
    )

    result = submit_inventory_correction(
        db_session,
        shop_id=context.shop.shop_id,
        item_id=item.item_id,
        expected_quantity=Decimal("2"),
        corrected_quantity=Decimal("6"),
        reason="Physical count differs from projected inventory",
        actor_id="owner_default",
    )

    persisted_item = db_session.get(InventoryItem, item.item_id)
    persisted_event = db_session.get(InventoryEvent, result.inventory_event.inventory_event_id)
    persisted_audit = db_session.get(AuditLog, result.audit_log.audit_log_id)
    stream_events = db_session.scalars(
        select(SessionStreamEvent)
        .where(SessionStreamEvent.session_id == context.session.session_id)
        .order_by(SessionStreamEvent.seq.asc())
    ).all()
    open_alerts = list_low_stock_alerts(db_session, shop_id=context.shop.shop_id, limit=20)

    assert persisted_item is not None
    assert persisted_item.current_stock == Decimal("6")
    assert persisted_event is not None
    assert persisted_event.event_type == "correction"
    assert persisted_event.quantity_delta == Decimal("4")
    assert persisted_event.quantity_after == Decimal("6")
    assert persisted_event.reason == "Physical count differs from projected inventory"
    assert persisted_audit is not None
    assert persisted_audit.action == "inventory.correction_submitted"
    assert persisted_audit.metadata_json["previous_quantity"] == 2.0
    assert persisted_audit.metadata_json["corrected_quantity"] == 6.0
    assert [event.event_type for event in stream_events] == [
        "inventory.updated",
        "alert.updated",
    ]
    assert stream_events[0].payload["inventory_event_id"] == persisted_event.inventory_event_id
    assert stream_events[1].payload["item_id"] == item.item_id
    assert open_alerts.items == []


def test_submit_inventory_correction_opens_low_stock_alert_when_quantity_below_threshold(db_session) -> None:
    context = ensure_default_context(db_session)
    item = _insert_item(
        db_session,
        item_id="item_correction_low_stock",
        name="Orange",
        stock=Decimal("8"),
        threshold=Decimal("5"),
    )

    submit_inventory_correction(
        db_session,
        shop_id=context.shop.shop_id,
        item_id=item.item_id,
        expected_quantity=Decimal("8"),
        corrected_quantity=Decimal("3"),
        reason="Physical recount found fewer boxes",
        actor_id="owner_default",
    )

    open_alerts = list_low_stock_alerts(db_session, shop_id=context.shop.shop_id, limit=20)

    assert len(open_alerts.items) == 1
    assert open_alerts.items[0].item_id == item.item_id
    assert open_alerts.items[0].stock == Decimal("3")


def test_submit_inventory_correction_rejects_negative_quantity_and_blank_reason(db_session) -> None:
    context = ensure_default_context(db_session)
    item = _insert_item(
        db_session,
        item_id="item_correction_validation",
        name="Banana",
        stock=Decimal("2"),
        threshold=Decimal("5"),
    )

    with pytest.raises(InventoryCorrectionValidationError):
        submit_inventory_correction(
            db_session,
            shop_id=context.shop.shop_id,
            item_id=item.item_id,
            expected_quantity=Decimal("2"),
            corrected_quantity=Decimal("-1"),
            reason="counted",
            actor_id="owner_default",
        )

    with pytest.raises(InventoryCorrectionValidationError):
        submit_inventory_correction(
            db_session,
            shop_id=context.shop.shop_id,
            item_id=item.item_id,
            expected_quantity=Decimal("2"),
            corrected_quantity=Decimal("1"),
            reason="   ",
            actor_id="owner_default",
        )


def test_submit_inventory_correction_rejects_stale_expected_quantity(db_session) -> None:
    context = ensure_default_context(db_session)
    item = _insert_item(
        db_session,
        item_id="item_correction_stale_quantity",
        name="Grape",
        stock=Decimal("5"),
        threshold=Decimal("5"),
    )

    with pytest.raises(InventoryCorrectionConflictError):
        submit_inventory_correction(
            db_session,
            shop_id=context.shop.shop_id,
            item_id=item.item_id,
            expected_quantity=Decimal("4"),
            corrected_quantity=Decimal("6"),
            reason="Inventory recount",
            actor_id="owner_default",
        )

    persisted_item = db_session.get(InventoryItem, item.item_id)
    assert persisted_item is not None
    assert persisted_item.current_stock == Decimal("5")


def test_submit_inventory_correction_rejects_inactive_item(db_session) -> None:
    context = ensure_default_context(db_session)
    item = _insert_item(
        db_session,
        item_id="item_correction_inactive",
        name="Pear",
        stock=Decimal("2"),
        threshold=Decimal("5"),
        is_active=False,
    )

    with pytest.raises(InventoryCorrectionConflictError):
        submit_inventory_correction(
            db_session,
            shop_id=context.shop.shop_id,
            item_id=item.item_id,
            expected_quantity=Decimal("2"),
            corrected_quantity=Decimal("3"),
            reason="Inventory recount",
            actor_id="owner_default",
        )

    assert db_session.scalars(select(InventoryEvent)).all() == []
