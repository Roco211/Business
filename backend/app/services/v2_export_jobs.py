from __future__ import annotations

import csv
import io
import uuid
from dataclasses import dataclass
from datetime import timedelta
from typing import Any, Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_session_factory
from app.models import V2ExportJob, V2InventoryLedgerEvent
from app.models.v2_commercial import V2FinanceTransaction, V2PurchaseOrder
from app.models.v2_sales import V2SalesOrder
from app.services.v2_audit import append_v2_audit_log
from app.services.v2_time import utc_now_naive

EXPORT_JOB_MAX_LIMIT = 50_000
EXPORT_JOB_DEFAULT_LIMIT = 5_000
EXPORT_JOB_RETENTION_DAYS = 7


@dataclass(frozen=True)
class V2ExportSpec:
    export_type: str
    permission: str
    filename: str
    headers: list[str]
    row_loader: Callable[[Session, str, str, int], list[list[object]]]


def _serialize(value: object) -> object:
    if hasattr(value, "isoformat"):
        return value.isoformat()  # type: ignore[no-any-return]
    if value is None:
        return ""
    return value


def _load_sales_orders(db: Session, tenant_id: str, shop_id: str, limit: int) -> list[list[object]]:
    orders = list(
        db.scalars(
            select(V2SalesOrder)
            .where(V2SalesOrder.tenant_id == tenant_id, V2SalesOrder.shop_id == shop_id)
            .order_by(V2SalesOrder.created_at.desc(), V2SalesOrder.sales_order_id.desc())
            .limit(limit)
        )
    )
    return [
        [
            order.order_no,
            order.customer_name or "",
            order.total_amount,
            order.status,
            order.sales_order_id,
            order.customer_id or "",
            order.payment_method,
            _serialize(order.created_at),
        ]
        for order in orders
    ]


def _load_purchase_orders(db: Session, tenant_id: str, shop_id: str, limit: int) -> list[list[object]]:
    orders = list(
        db.scalars(
            select(V2PurchaseOrder)
            .where(V2PurchaseOrder.tenant_id == tenant_id, V2PurchaseOrder.shop_id == shop_id)
            .order_by(V2PurchaseOrder.created_at.desc(), V2PurchaseOrder.purchase_order_id.desc())
            .limit(limit)
        )
    )
    return [
        [order.order_no, order.supplier_id, order.total_amount, order.status, order.purchase_order_id, order.note or "", _serialize(order.created_at)]
        for order in orders
    ]


def _load_finance_transactions(db: Session, tenant_id: str, shop_id: str, limit: int) -> list[list[object]]:
    transactions = list(
        db.scalars(
            select(V2FinanceTransaction)
            .where(V2FinanceTransaction.tenant_id == tenant_id, V2FinanceTransaction.shop_id == shop_id)
            .order_by(V2FinanceTransaction.occurred_at.desc(), V2FinanceTransaction.finance_transaction_id.desc())
            .limit(limit)
        )
    )
    return [
        [
            tx.transaction_type,
            tx.direction,
            tx.amount,
            tx.source_type,
            tx.source_id,
            tx.counterparty_name or "",
            tx.note or "",
            _serialize(tx.occurred_at),
        ]
        for tx in transactions
    ]


def _load_inventory_ledger(db: Session, tenant_id: str, shop_id: str, limit: int) -> list[list[object]]:
    events = list(
        db.scalars(
            select(V2InventoryLedgerEvent)
            .where(V2InventoryLedgerEvent.tenant_id == tenant_id, V2InventoryLedgerEvent.shop_id == shop_id)
            .order_by(V2InventoryLedgerEvent.occurred_at.desc(), V2InventoryLedgerEvent.event_id.desc())
            .limit(limit)
        )
    )
    return [
        [
            event.event_type,
            event.inventory_item_id,
            event.quantity_delta,
            event.quantity_after,
            event.unit,
            event.price or "",
            event.source_type,
            event.source_id,
            event.reason or "",
            _serialize(event.occurred_at),
        ]
        for event in events
    ]


EXPORT_SPECS: dict[str, V2ExportSpec] = {
    "sales_orders": V2ExportSpec(
        export_type="sales_orders",
        permission="exports:sales",
        filename="sales-orders.csv",
        headers=["order_no", "customer_name", "total_amount", "status", "sales_order_id", "customer_id", "payment_method", "created_at"],
        row_loader=_load_sales_orders,
    ),
    "purchase_orders": V2ExportSpec(
        export_type="purchase_orders",
        permission="exports:purchasing",
        filename="purchase-orders.csv",
        headers=["order_no", "supplier_id", "total_amount", "status", "purchase_order_id", "note", "created_at"],
        row_loader=_load_purchase_orders,
    ),
    "finance_transactions": V2ExportSpec(
        export_type="finance_transactions",
        permission="exports:finance",
        filename="finance-transactions.csv",
        headers=["transaction_type", "direction", "amount", "source_type", "source_id", "counterparty_name", "note", "occurred_at"],
        row_loader=_load_finance_transactions,
    ),
    "inventory_ledger": V2ExportSpec(
        export_type="inventory_ledger",
        permission="exports:inventory",
        filename="inventory-ledger.csv",
        headers=["event_type", "inventory_item_id", "quantity_delta", "quantity_after", "unit", "price", "source_type", "source_id", "reason", "occurred_at"],
        row_loader=_load_inventory_ledger,
    ),
}


