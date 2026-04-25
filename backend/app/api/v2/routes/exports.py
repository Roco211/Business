from __future__ import annotations

import csv
import io

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps.v2_context import V2AuthenticatedAccount, V2ExecutionContext, require_v2_authenticated_account, require_v2_execution_context
from app.contracts.v2.common import V2ErrorBody, V2ErrorEnvelope
from app.db.session import get_db_session
from app.models import V2InventoryLedgerEvent
from app.models.v2_commercial import V2FinanceTransaction, V2PurchaseOrder
from app.models.v2_sales import V2SalesOrder

router = APIRouter(prefix="/api/v2/exports", tags=["v2-exports"])


def _guard(account: V2AuthenticatedAccount, context: V2ExecutionContext):
    if account.account_id != context.account_id:
        return JSONResponse(status_code=403, content=V2ErrorEnvelope(error=V2ErrorBody(code="context_account_mismatch", message="Context account mismatch")).model_dump())
    return None


def _csv_response(filename: str, headers: list[str], rows: list[list[object]]) -> Response:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(headers)
    writer.writerows(rows)
    return Response(
        content=buffer.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/sales-orders")
def export_sales_orders_v2(
    account: V2AuthenticatedAccount = Depends(require_v2_authenticated_account),
    context: V2ExecutionContext = Depends(require_v2_execution_context),
    limit: int = Query(default=500, ge=1, le=2000),
    db_session: Session = Depends(get_db_session),
):
    if mismatch := _guard(account, context):
        return mismatch
    orders = list(db_session.scalars(select(V2SalesOrder).where(V2SalesOrder.tenant_id == context.tenant_id, V2SalesOrder.shop_id == context.shop_id).order_by(V2SalesOrder.created_at.desc(), V2SalesOrder.sales_order_id.desc()).limit(limit)))
    return _csv_response(
        "sales-orders.csv",
        ["order_no", "customer_name", "total_amount", "status", "sales_order_id", "customer_id", "payment_method", "created_at"],
        [[order.order_no, order.customer_name or "", order.total_amount, order.status, order.sales_order_id, order.customer_id or "", order.payment_method, order.created_at.isoformat() if order.created_at else ""] for order in orders],
    )


@router.get("/purchase-orders")
def export_purchase_orders_v2(
    account: V2AuthenticatedAccount = Depends(require_v2_authenticated_account),
    context: V2ExecutionContext = Depends(require_v2_execution_context),
    limit: int = Query(default=500, ge=1, le=2000),
    db_session: Session = Depends(get_db_session),
):
    if mismatch := _guard(account, context):
        return mismatch
    orders = list(db_session.scalars(select(V2PurchaseOrder).where(V2PurchaseOrder.tenant_id == context.tenant_id, V2PurchaseOrder.shop_id == context.shop_id).order_by(V2PurchaseOrder.created_at.desc(), V2PurchaseOrder.purchase_order_id.desc()).limit(limit)))
    return _csv_response(
        "purchase-orders.csv",
        ["order_no", "supplier_id", "total_amount", "status", "purchase_order_id", "note", "created_at"],
        [[order.order_no, order.supplier_id, order.total_amount, order.status, order.purchase_order_id, order.note or "", order.created_at.isoformat() if order.created_at else ""] for order in orders],
    )


@router.get("/finance-transactions")
def export_finance_transactions_v2(
    account: V2AuthenticatedAccount = Depends(require_v2_authenticated_account),
    context: V2ExecutionContext = Depends(require_v2_execution_context),
    limit: int = Query(default=500, ge=1, le=2000),
    db_session: Session = Depends(get_db_session),
):
    if mismatch := _guard(account, context):
        return mismatch
    transactions = list(db_session.scalars(select(V2FinanceTransaction).where(V2FinanceTransaction.tenant_id == context.tenant_id, V2FinanceTransaction.shop_id == context.shop_id).order_by(V2FinanceTransaction.occurred_at.desc(), V2FinanceTransaction.finance_transaction_id.desc()).limit(limit)))
    return _csv_response(
        "finance-transactions.csv",
        ["transaction_type", "direction", "amount", "source_type", "source_id", "counterparty_name", "note", "occurred_at"],
        [[tx.transaction_type, tx.direction, tx.amount, tx.source_type, tx.source_id, tx.counterparty_name or "", tx.note or "", tx.occurred_at.isoformat() if tx.occurred_at else ""] for tx in transactions],
    )


@router.get("/inventory-ledger")
def export_inventory_ledger_v2(
    account: V2AuthenticatedAccount = Depends(require_v2_authenticated_account),
    context: V2ExecutionContext = Depends(require_v2_execution_context),
    limit: int = Query(default=500, ge=1, le=2000),
    db_session: Session = Depends(get_db_session),
):
    if mismatch := _guard(account, context):
        return mismatch
    events = list(db_session.scalars(select(V2InventoryLedgerEvent).where(V2InventoryLedgerEvent.tenant_id == context.tenant_id, V2InventoryLedgerEvent.shop_id == context.shop_id).order_by(V2InventoryLedgerEvent.occurred_at.desc(), V2InventoryLedgerEvent.event_id.desc()).limit(limit)))
    return _csv_response(
        "inventory-ledger.csv",
        ["event_type", "inventory_item_id", "quantity_delta", "quantity_after", "unit", "price", "source_type", "source_id", "reason", "occurred_at"],
        [[event.event_type, event.inventory_item_id, event.quantity_delta, event.quantity_after, event.unit, event.price or "", event.source_type, event.source_id, event.reason or "", event.occurred_at.isoformat() if event.occurred_at else ""] for event in events],
    )
