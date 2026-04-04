from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.ids import new_prefixed_id
from app.models import InventoryEvent, InventoryItem


def append_stock_in_event(
    db_session: Session,
    *,
    item: InventoryItem,
    quantity: Decimal,
    price: Decimal,
    task_run_id: str,
    created_by: str,
) -> InventoryEvent:
    now = datetime.now(UTC).replace(tzinfo=None)
    quantity_after = Decimal(item.current_stock) + quantity
    event = InventoryEvent(
        inventory_event_id=new_prefixed_id("inv_evt"),
        shop_id=item.shop_id,
        item_id=item.item_id,
        event_type="stock-in",
        quantity_delta=quantity,
        quantity_after=quantity_after,
        unit=item.default_unit,
        price=price,
        source="voice-confirmed",
        task_run_id=task_run_id,
        created_by=created_by,
        reason=None,
        created_at=now,
    )
    item.current_stock = quantity_after
    item.current_price = price
    item.updated_at = now
    db_session.add(event)
    db_session.flush()
    return event


def append_correction_event(
    db_session: Session,
    *,
    item: InventoryItem,
    corrected_quantity: Decimal,
    actor_id: str,
    reason: str,
) -> InventoryEvent:
    now = datetime.now(UTC).replace(tzinfo=None)
    previous_quantity = Decimal(item.current_stock)
    quantity_delta = corrected_quantity - previous_quantity
    event = InventoryEvent(
        inventory_event_id=new_prefixed_id("inv_evt"),
        shop_id=item.shop_id,
        item_id=item.item_id,
        event_type="correction",
        quantity_delta=quantity_delta,
        quantity_after=corrected_quantity,
        unit=item.default_unit,
        price=item.current_price,
        source="owner-correction",
        task_run_id=None,
        created_by=actor_id,
        reason=reason,
        created_at=now,
    )
    item.current_stock = corrected_quantity
    item.updated_at = now
    db_session.add(event)
    db_session.flush()
    return event
