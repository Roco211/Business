from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import V2Customer, V2InventoryItem, V2InventoryLedgerEvent, V2InventoryStockSnapshot
from app.models.v2_sales import V2SalesOrder, V2SalesOrderLine
from app.services.v2_audit import append_v2_audit_log
from app.services.v2_time import utc_now_naive
from app.services.v2_commercial import add_finance_transaction


class V2SalesOrderValidationError(ValueError):
    pass


class V2SalesOrderItemNotFoundError(LookupError):
    pass


class V2SalesOrderInsufficientStockError(RuntimeError):
    pass


@dataclass(frozen=True)
class V2SalesOrderLineInput:
    inventory_item_id: str
    quantity: Decimal
    unit_price: Decimal


@dataclass(frozen=True)
class V2CreatedSalesOrderResult:
    order: V2SalesOrder
    lines: list[V2SalesOrderLine]


def _money(value: Decimal) -> Decimal:
    return Decimal(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _normalize_sales_order_lines(raw_items: list[object]) -> list[V2SalesOrderLineInput]:
    if not raw_items:
        raise V2SalesOrderValidationError("items is required")
    lines: list[V2SalesOrderLineInput] = []
    for raw in raw_items:
        if isinstance(raw, dict):
            inventory_item_id = str(raw.get("inventory_item_id") or "").strip()
            quantity = Decimal(str(raw.get("quantity") or "0"))
            unit_price = Decimal(str(raw.get("unit_price") or "0"))
        else:
            inventory_item_id = str(getattr(raw, "inventory_item_id", None) or "").strip()
            quantity = Decimal(getattr(raw, "quantity", 0))
            unit_price = Decimal(getattr(raw, "unit_price", 0))
        if not inventory_item_id:
            raise V2SalesOrderValidationError("inventory_item_id is required")
        if quantity <= 0:
            raise V2SalesOrderValidationError("quantity must be > 0")
        if unit_price < 0:
            raise V2SalesOrderValidationError("unit_price must be >= 0")
        lines.append(V2SalesOrderLineInput(inventory_item_id=inventory_item_id, quantity=quantity, unit_price=unit_price))
    return lines


def _generate_order_no() -> str:
    now = utc_now_naive()
    return f"SO{now.strftime('%Y%m%d%H%M%S')}{uuid.uuid4().hex[:6].upper()}"


def create_v2_sales_order(
    db_session: Session,
    *,
    tenant_id: str,
    shop_id: str,
    customer_id: str | None,
    customer_name: str | None,
    payment_method: str,
    items: list[object],
    note: str | None,
    created_by_account_id: str,
) -> V2CreatedSalesOrderResult:
    normalized_lines = _normalize_sales_order_lines(items)
    normalized_payment_method = (payment_method or "unknown").strip() or "unknown"
    normalized_customer_id = (customer_id or "").strip() or None
    normalized_customer_name = (customer_name or "").strip() or None
    normalized_note = (note or "").strip() or None
    if normalized_customer_id:
        customer = db_session.scalar(
            select(V2Customer).where(
                V2Customer.customer_id == normalized_customer_id,
                V2Customer.tenant_id == tenant_id,
                V2Customer.shop_id == shop_id,
                V2Customer.status == "active",
            )
        )
        if customer is None:
            raise V2SalesOrderValidationError("customer_id not found")
        normalized_customer_name = normalized_customer_name or customer.name

    try:
        now = utc_now_naive()
        order_id = f"vsorder_{uuid.uuid4().hex}"[:40]
        order = V2SalesOrder(
            sales_order_id=order_id,
            tenant_id=tenant_id,
            shop_id=shop_id,
            order_no=_generate_order_no(),
            status="paid",
            customer_id=normalized_customer_id,
            customer_name=normalized_customer_name,
            payment_method=normalized_payment_method,
            total_amount=Decimal("0.00"),
            note=normalized_note,
            created_by_account_id=created_by_account_id,
            created_at=now,
            updated_at=now,
        )
        db_session.add(order)
        db_session.flush()

        result_lines: list[V2SalesOrderLine] = []
        total_amount = Decimal("0.00")
        requested_by_item: dict[str, Decimal] = {}
        for line in normalized_lines:
            requested_by_item[line.inventory_item_id] = requested_by_item.get(line.inventory_item_id, Decimal("0")) + line.quantity

        items_by_id: dict[str, V2InventoryItem] = {}
        snapshots_by_id: dict[str, V2InventoryStockSnapshot] = {}
        for inventory_item_id, requested_quantity in requested_by_item.items():
            item = db_session.scalar(
                select(V2InventoryItem).where(
                    V2InventoryItem.inventory_item_id == inventory_item_id,
                    V2InventoryItem.tenant_id == tenant_id,
                    V2InventoryItem.status == "active",
                )
            )
            if item is None:
                raise V2SalesOrderItemNotFoundError(inventory_item_id)
            snapshot = db_session.scalar(
                select(V2InventoryStockSnapshot).where(
                    V2InventoryStockSnapshot.tenant_id == tenant_id,
                    V2InventoryStockSnapshot.shop_id == shop_id,
                    V2InventoryStockSnapshot.inventory_item_id == inventory_item_id,
                )
            )
            if snapshot is None:
                raise V2SalesOrderInsufficientStockError(inventory_item_id)
            if Decimal(snapshot.current_quantity) < requested_quantity:
                raise V2SalesOrderInsufficientStockError(inventory_item_id)
            items_by_id[inventory_item_id] = item
            snapshots_by_id[inventory_item_id] = snapshot

        for line_input in normalized_lines:
            item = items_by_id[line_input.inventory_item_id]
            snapshot = snapshots_by_id[line_input.inventory_item_id]
            line_amount = _money(line_input.quantity * line_input.unit_price)
            line = V2SalesOrderLine(
                sales_order_line_id=f"vsoline_{uuid.uuid4().hex}"[:40],
                sales_order_id=order.sales_order_id,
                tenant_id=tenant_id,
                shop_id=shop_id,
                inventory_item_id=item.inventory_item_id,
                item_name=item.name,
                quantity=line_input.quantity,
                unit=item.default_unit,
                unit_price=_money(line_input.unit_price),
                line_amount=line_amount,
                created_at=now,
            )
            total_amount += line_amount
            quantity_after = Decimal(snapshot.current_quantity) - line_input.quantity
            snapshot.current_quantity = quantity_after
            snapshot.updated_at = now
            item.updated_at = now
            event = V2InventoryLedgerEvent(
                event_id=f"vevent_{uuid.uuid4().hex}"[:40],
                tenant_id=tenant_id,
                shop_id=shop_id,
                inventory_item_id=item.inventory_item_id,
                event_type="stock_out",
                quantity_delta=-line_input.quantity,
                quantity_after=quantity_after,
                unit=item.default_unit,
                price=line_input.unit_price,
                source_type="sales_order",
                source_id=order.sales_order_id,
                reason="sales order paid",
                created_by_account_id=created_by_account_id,
                occurred_at=now,
            )
            db_session.add_all([line, event])
            result_lines.append(line)

        order.total_amount = _money(total_amount)
        order.updated_at = now
        add_finance_transaction(
            db_session,
            tenant_id=tenant_id,
            shop_id=shop_id,
            transaction_type="sales_revenue",
            direction="income",
            amount=order.total_amount,
            source_type="sales_order",
            source_id=order.sales_order_id,
            counterparty_name=order.customer_name,
            note=order.note,
            created_by_account_id=created_by_account_id,
        )
        append_v2_audit_log(
            db_session,
            tenant_id=tenant_id,
            shop_id=shop_id,
            action="sales_order.create",
            actor_id=created_by_account_id,
            target_type="sales_order",
            target_id=order.sales_order_id,
            metadata={"order_no": order.order_no, "amount": str(order.total_amount), "items_count": len(result_lines)},
        )
        db_session.commit()
        return V2CreatedSalesOrderResult(order=order, lines=result_lines)
    except Exception:
        db_session.rollback()
        raise


def list_v2_sales_orders(
    db_session: Session,
    *,
    tenant_id: str,
    shop_id: str,
    limit: int,
) -> list[tuple[V2SalesOrder, int]]:
    rows = db_session.execute(
        select(V2SalesOrder, func.count(V2SalesOrderLine.sales_order_line_id))
        .join(V2SalesOrderLine, V2SalesOrderLine.sales_order_id == V2SalesOrder.sales_order_id)
        .where(V2SalesOrder.tenant_id == tenant_id, V2SalesOrder.shop_id == shop_id)
        .group_by(V2SalesOrder.sales_order_id)
        .order_by(V2SalesOrder.created_at.desc(), V2SalesOrder.sales_order_id.desc())
        .limit(limit)
    ).all()
    return [(row[0], int(row[1])) for row in rows]


def list_v2_sales_order_lines(
    db_session: Session,
    *,
    tenant_id: str,
    shop_id: str,
    sales_order_id: str,
) -> list[V2SalesOrderLine]:
    return list(
        db_session.scalars(
            select(V2SalesOrderLine)
            .where(
                V2SalesOrderLine.tenant_id == tenant_id,
                V2SalesOrderLine.shop_id == shop_id,
                V2SalesOrderLine.sales_order_id == sales_order_id,
            )
            .order_by(V2SalesOrderLine.created_at.asc(), V2SalesOrderLine.sales_order_line_id.asc())
        )
    )