def get_export_spec(export_type: str) -> V2ExportSpec | None:
    return EXPORT_SPECS.get(export_type)


def build_csv(headers: list[str], rows: list[list[object]]) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(headers)
    writer.writerows(rows)
    return buffer.getvalue()


def create_v2_export_job(
    db: Session,
    *,
    tenant_id: str,
    shop_id: str,
    account_id: str,
    export_type: str,
    requested_limit: int,
) -> V2ExportJob:
    spec = EXPORT_SPECS[export_type]
    now = utc_now_naive()
    safe_limit = max(1, min(int(requested_limit), EXPORT_JOB_MAX_LIMIT))
    job = V2ExportJob(
        export_job_id=f"vexport_{uuid.uuid4().hex}"[:40],
        tenant_id=tenant_id,
        shop_id=shop_id,
        account_id=account_id,
        export_type=export_type,
        status="queued",
        requested_limit=safe_limit,
        row_count=0,
        filename=spec.filename,
        content_type="text/csv; charset=utf-8",
        storage_kind="database",
        result_content=None,
        error_code=None,
        error_message=None,
        metadata_json={"phase": "K5", "large_data_protection": True},
        expires_at=now + timedelta(days=EXPORT_JOB_RETENTION_DAYS),
        started_at=None,
        completed_at=None,
        created_at=now,
        updated_at=now,
    )
    db.add(job)
    append_v2_audit_log(
        db,
        tenant_id=tenant_id,
        shop_id=shop_id,
        action="export_job.create",
        actor_id=account_id,
        target_type="export_job",
        target_id=job.export_job_id,
        metadata={"export_type": export_type, "requested_limit": safe_limit},
    )
    return job


def process_v2_export_job(export_job_id: str) -> None:
    session = get_session_factory()()
    try:
        job = session.get(V2ExportJob, export_job_id)
        if job is None or job.status not in {"queued", "failed"}:
            return
        now = utc_now_naive()
        job.status = "running"
        job.started_at = now
        job.updated_at = now
        session.commit()

        spec = EXPORT_SPECS[job.export_type]
        rows = spec.row_loader(session, job.tenant_id, job.shop_id, job.requested_limit)
        csv_content = build_csv(spec.headers, rows)
        done = utc_now_naive()
        job.status = "completed"
        job.row_count = len(rows)
        job.result_content = csv_content
        job.completed_at = done
        job.updated_at = done
        job.error_code = None
        job.error_message = None
        append_v2_audit_log(
            session,
            tenant_id=job.tenant_id,
            shop_id=job.shop_id,
            action="export_job.complete",
            actor_id=job.account_id,
            target_type="export_job",
            target_id=job.export_job_id,
            metadata={"export_type": job.export_type, "row_count": len(rows), "storage_kind": job.storage_kind},
        )
        session.commit()
    except Exception as exc:  # pragma: no cover - defensive failure state
        session.rollback()
        job = session.get(V2ExportJob, export_job_id)
        if job is not None:
            job.status = "failed"
            job.error_code = "export_generation_failed"
            job.error_message = type(exc).__name__
            job.updated_at = utc_now_naive()
            append_v2_audit_log(
                session,
                tenant_id=job.tenant_id,
                shop_id=job.shop_id,
                action="export_job.fail",
                actor_id=job.account_id,
                target_type="export_job",
                target_id=job.export_job_id,
                metadata={"export_type": job.export_type, "error_type": type(exc).__name__},
            )
            session.commit()
    finally:
        session.close()


def serialize_export_job(job: V2ExportJob) -> dict[str, Any]:
    return {
        "export_job_id": job.export_job_id,
        "export_type": job.export_type,
        "status": job.status,
        "requested_limit": job.requested_limit,
        "row_count": job.row_count,
        "filename": job.filename,
        "content_type": job.content_type,
        "storage_kind": job.storage_kind,
        "download_ready": job.status == "completed" and bool(job.result_content),
        "error_code": job.error_code,
        "error_message": job.error_message,
        "expires_at": _serialize(job.expires_at),
        "started_at": _serialize(job.started_at),
        "completed_at": _serialize(job.completed_at),
        "created_at": _serialize(job.created_at),
        "updated_at": _serialize(job.updated_at),
    }
