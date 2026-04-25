"""V2 Stock Check (Inventory Audit) services."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.v2_inventory import V2InventoryItem, V2InventoryStockSnapshot, V2StockCheckRecord
from app.services.v2_inventory import (
    V2InventoryCorrectionConflictError,
    V2InventoryCorrectionItemNotFoundError,
    submit_v2_inventory_correction,
)
from app.services.v2_time import utc_now_naive


class V2StockCheckNotFoundError(LookupError):
    pass


class V2StockCheckAlreadyResolvedError(ValueError):
    pass


class V2StockCheckValidationError(ValueError):
    pass


@dataclass(frozen=True)
class V2StockCheckResult:
    check_record: V2StockCheckRecord
    correction_event_id: str | None = None
    new_quantity: Decimal | None = None


def create_v2_stock_check(
    db_session: Session,
    *,
    tenant_id: str,
    shop_id: str,
    inventory_item_id: str,
    actual_quantity: Decimal,
    check_method: str = "manual",
    notes: str | None = None,
    created_by_account_id: str,
) -> V2StockCheckResult:
    """Create a stock check record comparing system vs actual inventory.

    Args:
        db_session: Database session
        tenant_id: Tenant ID
        shop_id: Shop ID
        inventory_item_id: Item to check
        actual_quantity: Physical count
        check_method: How the check was performed (manual, scan, voice, photo)
        notes: Optional notes
        created_by_account_id: Who performed the check

    Returns:
        V2StockCheckResult with the created record
    """
    # Get current system quantity
    snapshot = db_session.scalar(
        select(V2InventoryStockSnapshot).where(
            V2InventoryStockSnapshot.tenant_id == tenant_id,
            V2InventoryStockSnapshot.shop_id == shop_id,
            V2InventoryStockSnapshot.inventory_item_id == inventory_item_id,
        )
    )
    if snapshot is None:
        raise V2InventoryCorrectionItemNotFoundError(inventory_item_id)

    item = db_session.scalar(
        select(V2InventoryItem).where(
            V2InventoryItem.inventory_item_id == inventory_item_id,
            V2InventoryItem.tenant_id == tenant_id,
        )
    )
    if item is None:
        raise V2InventoryCorrectionItemNotFoundError(inventory_item_id)

    system_quantity = Decimal(snapshot.current_quantity)
    actual = Decimal(actual_quantity)
    difference = actual - system_quantity

    now = utc_now_naive()
    check_record = V2StockCheckRecord(
        check_id=f"vcheck_{uuid.uuid4().hex}"[:40],
        tenant_id=tenant_id,
        shop_id=shop_id,
        inventory_item_id=inventory_item_id,
        system_quantity=system_quantity,
        actual_quantity=actual,
        difference=difference,
        unit=item.default_unit,
        check_method=check_method,
        status="pending",
        notes=notes,
        created_by_account_id=created_by_account_id,
        created_at=now,
        resolved_at=None,
    )
    db_session.add(check_record)
    db_session.commit()

    return V2StockCheckResult(check_record=check_record)


def resolve_v2_stock_check(
    db_session: Session,
    *,
    tenant_id: str,
    shop_id: str,
    check_id: str,
    resolution: str,  # "correct" | "ignore" | "recheck"
    created_by_account_id: str,
) -> V2StockCheckResult:
    """Resolve a stock check by applying correction or marking as handled.

    Args:
        db_session: Database session
        tenant_id: Tenant ID
        shop_id: Shop ID
        check_id: Check record ID
        resolution: How to resolve (correct=apply correction, ignore=mark resolved, recheck=mark for recheck)
        created_by_account_id: Who is resolving

    Returns:
        V2StockCheckResult with updated record
    """
    check_record = db_session.scalar(
        select(V2StockCheckRecord).where(
            V2StockCheckRecord.check_id == check_id,
            V2StockCheckRecord.tenant_id == tenant_id,
            V2StockCheckRecord.shop_id == shop_id,
        )
    )
    if check_record is None:
        raise V2StockCheckNotFoundError(check_id)

    if check_record.status != "pending":
        raise V2StockCheckAlreadyResolvedError(
            f"Stock check {check_id} is already {check_record.status}"
        )

    now = utc_now_naive()
    correction_event_id = None
    new_quantity = None

    if resolution == "correct":
        # Apply inventory correction
        result = submit_v2_inventory_correction(
            db_session,
            tenant_id=tenant_id,
            shop_id=shop_id,
            inventory_item_id=check_record.inventory_item_id,
            expected_quantity=check_record.system_quantity,
            corrected_quantity=check_record.actual_quantity,
            reason=f"Stock check correction (check_id={check_id})",
            created_by_account_id=created_by_account_id,
        )
        correction_event_id = result.event.event_id
        new_quantity = result.snapshot.current_quantity
        check_record.status = "corrected"
    elif resolution == "ignore":
        check_record.status = "ignored"
    elif resolution == "recheck":
        check_record.status = "recheck"
    else:
        raise V2StockCheckValidationError(f"Invalid resolution: {resolution}")

    check_record.resolved_at = now
    db_session.commit()

    return V2StockCheckResult(
        check_record=check_record,
        correction_event_id=correction_event_id,
        new_quantity=new_quantity,
    )


def list_v2_stock_checks(
    db_session: Session,
    *,
    tenant_id: str,
    shop_id: str,
    status: str | None = None,
    limit: int = 20,
) -> list[tuple[V2StockCheckRecord, V2InventoryItem]]:
    """List stock check records with item details."""
    safe_limit = max(1, min(limit, 50))
    statement = (
        select(V2StockCheckRecord, V2InventoryItem)
        .join(
            V2InventoryItem,
            V2InventoryItem.inventory_item_id == V2StockCheckRecord.inventory_item_id,
        )
        .where(
            V2StockCheckRecord.tenant_id == tenant_id,
            V2StockCheckRecord.shop_id == shop_id,
        )
        .order_by(V2StockCheckRecord.created_at.desc())
        .limit(safe_limit)
    )

    if status:
        statement = statement.where(V2StockCheckRecord.status == status)

    return list(db_session.execute(statement).all())


def get_v2_stock_check_summary(
    db_session: Session,
    *,
    tenant_id: str,
    shop_id: str,
) -> dict:
    """Get summary of stock check status for a shop."""
    from sqlalchemy import func

    total = db_session.scalar(
        select(func.count(V2StockCheckRecord.check_id))
        .where(
            V2StockCheckRecord.tenant_id == tenant_id,
            V2StockCheckRecord.shop_id == shop_id,
        )
    ) or 0

    pending = db_session.scalar(
        select(func.count(V2StockCheckRecord.check_id))
        .where(
            V2StockCheckRecord.tenant_id == tenant_id,
            V2StockCheckRecord.shop_id == shop_id,
            V2StockCheckRecord.status == "pending",
        )
    ) or 0

    corrected = db_session.scalar(
        select(func.count(V2StockCheckRecord.check_id))
        .where(
            V2StockCheckRecord.tenant_id == tenant_id,
            V2StockCheckRecord.shop_id == shop_id,
            V2StockCheckRecord.status == "corrected",
        )
    ) or 0

    return {
        "total": total,
        "pending": pending,
        "corrected": corrected,
        "ignored": total - pending - corrected,
    }
