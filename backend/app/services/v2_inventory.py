from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any
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


class V2InventoryCorrectionValidationError(ValueError):
    pass


class V2InventoryCorrectionConflictError(ValueError):
    pass


class V2InventoryCorrectionItemNotFoundError(LookupError):
    pass


class V2InventoryStockOutValidationError(ValueError):
    pass


class V2InventoryStockOutConflictError(ValueError):
    pass


class V2InventoryStockOutItemNotFoundError(LookupError):
    pass


class V2InventoryStockInValidationError(ValueError):
    pass


class V2InventoryStockInItemNotFoundError(LookupError):
    pass


_UNSET = object()


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


@dataclass(frozen=True)
class V2InventoryCorrectionResult:
    snapshot: V2InventoryStockSnapshot
    event: V2InventoryLedgerEvent


@dataclass(frozen=True)
class V2InventoryStockOutResult:
    item: V2InventoryItem
    snapshot: V2InventoryStockSnapshot
    event: V2InventoryLedgerEvent


@dataclass(frozen=True)
class V2InventoryStockInResult:
    item: V2InventoryItem
    snapshot: V2InventoryStockSnapshot
    event: V2InventoryLedgerEvent


@dataclass(frozen=True)
class V2ApprovedStockOutPayload:
    inventory_item_id: str
    expected_quantity: Decimal
    stock_out_quantity: Decimal
    reason: str


def _normalize_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _normalize_required_text(value: str | None, field_name: str) -> str:
    normalized = _normalize_optional_text(value)
    if normalized is None:
        raise V2InventoryPayloadValidationError(f"{field_name} is required")
    return normalized


def _serialize_v2_inventory_item_not_deleted_query(tenant_id: str, inventory_item_id: str):
    return select(V2InventoryItem).where(
        V2InventoryItem.inventory_item_id == inventory_item_id,
        V2InventoryItem.tenant_id == tenant_id,
        V2InventoryItem.status == "active",
    )


def list_v2_inventory_items(
    db_session: Session,
    *,
    tenant_id: str,
    query: str | None,
    limit: int,
) -> list[V2InventoryItem]:
    safe_limit = max(1, min(limit, 50))
    statement = select(V2InventoryItem).where(
        V2InventoryItem.tenant_id == tenant_id,
        V2InventoryItem.status == "active",
    )
    if query is not None and query.strip():
        statement = statement.where(V2InventoryItem.name.ilike(f"%{query.strip()}%"))
    statement = statement.order_by(V2InventoryItem.updated_at.desc(), V2InventoryItem.inventory_item_id.desc()).limit(
        safe_limit
    )
    return list(db_session.scalars(statement))


def get_v2_inventory_item(
    db_session: Session,
    *,
    tenant_id: str,
    inventory_item_id: str,
) -> V2InventoryItem:
    item = db_session.scalar(_serialize_v2_inventory_item_not_deleted_query(tenant_id, inventory_item_id))
    if item is None:
        raise V2InventoryItemNotFoundError(inventory_item_id)
    return item


def create_v2_inventory_item(
    db_session: Session,
    *,
    tenant_id: str,
    sku: str | None,
    name: str,
    barcode: str | None,
    default_unit: str,
) -> V2InventoryItem:
    now = utc_now_naive()
    item = V2InventoryItem(
        inventory_item_id=f"vitem_{uuid.uuid4().hex}"[:40],
        tenant_id=tenant_id,
        sku=_normalize_optional_text(sku),
        name=_normalize_required_text(name, "name"),
        barcode=_normalize_optional_text(barcode),
        default_unit=_normalize_required_text(default_unit, "default_unit"),
        status="active",
        created_at=now,
        updated_at=now,
    )
    db_session.add(item)
    db_session.commit()
    db_session.refresh(item)
    return item


def update_v2_inventory_item(
    db_session: Session,
    *,
    tenant_id: str,
    inventory_item_id: str,
    sku: Any = _UNSET,
    name: Any = _UNSET,
    barcode: Any = _UNSET,
    default_unit: Any = _UNSET,
) -> V2InventoryItem:
    item = get_v2_inventory_item(db_session, tenant_id=tenant_id, inventory_item_id=inventory_item_id)
    if sku is not _UNSET:
        item.sku = _normalize_optional_text(sku)
    if name is not _UNSET:
        item.name = _normalize_required_text(name, "name")
    if barcode is not _UNSET:
        item.barcode = _normalize_optional_text(barcode)
    if default_unit is not _UNSET:
        item.default_unit = _normalize_required_text(default_unit, "default_unit")
    item.updated_at = utc_now_naive()
    db_session.commit()
    db_session.refresh(item)
    return item


def delete_v2_inventory_item(
    db_session: Session,
    *,
    tenant_id: str,
    inventory_item_id: str,
) -> V2InventoryItem:
    item = get_v2_inventory_item(db_session, tenant_id=tenant_id, inventory_item_id=inventory_item_id)
    item.status = "deleted"
    item.updated_at = utc_now_naive()
    db_session.commit()
    db_session.refresh(item)
    return item


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
            V2InventoryItem.tenant_id == tenant_id,
            V2InventoryItem.status == "active",
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
            V2InventoryItem.tenant_id == tenant_id,
            V2InventoryItem.status == "active",
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


