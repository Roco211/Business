from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
import re
import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import V2Confirmation, V2ConversationSession, V2InventoryItem, V2InventoryLedgerEvent, V2InventoryStockSnapshot, V2Message, V2TaskRun
from app.services.v2_audit import append_v2_audit_log
from app.models.v2_commercial import V2Customer, V2FinanceTransaction, V2PurchaseOrder, V2PurchaseOrderLine, V2SalesReturn, V2Supplier
from app.models.v2_sales import V2SalesOrder, V2SalesOrderLine
from app.services.v2_time import utc_now_naive


def money(value) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def add_finance_transaction(db: Session, *, tenant_id: str, shop_id: str, transaction_type: str, direction: str, amount, source_type: str, source_id: str, counterparty_name: str | None, note: str | None, created_by_account_id: str):
    tx = V2FinanceTransaction(
        finance_transaction_id=f"vfin_{uuid.uuid4().hex}"[:40], tenant_id=tenant_id, shop_id=shop_id,
        transaction_type=transaction_type, direction=direction, amount=money(amount), source_type=source_type, source_id=source_id,
        counterparty_name=counterparty_name, note=note, created_by_account_id=created_by_account_id, occurred_at=utc_now_naive()
    )
    db.add(tx)
    return tx


def get_finance_transactions(db: Session, *, tenant_id: str, shop_id: str, limit: int, transaction_type: str | None = None, direction: str | None = None):
    statement = select(V2FinanceTransaction).where(V2FinanceTransaction.tenant_id == tenant_id, V2FinanceTransaction.shop_id == shop_id)
    if transaction_type:
        statement = statement.where(V2FinanceTransaction.transaction_type == transaction_type)
    if direction:
        statement = statement.where(V2FinanceTransaction.direction == direction)
    return list(db.scalars(statement.order_by(V2FinanceTransaction.occurred_at.desc(), V2FinanceTransaction.finance_transaction_id.desc()).limit(limit)))


def finance_summary(db: Session, *, tenant_id: str, shop_id: str) -> dict:
    rows = db.execute(select(V2FinanceTransaction.direction, func.coalesce(func.sum(V2FinanceTransaction.amount), 0)).where(V2FinanceTransaction.tenant_id == tenant_id, V2FinanceTransaction.shop_id == shop_id).group_by(V2FinanceTransaction.direction)).all()
    income = Decimal("0.00"); expense = Decimal("0.00")
    for direction, amount in rows:
        if direction == "income": income += Decimal(amount)
        if direction == "expense": expense += Decimal(amount)
    return {"total_income": money(income), "total_expense": money(expense), "net_cashflow": money(income - expense)}


def get_sales_order_detail(db: Session, *, tenant_id: str, shop_id: str, sales_order_id: str):
    order = db.scalar(select(V2SalesOrder).where(V2SalesOrder.sales_order_id == sales_order_id, V2SalesOrder.tenant_id == tenant_id, V2SalesOrder.shop_id == shop_id))
    if order is None:
        raise LookupError(sales_order_id)
    lines = list(db.scalars(select(V2SalesOrderLine).where(V2SalesOrderLine.sales_order_id == sales_order_id, V2SalesOrderLine.tenant_id == tenant_id, V2SalesOrderLine.shop_id == shop_id).order_by(V2SalesOrderLine.created_at.asc())))
    return order, lines


def cancel_sales_order(db: Session, *, tenant_id: str, shop_id: str, sales_order_id: str, reason: str, account_id: str):
    try:
        order, lines = get_sales_order_detail(db, tenant_id=tenant_id, shop_id=shop_id, sales_order_id=sales_order_id)
        if order.status == "cancelled":
            return order, lines
        if order.status not in {"paid", "partially_refunded"}:
            raise ValueError("sales order cannot be cancelled")
        now = utc_now_naive()
        for line in lines:
            snap = db.scalar(select(V2InventoryStockSnapshot).where(V2InventoryStockSnapshot.tenant_id == tenant_id, V2InventoryStockSnapshot.shop_id == shop_id, V2InventoryStockSnapshot.inventory_item_id == line.inventory_item_id))
            if snap is not None:
                snap.current_quantity = Decimal(snap.current_quantity) + Decimal(line.quantity)
                snap.updated_at = now
                db.add(V2InventoryLedgerEvent(event_id=f"vevent_{uuid.uuid4().hex}"[:40], tenant_id=tenant_id, shop_id=shop_id, inventory_item_id=line.inventory_item_id, event_type="stock_in", quantity_delta=line.quantity, quantity_after=snap.current_quantity, unit=line.unit, price=line.unit_price, source_type="sales_order_cancel", source_id=sales_order_id, reason="sales order cancelled", created_by_account_id=account_id, occurred_at=now))
        order.status = "cancelled"; order.updated_at = now
        add_finance_transaction(db, tenant_id=tenant_id, shop_id=shop_id, transaction_type="sales_refund", direction="expense", amount=order.total_amount, source_type="sales_order_cancel", source_id=sales_order_id, counterparty_name=order.customer_name, note=reason, created_by_account_id=account_id)
        append_v2_audit_log(db, tenant_id=tenant_id, shop_id=shop_id, action="sales_order.cancel", actor_id=account_id, target_type="sales_order", target_id=sales_order_id, metadata={"reason": reason, "amount": str(order.total_amount)})
        db.commit(); return order, lines
    except Exception:
        db.rollback(); raise


