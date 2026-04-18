from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import V2InventoryItem, V2InventoryLedgerEvent, V2InventoryStockSnapshot, V2TaskRun
from app.services.v2_time import utc_now_naive


class V2InventoryPayloadValidationError(ValueError):
    pass


class V2InventoryItemNotFoundError(LookupError):
    pass


class V2InventoryUnitMismatchError(ValueError):
    pass


@dataclass(frozen=True)
class V2ApprovedStockInPayload:
    item_id: str | None
    item_name: str | None
    quantity: Decimal
    unit: str
    price: Decimal


@dataclass(frozen=True)
class V2CommittedStockInResult:
    item: V2InventoryItem
    snapshot: V2InventoryStockSnapshot
    event: V2InventoryLedgerEvent


def list_v2_inventory_items(
    db_session: Session,
    *,
    tenant_id: str,
    query: str | None,
    limit: int,
) -> list[V2InventoryItem]:
    safe_limit = max(1, min(limit, 50))
    statement = select(V2InventoryItem).where(V2InventoryItem.tenant_id == tenant_id)
    if query is not None and query.strip():
        statement = statement.where(V2InventoryItem.name.ilike(f"%{query.strip()}%"))
    statement = statement.order_by(V2InventoryItem.updated_at.desc(), V2InventoryItem.inventory_item_id.desc()).limit(
        safe_limit
    )
    return list(db_session.scalars(statement))


def list_v2_inventory_stock(
    db_session: Session,
    *,
    tenant_id: str,
    shop_id: str,
    limit: int,
) -> list[tuple[V2InventoryStockSnapshot, V2InventoryItem]]:
    safe_limit = max(1, min(limit, 50))
    statement = (
        select(V2InventoryStockSnapshot, V2InventoryItem)
        .join(
            V2InventoryItem,
            V2InventoryItem.inventory_item_id == V2InventoryStockSnapshot.inventory_item_id,
        )
        .where(
            V2InventoryStockSnapshot.tenant_id == tenant_id,
            V2InventoryStockSnapshot.shop_id == shop_id,
        )
        .order_by(V2InventoryStockSnapshot.updated_at.desc(), V2InventoryStockSnapshot.snapshot_id.desc())
        .limit(safe_limit)
    )
    return list(db_session.execute(statement).all())


def list_v2_inventory_events(
    db_session: Session,
    *,
    tenant_id: str,
    shop_id: str,
    limit: int,
) -> list[tuple[V2InventoryLedgerEvent, V2InventoryItem]]:
    safe_limit = max(1, min(limit, 50))
    statement = (
        select(V2InventoryLedgerEvent, V2InventoryItem)
        .join(
            V2InventoryItem,
            V2InventoryItem.inventory_item_id == V2InventoryLedgerEvent.inventory_item_id,
        )
        .where(
            V2InventoryLedgerEvent.tenant_id == tenant_id,
            V2InventoryLedgerEvent.shop_id == shop_id,
        )
        .order_by(V2InventoryLedgerEvent.occurred_at.desc(), V2InventoryLedgerEvent.event_id.desc())
        .limit(safe_limit)
    )
    return list(db_session.execute(statement).all())


def _parse_v2_stock_in_payload(payload: dict[str, object]) -> V2ApprovedStockInPayload:
    raw_item_id = payload.get("item_id")
    item_id = str(raw_item_id).strip() or None if raw_item_id is not None else None
    raw_item_name = payload.get("item_name")
    item_name = raw_item_name.strip() if isinstance(raw_item_name, str) and raw_item_name.strip() else None
    raw_unit = payload.get("unit")
    unit = raw_unit.strip() if isinstance(raw_unit, str) and raw_unit.strip() else None

    if item_id is None and item_name is None:
        raise V2InventoryPayloadValidationError("item_name is required when item_id is absent")
    if unit is None:
        raise V2InventoryPayloadValidationError("unit is required")

    try:
        quantity = Decimal(str(payload.get("quantity")))
        price = Decimal(str(payload.get("price")))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise V2InventoryPayloadValidationError("quantity and price must be numeric") from exc

    if quantity <= 0:
        raise V2InventoryPayloadValidationError("quantity must be > 0")
    if price < 0:
        raise V2InventoryPayloadValidationError("price must be >= 0")

    return V2ApprovedStockInPayload(
        item_id=item_id,
        item_name=item_name,
        quantity=quantity,
        unit=unit,
        price=price,
    )