def validate_v2_stock_in_draft_payload(payload: dict[str, object]) -> None:
    _parse_v2_stock_in_payload(payload)


def _parse_v2_stock_out_payload(payload: dict[str, object]) -> V2ApprovedStockOutPayload:
    inventory_item_id = str(payload.get("inventory_item_id") or "").strip()
    if not inventory_item_id:
        raise V2InventoryStockOutValidationError("inventory_item_id is required")

    normalized_reason = str(payload.get("reason") or "").strip()
    if not normalized_reason:
        raise V2InventoryStockOutValidationError("reason is required")

    try:
        normalized_expected_quantity = Decimal(str(payload.get("expected_quantity")))
        normalized_stock_out_quantity = Decimal(str(payload.get("stock_out_quantity")))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise V2InventoryStockOutValidationError(
            "expected_quantity and stock_out_quantity must be numeric"
        ) from exc

    if normalized_expected_quantity < 0:
        raise V2InventoryStockOutValidationError("expected_quantity must be >= 0")
    if normalized_stock_out_quantity <= 0:
        raise V2InventoryStockOutValidationError("stock_out_quantity must be > 0")

    return V2ApprovedStockOutPayload(
        inventory_item_id=inventory_item_id,
        expected_quantity=normalized_expected_quantity,
        stock_out_quantity=normalized_stock_out_quantity,
        reason=normalized_reason,
    )


def validate_v2_stock_out_draft_payload(payload: dict[str, object]) -> None:
    _parse_v2_stock_out_payload(payload)


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


def _require_v2_inventory_snapshot(
    db_session: Session,
    *,
    tenant_id: str,
    shop_id: str,
    inventory_item_id: str,
) -> V2InventoryStockSnapshot:
    snapshot = db_session.scalar(
        select(V2InventoryStockSnapshot).where(
            V2InventoryStockSnapshot.tenant_id == tenant_id,
            V2InventoryStockSnapshot.shop_id == shop_id,
            V2InventoryStockSnapshot.inventory_item_id == inventory_item_id,
        )
    )
    if snapshot is None:
        raise V2InventoryCorrectionItemNotFoundError(inventory_item_id)
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


def submit_v2_inventory_stock_in(
    db_session: Session,
    *,
    tenant_id: str,
    shop_id: str,
    inventory_item_id: str | None,
    item_name: str | None,
    stock_in_quantity: Decimal,
    unit: str,
    price: Decimal,
    reason: str | None,
    created_by_account_id: str,
) -> V2InventoryStockInResult:
    try:
        approved_payload = _parse_v2_stock_in_payload(
            {
                "item_id": inventory_item_id,
                "item_name": item_name,
                "quantity": stock_in_quantity,
                "unit": unit,
                "price": price,
            }
        )
        normalized_reason = (reason or "manual stock in").strip() or "manual stock in"
        now = utc_now_naive()
        try:
            item = _resolve_v2_inventory_item_for_stock_in(
                db_session,
                tenant_id=tenant_id,
                payload=approved_payload,
                now=now,
            )
        except V2InventoryItemNotFoundError as exc:
            raise V2InventoryStockInItemNotFoundError(str(exc)) from exc
        except V2InventoryUnitMismatchError as exc:
            raise V2InventoryStockInValidationError("unit does not match inventory item default_unit") from exc

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
            source_type="inventory_stock_in",
            source_id=item.inventory_item_id,
            reason=normalized_reason,
            created_by_account_id=created_by_account_id,
            occurred_at=now,
        )
        db_session.add(event)
        db_session.commit()
        return V2InventoryStockInResult(item=item, snapshot=snapshot, event=event)
    except V2InventoryStockInItemNotFoundError:
        db_session.rollback()
        raise
    except V2InventoryStockInValidationError:
        db_session.rollback()
        raise
    except V2InventoryPayloadValidationError as exc:
        db_session.rollback()
        raise V2InventoryStockInValidationError(str(exc)) from exc
    except Exception:
        db_session.rollback()
        raise