def return_sales_order_items(db: Session, *, tenant_id: str, shop_id: str, sales_order_id: str, items: list[dict], reason: str, account_id: str):
    try:
        order, lines = get_sales_order_detail(db, tenant_id=tenant_id, shop_id=shop_id, sales_order_id=sales_order_id)
        line_by_id = {line.sales_order_line_id: line for line in lines}
        now = utc_now_naive(); refund_total = Decimal("0.00")
        for raw in items:
            line_id = str(raw.get("sales_order_line_id") or "")
            quantity = Decimal(str(raw.get("quantity") or "0"))
            if line_id not in line_by_id or quantity <= 0:
                raise ValueError("invalid return line")
            line = line_by_id[line_id]
            if quantity > Decimal(line.quantity):
                raise ValueError("return quantity exceeds sold quantity")
            refund = money(quantity * Decimal(line.unit_price)); refund_total += refund
            snap = db.scalar(select(V2InventoryStockSnapshot).where(V2InventoryStockSnapshot.tenant_id == tenant_id, V2InventoryStockSnapshot.shop_id == shop_id, V2InventoryStockSnapshot.inventory_item_id == line.inventory_item_id))
            if snap is not None:
                snap.current_quantity = Decimal(snap.current_quantity) + quantity; snap.updated_at = now
                db.add(V2InventoryLedgerEvent(event_id=f"vevent_{uuid.uuid4().hex}"[:40], tenant_id=tenant_id, shop_id=shop_id, inventory_item_id=line.inventory_item_id, event_type="stock_in", quantity_delta=quantity, quantity_after=snap.current_quantity, unit=line.unit, price=line.unit_price, source_type="sales_return", source_id=sales_order_id, reason="sales order returned", created_by_account_id=account_id, occurred_at=now))
            db.add(V2SalesReturn(sales_return_id=f"vret_{uuid.uuid4().hex}"[:40], tenant_id=tenant_id, shop_id=shop_id, sales_order_id=sales_order_id, sales_order_line_id=line_id, inventory_item_id=line.inventory_item_id, quantity=quantity, refund_amount=refund, reason=reason, created_by_account_id=account_id, created_at=now))
        order.status = "refunded" if refund_total >= Decimal(order.total_amount) else "partially_refunded"; order.updated_at = now
        add_finance_transaction(db, tenant_id=tenant_id, shop_id=shop_id, transaction_type="sales_refund", direction="expense", amount=refund_total, source_type="sales_return", source_id=sales_order_id, counterparty_name=order.customer_name, note=reason, created_by_account_id=account_id)
        append_v2_audit_log(db, tenant_id=tenant_id, shop_id=shop_id, action="sales_order.return", actor_id=account_id, target_type="sales_order", target_id=sales_order_id, metadata={"reason": reason, "refund_total": str(refund_total), "items_count": len(items)})
        db.commit(); return order, lines
    except Exception:
        db.rollback(); raise


def list_suppliers(db: Session, *, tenant_id: str, shop_id: str, limit: int):
    return list(db.scalars(select(V2Supplier).where(V2Supplier.tenant_id == tenant_id, V2Supplier.shop_id == shop_id, V2Supplier.status == "active").order_by(V2Supplier.created_at.desc(), V2Supplier.supplier_id.desc()).limit(limit)))


