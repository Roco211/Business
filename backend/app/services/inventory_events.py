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