def _require_v2_task_run(
    db_session: Session,
    *,
    tenant_id: str,
    shop_id: str,
    task_run_id: str,
) -> V2TaskRun:
    task_run = db_session.scalar(
        select(V2TaskRun).where(
            V2TaskRun.task_run_id == task_run_id,
            V2TaskRun.tenant_id == tenant_id,
            V2TaskRun.shop_id == shop_id,
        )
    )
    if task_run is None:
        raise LookupError(task_run_id)
    return task_run


def _resolve_v2_inventory_item_for_stock_in(
    db_session: Session,
    *,
    tenant_id: str,
    payload: V2ApprovedStockInPayload,
    now,
) -> V2InventoryItem:
    if payload.item_id is not None:
        item = db_session.scalar(
            select(V2InventoryItem).where(
                V2InventoryItem.inventory_item_id == payload.item_id,
                V2InventoryItem.tenant_id == tenant_id,
            )
        )
        if item is None:
            raise V2InventoryItemNotFoundError(payload.item_id)
    else:
        item = db_session.scalar(
            select(V2InventoryItem).where(
                V2InventoryItem.tenant_id == tenant_id,
                V2InventoryItem.name == (payload.item_name or ""),
            )
        )
        if item is None:
            item = V2InventoryItem(
                inventory_item_id=f"vitem_{uuid.uuid4().hex}"[:40],
                tenant_id=tenant_id,
                sku=None,
                name=payload.item_name or "",
                barcode=None,
                default_unit=payload.unit,
                status="active",
                created_at=now,
                updated_at=now,
            )
            db_session.add(item)
            db_session.flush()

    if item.default_unit != payload.unit:
        raise V2InventoryUnitMismatchError(item.inventory_item_id)
    return item


def _get_or_create_v2_stock_snapshot(
    db_session: Session,
    *,
    tenant_id: str,
    shop_id: str,
    inventory_item_id: str,
    price: Decimal,
    now,
) -> V2InventoryStockSnapshot:
    snapshot = db_session.scalar(
        select(V2InventoryStockSnapshot).where(
            V2InventoryStockSnapshot.tenant_id == tenant_id,
            V2InventoryStockSnapshot.shop_id == shop_id,
            V2InventoryStockSnapshot.inventory_item_id == inventory_item_id,
        )
    )
    if snapshot is not None:
        return snapshot

    snapshot = V2InventoryStockSnapshot(
        snapshot_id=f"vsnapshot_{uuid.uuid4().hex}"[:40],
        tenant_id=tenant_id,
        shop_id=shop_id,
        inventory_item_id=inventory_item_id,
        current_quantity=Decimal("0"),
        current_price=price,
        low_stock_threshold=None,
        updated_at=now,
    )
    db_session.add(snapshot)
    db_session.flush()
    return snapshot


def commit_v2_inventory_stock_in(
    db_session: Session,
    *,
    tenant_id: str,
    shop_id: str,
    task_run_id: str,
    created_by_account_id: str,
    payload: dict[str, object],
) -> V2CommittedStockInResult:
    approved_payload = _parse_v2_stock_in_payload(payload)
    _require_v2_task_run(
        db_session,
        tenant_id=tenant_id,
        shop_id=shop_id,
        task_run_id=task_run_id,
    )
    now = utc_now_naive()
    item = _resolve_v2_inventory_item_for_stock_in(
        db_session,
        tenant_id=tenant_id,
        payload=approved_payload,
        now=now,
    )
    snapshot = _get_or_create_v2_stock_snapshot(
        db_session,
        tenant_id=tenant_id,
        shop_id=shop_id,
        inventory_item_id=item.inventory_item_id,
        price=approved_payload.price,
        now=now,
    )
    quantity_after = Decimal(snapshot.current_quantity) + approved_payload.quantity
    snapshot.current_quantity = quantity_after
    snapshot.current_price = approved_payload.price
    snapshot.updated_at = now
    item.updated_at = now
    event = V2InventoryLedgerEvent(
        event_id=f"vevent_{uuid.uuid4().hex}"[:40],
        tenant_id=tenant_id,
        shop_id=shop_id,
        inventory_item_id=item.inventory_item_id,
        event_type="stock_in",
        quantity_delta=approved_payload.quantity,
        quantity_after=quantity_after,
        unit=approved_payload.unit,
        price=approved_payload.price,
        source_type="task_run",
        source_id=task_run_id,
        reason="approved stock in",
        created_by_account_id=created_by_account_id,
        occurred_at=now,
    )
    db_session.add(event)
    db_session.flush()
    return V2CommittedStockInResult(item=item, snapshot=snapshot, event=event)
