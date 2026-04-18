from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import V2InventoryItem, V2InventoryLedgerEvent, V2InventoryStockSnapshot
from app.services.v2_inventory import V2InventoryItemNotFoundError
from app.services.v2_time import utc_now_naive


@dataclass(frozen=True)
class V2InventoryProjectionReplayResult:
    tenant_id: str
    shop_id: str
    inventory_item_id: str | None
    replayed_item_count: int
    replayed_snapshot_count: int
    deleted_snapshot_count: int
    ledger_event_count: int
    replayed_at: datetime


@dataclass
class _InventoryProjectionState:
    current_quantity: Decimal
    current_price: Decimal | None
    updated_at: datetime


def _require_inventory_item(
    db_session: Session,
    *,
    tenant_id: str,
    inventory_item_id: str,
) -> None:
    item = db_session.scalar(
        select(V2InventoryItem).where(
            V2InventoryItem.tenant_id == tenant_id,
            V2InventoryItem.inventory_item_id == inventory_item_id,
        )
    )
    if item is None:
        raise V2InventoryItemNotFoundError(inventory_item_id)


def replay_v2_inventory_stock_projection(
    db_session: Session,
    *,
    tenant_id: str,
    shop_id: str,
    inventory_item_id: str | None = None,
    replayed_at: datetime | None = None,
) -> V2InventoryProjectionReplayResult:
    replay_time = replayed_at or utc_now_naive()
    if inventory_item_id is not None:
        _require_inventory_item(
            db_session,
            tenant_id=tenant_id,
            inventory_item_id=inventory_item_id,
        )

    event_statement = select(V2InventoryLedgerEvent).where(
        V2InventoryLedgerEvent.tenant_id == tenant_id,
        V2InventoryLedgerEvent.shop_id == shop_id,
    )
    snapshot_statement = select(V2InventoryStockSnapshot).where(
        V2InventoryStockSnapshot.tenant_id == tenant_id,
        V2InventoryStockSnapshot.shop_id == shop_id,
    )
    if inventory_item_id is not None:
        event_statement = event_statement.where(V2InventoryLedgerEvent.inventory_item_id == inventory_item_id)
        snapshot_statement = snapshot_statement.where(
            V2InventoryStockSnapshot.inventory_item_id == inventory_item_id
        )

    events = db_session.scalars(
        event_statement.order_by(
            V2InventoryLedgerEvent.occurred_at.asc(),
            V2InventoryLedgerEvent.event_id.asc(),
        )
    ).all()
    existing_snapshots = {
        snapshot.inventory_item_id: snapshot
        for snapshot in db_session.scalars(snapshot_statement).all()
    }

    states: dict[str, _InventoryProjectionState] = {}
    for event in events:
        state = states.setdefault(
            event.inventory_item_id,
            _InventoryProjectionState(
                current_quantity=Decimal("0"),
                current_price=None,
                updated_at=event.occurred_at,
            ),
        )
        state.current_quantity += Decimal(event.quantity_delta)
        if event.price is not None:
            state.current_price = Decimal(event.price)
        state.updated_at = event.occurred_at

    replayed_snapshot_count = 0
    for item_id, state in states.items():
        snapshot = existing_snapshots.pop(item_id, None)
        if snapshot is None:
            snapshot = V2InventoryStockSnapshot(
                snapshot_id=f"vsnapshot_{uuid.uuid4().hex}"[:40],
                tenant_id=tenant_id,
                shop_id=shop_id,
                inventory_item_id=item_id,
                current_quantity=Decimal("0"),
                current_price=None,
                low_stock_threshold=None,
                updated_at=state.updated_at,
            )
            db_session.add(snapshot)

        snapshot.current_quantity = state.current_quantity
        snapshot.current_price = state.current_price
        snapshot.updated_at = state.updated_at
        replayed_snapshot_count += 1

    deleted_snapshot_count = 0
    for stale_snapshot in existing_snapshots.values():
        db_session.delete(stale_snapshot)
        deleted_snapshot_count += 1

    db_session.flush()
    return V2InventoryProjectionReplayResult(
        tenant_id=tenant_id,
        shop_id=shop_id,
        inventory_item_id=inventory_item_id,
        replayed_item_count=len(states),
        replayed_snapshot_count=replayed_snapshot_count,
        deleted_snapshot_count=deleted_snapshot_count,
        ledger_event_count=len(events),
        replayed_at=replay_time,
    )