def create_supplier(db: Session, *, tenant_id: str, shop_id: str, name: str, phone: str | None, account_id: str | None = None):
    now = utc_now_naive(); supplier = V2Supplier(supplier_id=f"vsup_{uuid.uuid4().hex}"[:40], tenant_id=tenant_id, shop_id=shop_id, name=name.strip(), phone=(phone or None), status="active", created_at=now, updated_at=now)
    db.add(supplier)
    if account_id:
        append_v2_audit_log(db, tenant_id=tenant_id, shop_id=shop_id, action="supplier.create", actor_id=account_id, target_type="supplier", target_id=supplier.supplier_id, metadata={"name": supplier.name})
    db.commit(); return supplier


def list_purchase_orders(db: Session, *, tenant_id: str, shop_id: str, limit: int):
    return list(db.scalars(select(V2PurchaseOrder).where(V2PurchaseOrder.tenant_id == tenant_id, V2PurchaseOrder.shop_id == shop_id).order_by(V2PurchaseOrder.created_at.desc(), V2PurchaseOrder.purchase_order_id.desc()).limit(limit)))


def create_purchase_order(db: Session, *, tenant_id: str, shop_id: str, supplier_id: str, items: list[dict], note: str | None, account_id: str):
    try:
        supplier = db.scalar(select(V2Supplier).where(V2Supplier.supplier_id == supplier_id, V2Supplier.tenant_id == tenant_id, V2Supplier.shop_id == shop_id, V2Supplier.status == "active"))
        if supplier is None: raise LookupError(supplier_id)
        now = utc_now_naive(); po = V2PurchaseOrder(purchase_order_id=f"vpo_{uuid.uuid4().hex}"[:40], tenant_id=tenant_id, shop_id=shop_id, supplier_id=supplier_id, order_no=f"PO{now.strftime('%Y%m%d%H%M%S')}{uuid.uuid4().hex[:6].upper()}", status="received", total_amount=Decimal("0.00"), note=note, created_by_account_id=account_id, created_at=now, updated_at=now)
        db.add(po); db.flush(); total = Decimal("0.00")
        for raw in items:
            item_id = str(raw.get("inventory_item_id") or ""); qty = Decimal(str(raw.get("quantity") or "0")); cost = money(raw.get("unit_cost") or 0)
            item = db.scalar(select(V2InventoryItem).where(V2InventoryItem.inventory_item_id == item_id, V2InventoryItem.tenant_id == tenant_id, V2InventoryItem.status == "active"))
            if item is None or qty <= 0: raise LookupError(item_id)
            snap = db.scalar(select(V2InventoryStockSnapshot).where(V2InventoryStockSnapshot.tenant_id == tenant_id, V2InventoryStockSnapshot.shop_id == shop_id, V2InventoryStockSnapshot.inventory_item_id == item_id))
            if snap is None:
                snap = V2InventoryStockSnapshot(snapshot_id=f"vsnap_{uuid.uuid4().hex}"[:40], tenant_id=tenant_id, shop_id=shop_id, inventory_item_id=item_id, current_quantity=Decimal("0"), current_price=cost, low_stock_threshold=Decimal("0"), updated_at=now); db.add(snap); db.flush()
            amount = money(qty * cost); total += amount; snap.current_quantity = Decimal(snap.current_quantity) + qty; snap.current_price = cost; snap.updated_at = now
            db.add(V2PurchaseOrderLine(purchase_order_line_id=f"vpol_{uuid.uuid4().hex}"[:40], purchase_order_id=po.purchase_order_id, tenant_id=tenant_id, shop_id=shop_id, inventory_item_id=item_id, item_name=item.name, quantity=qty, unit=item.default_unit, unit_cost=cost, line_amount=amount, created_at=now))
            db.add(V2InventoryLedgerEvent(event_id=f"vevent_{uuid.uuid4().hex}"[:40], tenant_id=tenant_id, shop_id=shop_id, inventory_item_id=item_id, event_type="stock_in", quantity_delta=qty, quantity_after=snap.current_quantity, unit=item.default_unit, price=cost, source_type="purchase_order", source_id=po.purchase_order_id, reason="purchase order received", created_by_account_id=account_id, occurred_at=now))
        po.total_amount = money(total)
        add_finance_transaction(db, tenant_id=tenant_id, shop_id=shop_id, transaction_type="purchase_payment", direction="expense", amount=po.total_amount, source_type="purchase_order", source_id=po.purchase_order_id, counterparty_name=supplier.name, note=note, created_by_account_id=account_id)
        append_v2_audit_log(db, tenant_id=tenant_id, shop_id=shop_id, action="purchase_order.create", actor_id=account_id, target_type="purchase_order", target_id=po.purchase_order_id, metadata={"supplier_id": supplier_id, "amount": str(po.total_amount), "items_count": len(items)})
        db.commit(); return po
    except Exception:
        db.rollback(); raise