def submit_v2_inventory_correction(
    db_session: Session,
    *,
    tenant_id: str,
    shop_id: str,
    inventory_item_id: str,
    expected_quantity: Decimal,
    corrected_quantity: Decimal,
    reason: str,
    created_by_account_id: str,
) -> V2InventoryCorrectionResult:
    normalized_reason = reason.strip()
    if not normalized_reason:
        raise V2InventoryCorrectionValidationError("reason is required")
    normalized_corrected_quantity = Decimal(corrected_quantity)
    if normalized_corrected_quantity < 0:
        raise V2InventoryCorrectionValidationError("corrected_quantity must be >= 0")
    normalized_expected_quantity = Decimal(expected_quantity)

    snapshot = _require_v2_inventory_snapshot(
        db_session,
        tenant_id=tenant_id,
        shop_id=shop_id,
        inventory_item_id=inventory_item_id,
    )
    if Decimal(snapshot.current_quantity) != normalized_expected_quantity:
        raise V2InventoryCorrectionConflictError("inventory changed since the snapshot was read")

    item = db_session.scalar(
        select(V2InventoryItem).where(
            V2InventoryItem.inventory_item_id == inventory_item_id,
            V2InventoryItem.tenant_id == tenant_id,
        )
    )
    if item is None:
        raise V2InventoryCorrectionItemNotFoundError(inventory_item_id)

    now = utc_now_naive()
    quantity_delta = normalized_corrected_quantity - Decimal(snapshot.current_quantity)
    snapshot.current_quantity = normalized_corrected_quantity
    snapshot.updated_at = now
    item.updated_at = now
    event = V2InventoryLedgerEvent(
        event_id=f"vevent_{uuid.uuid4().hex}"[:40],
        tenant_id=tenant_id,
        shop_id=shop_id,
        inventory_item_id=inventory_item_id,
        event_type="correction",
        quantity_delta=quantity_delta,
        quantity_after=normalized_corrected_quantity,
        unit=item.default_unit,
        price=snapshot.current_price,
        source_type="inventory_correction",
        source_id=inventory_item_id,
        reason=normalized_reason,
        created_by_account_id=created_by_account_id,
        occurred_at=now,
    )
    db_session.add(event)
    db_session.commit()
    return V2InventoryCorrectionResult(snapshot=snapshot, event=event)


def commit_v2_inventory_stock_out(
    db_session: Session,
    *,
    tenant_id: str,
    shop_id: str,
    inventory_item_id: str,
    expected_quantity: Decimal,
    stock_out_quantity: Decimal,
    reason: str,
    created_by_account_id: str,
) -> V2InventoryStockOutResult:
    approved_payload = _parse_v2_stock_out_payload(
        {
            "inventory_item_id": inventory_item_id,
            "expected_quantity": expected_quantity,
            "stock_out_quantity": stock_out_quantity,
            "reason": reason,
        }
    )

    try:
        snapshot = _require_v2_inventory_snapshot(
            db_session,
            tenant_id=tenant_id,
            shop_id=shop_id,
            inventory_item_id=approved_payload.inventory_item_id,
        )
    except V2InventoryCorrectionItemNotFoundError as exc:
        raise V2InventoryStockOutItemNotFoundError(approved_payload.inventory_item_id) from exc

    item = db_session.scalar(
        select(V2InventoryItem).where(
            V2InventoryItem.inventory_item_id == approved_payload.inventory_item_id,
            V2InventoryItem.tenant_id == tenant_id,
        )
    )
    if item is None:
        raise V2InventoryStockOutItemNotFoundError(approved_payload.inventory_item_id)

    current_quantity = Decimal(snapshot.current_quantity)
    if current_quantity != approved_payload.expected_quantity:
        raise V2InventoryStockOutConflictError("inventory changed since the snapshot was read")
    if approved_payload.stock_out_quantity > current_quantity:
        raise V2InventoryStockOutValidationError("stock_out_quantity exceeds the current stock")

    now = utc_now_naive()
    quantity_after = approved_payload.expected_quantity - approved_payload.stock_out_quantity
    snapshot.current_quantity = quantity_after
    snapshot.updated_at = now
    item.updated_at = now
    event = V2InventoryLedgerEvent(
        event_id=f"vevent_{uuid.uuid4().hex}"[:40],
        tenant_id=tenant_id,
        shop_id=shop_id,
        inventory_item_id=approved_payload.inventory_item_id,
        event_type="stock_out",
        quantity_delta=-approved_payload.stock_out_quantity,
        quantity_after=quantity_after,
        unit=item.default_unit,
        price=snapshot.current_price,
        source_type="inventory_stock_out",
        source_id=approved_payload.inventory_item_id,
        reason=approved_payload.reason,
        created_by_account_id=created_by_account_id,
        occurred_at=now,
    )
    db_session.add(event)
    db_session.flush()
    return V2InventoryStockOutResult(item=item, snapshot=snapshot, event=event)


def submit_v2_inventory_stock_out(
    db_session: Session,
    *,
    tenant_id: str,
    shop_id: str,
    inventory_item_id: str,
    expected_quantity: Decimal,
    stock_out_quantity: Decimal,
    reason: str,
    created_by_account_id: str,
) -> V2InventoryStockOutResult:
    try:
        result = commit_v2_inventory_stock_out(
            db_session,
            tenant_id=tenant_id,
            shop_id=shop_id,
            inventory_item_id=inventory_item_id,
            expected_quantity=expected_quantity,
            stock_out_quantity=stock_out_quantity,
            reason=reason,
            created_by_account_id=created_by_account_id,
        )
        db_session.commit()
        return result
    except Exception:
        db_session.rollback()
        raise
