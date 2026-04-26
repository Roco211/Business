from __future__ import annotations

import csv
import io

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps.v2_context import V2AuthenticatedAccount, V2ExecutionContext, ensure_v2_permission, require_v2_authenticated_account, require_v2_execution_context
from app.contracts.v2.common import V2ErrorBody, V2ErrorEnvelope
from app.db.session import get_db_session
from app.models import V2ExportJob, V2InventoryLedgerEvent
from app.models.v2_commercial import V2FinanceTransaction, V2PurchaseOrder
from app.models.v2_sales import V2SalesOrder
from app.services.v2_audit import append_v2_audit_log
from app.services.v2_export_jobs import (
    EXPORT_JOB_DEFAULT_LIMIT,
    EXPORT_JOB_MAX_LIMIT,
    create_v2_export_job,
    get_export_spec,
    process_v2_export_job,
    serialize_export_job,
)

router = APIRouter(prefix="/api/v2/exports", tags=["v2-exports"])


class V2ExportJobCreateRequest(BaseModel):
    export_type: str = Field(..., min_length=1, max_length=40)
    limit: int = Field(default=EXPORT_JOB_DEFAULT_LIMIT, ge=1, le=EXPORT_JOB_MAX_LIMIT)


def _error_response(status_code: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status_code, content=V2ErrorEnvelope(error=V2ErrorBody(code=code, message=message)).model_dump())


def _guard(account: V2AuthenticatedAccount, context: V2ExecutionContext):
    if account.account_id != context.account_id:
        return _error_response(403, "context_account_mismatch", "Context account mismatch")
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


@router.post("/jobs")
def create_export_job_v2(
    request: V2ExportJobCreateRequest,
    background_tasks: BackgroundTasks,
    account: V2AuthenticatedAccount = Depends(require_v2_authenticated_account),
    context: V2ExecutionContext = Depends(require_v2_execution_context),
    db_session: Session = Depends(get_db_session),
):
    if mismatch := _guard(account, context):
        return mismatch
    spec = get_export_spec(request.export_type)
    if spec is None:
        return _error_response(400, "unsupported_export_type", "Unsupported export type")
    ensure_v2_permission(context, spec.permission)
    job = create_v2_export_job(
        db_session,
        tenant_id=context.tenant_id,
        shop_id=context.shop_id,
        account_id=context.account_id,
        export_type=request.export_type,
        requested_limit=request.limit,
    )
    db_session.commit()
    background_tasks.add_task(process_v2_export_job, job.export_job_id)
    return {"data": {"job": serialize_export_job(job)}}


@router.get("/jobs")
def list_export_jobs_v2(
    account: V2AuthenticatedAccount = Depends(require_v2_authenticated_account),
    context: V2ExecutionContext = Depends(require_v2_execution_context),
    limit: int = Query(default=50, ge=1, le=200),
    db_session: Session = Depends(get_db_session),
):
    if mismatch := _guard(account, context):
        return mismatch
    jobs = list(
        db_session.scalars(
            select(V2ExportJob)
            .where(V2ExportJob.tenant_id == context.tenant_id, V2ExportJob.shop_id == context.shop_id)
            .order_by(V2ExportJob.created_at.desc(), V2ExportJob.export_job_id.desc())
            .limit(limit)
        )
    )
    visible_jobs = [job for job in jobs if get_export_spec(job.export_type) and get_export_spec(job.export_type).permission in set(context.permissions)]
    return {"data": {"jobs": [serialize_export_job(job) for job in visible_jobs]}}


@router.get("/jobs/{export_job_id}")
def get_export_job_v2(
    export_job_id: str,
    account: V2AuthenticatedAccount = Depends(require_v2_authenticated_account),
    context: V2ExecutionContext = Depends(require_v2_execution_context),
    db_session: Session = Depends(get_db_session),
):
    if mismatch := _guard(account, context):
        return mismatch
    job = db_session.scalar(select(V2ExportJob).where(V2ExportJob.export_job_id == export_job_id, V2ExportJob.tenant_id == context.tenant_id, V2ExportJob.shop_id == context.shop_id))
    if job is None:
        return _error_response(404, "export_job_not_found", "Export job not found")
    spec = get_export_spec(job.export_type)
    if spec is None:
        return _error_response(404, "export_job_not_found", "Export job not found")
    ensure_v2_permission(context, spec.permission)
    return {"data": {"job": serialize_export_job(job)}}


@router.get("/jobs/{export_job_id}/download")
def download_export_job_v2(
    export_job_id: str,
    account: V2AuthenticatedAccount = Depends(require_v2_authenticated_account),
    context: V2ExecutionContext = Depends(require_v2_execution_context),
    db_session: Session = Depends(get_db_session),
):
    if mismatch := _guard(account, context):
        return mismatch
    job = db_session.scalar(select(V2ExportJob).where(V2ExportJob.export_job_id == export_job_id, V2ExportJob.tenant_id == context.tenant_id, V2ExportJob.shop_id == context.shop_id))
    if job is None:
        return _error_response(404, "export_job_not_found", "Export job not found")
    spec = get_export_spec(job.export_type)
    if spec is None:
        return _error_response(404, "export_job_not_found", "Export job not found")
    ensure_v2_permission(context, spec.permission)
    if job.status != "completed" or not job.result_content:
        return _error_response(409, "export_job_not_ready", "Export job is not ready for download")
    append_v2_audit_log(
        db_session,
        tenant_id=context.tenant_id,
        shop_id=context.shop_id,
        action="export_job.download",
        actor_id=context.account_id,
        target_type="export_job",
        target_id=job.export_job_id,
        metadata={"export_type": job.export_type, "row_count": job.row_count},
    )
    db_session.commit()
    return Response(
        content=job.result_content,
        media_type=job.content_type,
        headers={"Content-Disposition": f'attachment; filename="{job.filename}"'},
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
    ensure_v2_permission(context, "exports:sales")
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
    ensure_v2_permission(context, "exports:purchasing")
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
    ensure_v2_permission(context, "exports:finance")
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
    ensure_v2_permission(context, "exports:inventory")
    events = list(db_session.scalars(select(V2InventoryLedgerEvent).where(V2InventoryLedgerEvent.tenant_id == context.tenant_id, V2InventoryLedgerEvent.shop_id == context.shop_id).order_by(V2InventoryLedgerEvent.occurred_at.desc(), V2InventoryLedgerEvent.event_id.desc()).limit(limit)))
    return _csv_response(
        "inventory-ledger.csv",
        ["event_type", "inventory_item_id", "quantity_delta", "quantity_after", "unit", "price", "source_type", "source_id", "reason", "occurred_at"],
        [[event.event_type, event.inventory_item_id, event.quantity_delta, event.quantity_after, event.unit, event.price or "", event.source_type, event.source_id, event.reason or "", event.occurred_at.isoformat() if event.occurred_at else ""] for event in events],
    )