def list_customers(db: Session, *, tenant_id: str, shop_id: str, limit: int):
    return list(db.scalars(select(V2Customer).where(V2Customer.tenant_id == tenant_id, V2Customer.shop_id == shop_id, V2Customer.status == "active").order_by(V2Customer.created_at.desc(), V2Customer.customer_id.desc()).limit(limit)))


def create_customer(db: Session, *, tenant_id: str, shop_id: str, name: str, phone: str | None, account_id: str | None = None):
    now = utc_now_naive(); customer = V2Customer(customer_id=f"vcus_{uuid.uuid4().hex}"[:40], tenant_id=tenant_id, shop_id=shop_id, name=name.strip(), phone=(phone or None), status="active", created_at=now, updated_at=now)
    db.add(customer)
    if account_id:
        append_v2_audit_log(db, tenant_id=tenant_id, shop_id=shop_id, action="customer.create", actor_id=account_id, target_type="customer", target_id=customer.customer_id, metadata={"name": customer.name})
    db.commit(); return customer


def customer_repurchase_analysis(db: Session, *, tenant_id: str, shop_id: str):
    customers = list(db.scalars(select(V2Customer).where(V2Customer.tenant_id == tenant_id, V2Customer.shop_id == shop_id, V2Customer.status == "active")))
    orders = list(db.scalars(select(V2SalesOrder).where(V2SalesOrder.tenant_id == tenant_id, V2SalesOrder.shop_id == shop_id)))
    by_id = {c.customer_id: {"customer_id": c.customer_id, "name": c.name, "phone": c.phone, "order_count": 0, "total_amount": Decimal("0.00")} for c in customers}
    by_name = {c.name: c.customer_id for c in customers}
    for order in orders:
        matched_customer_id = getattr(order, "customer_id", None) or by_name.get(order.customer_name or "")
        if matched_customer_id in by_id:
            by_id[matched_customer_id]["order_count"] += 1
            by_id[matched_customer_id]["total_amount"] += Decimal(order.total_amount)
    return {"summary": {"customer_count": len(customers), "matched_order_count": sum(v["order_count"] for v in by_id.values())}, "customers": list(by_id.values())}


def create_sales_order_confirmation_from_text(db: Session, *, tenant_id: str, shop_id: str, account_id: str, message: str):
    # MVP deterministic parser: match quantity + active item name substring + optional unit price/customer.
    item = None
    for candidate in db.scalars(select(V2InventoryItem).where(V2InventoryItem.tenant_id == tenant_id, V2InventoryItem.status == "active")):
        if candidate.name in message:
            item = candidate; break
    if item is None: raise LookupError("item")
    qty_match = re.search(r"(\d+(?:\.\d+)?)", message); price_match = re.search(r"单价\s*(\d+(?:\.\d+)?)", message)
    qty = Decimal(qty_match.group(1)) if qty_match else Decimal("1")
    price = money(price_match.group(1) if price_match else "0")
    customer = "散客"
    if "客户" in message:
        customer = message.split("客户", 1)[1].strip()[:40] or "散客"
    now = utc_now_naive()
    session = V2ConversationSession(session_id=f"vsess_{uuid.uuid4().hex}"[:40], tenant_id=tenant_id, shop_id=shop_id, session_type="sales_order_draft", title="AI销售单草稿", status="active", initiated_by_account_id=account_id, created_at=now, updated_at=now)
    db.add(session); db.flush()
    msg = V2Message(message_id=f"vmsg_{uuid.uuid4().hex}"[:40], tenant_id=tenant_id, shop_id=shop_id, session_id=session.session_id, actor_type="account", actor_id=account_id, message_kind="text", payload_json={"text": message}, created_at=now)
    task = V2TaskRun(task_run_id=f"vtask_{uuid.uuid4().hex}"[:40], tenant_id=tenant_id, shop_id=shop_id, session_id=session.session_id, source_message_id=msg.message_id, intent_type="sales.order_create", status="awaiting_confirmation", risk_level="medium", trace_id=f"trace_{uuid.uuid4().hex}"[:64], result_summary="AI sales order draft awaiting confirmation.", created_at=now, updated_at=now)
    draft = {"customer_name": customer, "payment_method": "unknown", "items": [{"inventory_item_id": item.inventory_item_id, "item_name": item.name, "quantity": str(qty), "unit_price": str(price), "line_amount": str(money(qty * price))}], "note": "AI sales order draft"}
    confirmation = V2Confirmation(confirmation_id=f"vconf_{uuid.uuid4().hex}"[:40], tenant_id=tenant_id, shop_id=shop_id, task_run_id=task.task_run_id, confirmation_type="sales.order_create", status="pending", draft_payload=draft, resolution_payload={}, created_at=now)
    db.add_all([msg, task, confirmation]); db.commit(); return confirmation


def create_purchase_order_confirmation_from_text(db: Session, *, tenant_id: str, shop_id: str, account_id: str, message: str):
    item = None
    for candidate in db.scalars(select(V2InventoryItem).where(V2InventoryItem.tenant_id == tenant_id, V2InventoryItem.status == "active")):
        if candidate.name in message:
            item = candidate
            break
    if item is None:
        raise LookupError("item")

    supplier = None
    supplier_source = "matched_by_name"
    active_suppliers = list(db.scalars(select(V2Supplier).where(V2Supplier.tenant_id == tenant_id, V2Supplier.shop_id == shop_id, V2Supplier.status == "active").order_by(V2Supplier.created_at.asc(), V2Supplier.supplier_id.asc())))
    for candidate in active_suppliers:
        if candidate.name in message:
            supplier = candidate
            break
    if supplier is None and active_suppliers:
        supplier = active_suppliers[0]
        supplier_source = "fallback_first_supplier"
    if supplier is None:
        supplier_name = "默认五金供应商"
        if "供应商" in message:
            supplier_name = message.split("供应商", 1)[0].replace("向", "").strip() or supplier_name
        supplier_id = "__new_supplier__"
        supplier_source = "pending_create_on_approval"
    else:
        supplier_id = supplier.supplier_id
        supplier_name = supplier.name

    qty_match = re.search(r"(\d+(?:\.\d+)?)", message)
    price_match = re.search(r"(?:单价|进价|成本)\s*(\d+(?:\.\d+)?)", message)
    qty = Decimal(qty_match.group(1)) if qty_match else Decimal("1")
    unit_cost = money(price_match.group(1) if price_match else "0")
    now = utc_now_naive()
    session = V2ConversationSession(session_id=f"vsess_{uuid.uuid4().hex}"[:40], tenant_id=tenant_id, shop_id=shop_id, session_type="purchase_order_draft", title="AI采购单草稿", status="active", initiated_by_account_id=account_id, created_at=now, updated_at=now)
    db.add(session); db.flush()
    msg = V2Message(message_id=f"vmsg_{uuid.uuid4().hex}"[:40], tenant_id=tenant_id, shop_id=shop_id, session_id=session.session_id, actor_type="account", actor_id=account_id, message_kind="text", payload_json={"text": message}, created_at=now)
    task = V2TaskRun(task_run_id=f"vtask_{uuid.uuid4().hex}"[:40], tenant_id=tenant_id, shop_id=shop_id, session_id=session.session_id, source_message_id=msg.message_id, intent_type="purchase.order_create", status="awaiting_confirmation", risk_level="high", trace_id=f"trace_{uuid.uuid4().hex}"[:64], result_summary="AI purchase order draft awaiting confirmation.", created_at=now, updated_at=now)
    draft = {
        "supplier_id": supplier_id,
        "supplier_name": supplier_name,
        "supplier_source": supplier_source,
        "items": [{"inventory_item_id": item.inventory_item_id, "item_name": item.name, "quantity": str(qty), "unit_cost": str(unit_cost), "line_amount": str(money(qty * unit_cost))}],
        "note": "AI purchase order draft",
        "source_text": message,
    }
    confirmation = V2Confirmation(confirmation_id=f"vconf_{uuid.uuid4().hex}"[:40], tenant_id=tenant_id, shop_id=shop_id, task_run_id=task.task_run_id, confirmation_type="purchase.order_create", status="pending", draft_payload=draft, resolution_payload={}, created_at=now)
    db.add_all([msg, task, confirmation])
    db.commit()
    return confirmation
