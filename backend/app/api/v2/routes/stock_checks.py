"""V2 Stock Check (Inventory Audit) API routes."""
from __future__ import annotations

from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps.v2_context import (
    V2AuthenticatedAccount,
    V2ExecutionContext,
    require_v2_authenticated_account,
    require_v2_execution_context,
)
from app.contracts.v2.common import V2DataEnvelope, V2ErrorBody, V2ErrorEnvelope
from app.db.session import get_db_session
from app.services.v2_stock_check import (
    V2StockCheckAlreadyResolvedError,
    V2StockCheckNotFoundError,
    V2StockCheckValidationError,
    create_v2_stock_check,
    get_v2_stock_check_summary,
    list_v2_stock_checks,
    resolve_v2_stock_check,
)

router = APIRouter(prefix="/api/v2/stock-checks", tags=["v2-stock-checks"])


class CreateStockCheckRequest(BaseModel):
    inventory_item_id: str
    actual_quantity: float
    check_method: str = "manual"
    notes: str | None = None


class ResolveStockCheckRequest(BaseModel):
    resolution: str  # "correct" | "ignore" | "recheck"


def _context_account_mismatch() -> JSONResponse:
    return JSONResponse(
        status_code=403,
        content=V2ErrorEnvelope(
            error=V2ErrorBody(code="context_account_mismatch", message="Context account mismatch")
        ).model_dump(),
    )


@router.post("", response_model=V2DataEnvelope[dict])
def create_stock_check_v2(
    payload: CreateStockCheckRequest,
    account: V2AuthenticatedAccount = Depends(require_v2_authenticated_account),
    context: V2ExecutionContext = Depends(require_v2_execution_context),
    db_session: Session = Depends(get_db_session),
) -> V2DataEnvelope[dict] | JSONResponse:
    """Create a new stock check record."""
    if account.account_id != context.account_id:
        return _context_account_mismatch()

    try:
        result = create_v2_stock_check(
            db_session,
            tenant_id=context.tenant_id,
            shop_id=context.shop_id,
            inventory_item_id=payload.inventory_item_id,
            actual_quantity=Decimal(str(payload.actual_quantity)),
            check_method=payload.check_method,
            notes=payload.notes,
            created_by_account_id=account.account_id,
        )
    except Exception as exc:
        return JSONResponse(
            status_code=400,
            content=V2ErrorEnvelope(
                error=V2ErrorBody(code="stock_check_error", message=str(exc))
            ).model_dump(),
        )

    record = result.check_record
    return V2DataEnvelope(
        data={
            "check_id": record.check_id,
            "inventory_item_id": record.inventory_item_id,
            "system_quantity": float(record.system_quantity),
            "actual_quantity": float(record.actual_quantity),
            "difference": float(record.difference),
            "unit": record.unit,
            "status": record.status,
            "check_method": record.check_method,
            "notes": record.notes,
            "created_at": record.created_at.isoformat() if record.created_at else None,
        }
    )


@router.get("", response_model=V2DataEnvelope[dict])
def list_stock_checks_v2(
    account: V2AuthenticatedAccount = Depends(require_v2_authenticated_account),
    context: V2ExecutionContext = Depends(require_v2_execution_context),
    status: Annotated[str | None, Query()] = None,
    limit: int = Query(default=20, ge=1, le=50),
    db_session: Session = Depends(get_db_session),
) -> V2DataEnvelope[dict] | JSONResponse:
    """List stock check records."""
    if account.account_id != context.account_id:
        return _context_account_mismatch()

    records = list_v2_stock_checks(
        db_session,
        tenant_id=context.tenant_id,
        shop_id=context.shop_id,
        status=status,
        limit=limit,
    )

    return V2DataEnvelope(
        data={
            "checks": [
                {
                    "check_id": record.check_id,
                    "inventory_item_id": record.inventory_item_id,
                    "item_name": item.name,
                    "sku": item.sku,
                    "system_quantity": float(record.system_quantity),
                    "actual_quantity": float(record.actual_quantity),
                    "difference": float(record.difference),
                    "unit": record.unit,
                    "status": record.status,
                    "check_method": record.check_method,
                    "notes": record.notes,
                    "created_at": record.created_at.isoformat() if record.created_at else None,
                    "resolved_at": record.resolved_at.isoformat() if record.resolved_at else None,
                }
                for record, item in records
            ],
            "count": len(records),
        }
    )


@router.get("/summary", response_model=V2DataEnvelope[dict])
def get_stock_check_summary_v2(
    account: V2AuthenticatedAccount = Depends(require_v2_authenticated_account),
    context: V2ExecutionContext = Depends(require_v2_execution_context),
    db_session: Session = Depends(get_db_session),
) -> V2DataEnvelope[dict] | JSONResponse:
    """Get stock check summary."""
    if account.account_id != context.account_id:
        return _context_account_mismatch()

    summary = get_v2_stock_check_summary(
        db_session,
        tenant_id=context.tenant_id,
        shop_id=context.shop_id,
    )

    return V2DataEnvelope(data=summary)


@router.post("/{check_id}/resolve", response_model=V2DataEnvelope[dict])
def resolve_stock_check_v2(
    check_id: str,
    payload: ResolveStockCheckRequest,
    account: V2AuthenticatedAccount = Depends(require_v2_authenticated_account),
    context: V2ExecutionContext = Depends(require_v2_execution_context),
    db_session: Session = Depends(get_db_session),
) -> V2DataEnvelope[dict] | JSONResponse:
    """Resolve a stock check by applying correction or marking as handled."""
    if account.account_id != context.account_id:
        return _context_account_mismatch()

    try:
        result = resolve_v2_stock_check(
            db_session,
            tenant_id=context.tenant_id,
            shop_id=context.shop_id,
            check_id=check_id,
            resolution=payload.resolution,
            created_by_account_id=account.account_id,
        )
    except V2StockCheckNotFoundError:
        return JSONResponse(
            status_code=404,
            content=V2ErrorEnvelope(
                error=V2ErrorBody(code="stock_check_not_found", message="Stock check not found")
            ).model_dump(),
        )
    except V2StockCheckAlreadyResolvedError as exc:
        return JSONResponse(
            status_code=409,
            content=V2ErrorEnvelope(
                error=V2ErrorBody(code="already_resolved", message=str(exc))
            ).model_dump(),
        )
    except V2StockCheckValidationError as exc:
        return JSONResponse(
            status_code=422,
            content=V2ErrorEnvelope(
                error=V2ErrorBody(code="validation_error", message=str(exc))
            ).model_dump(),
        )

    record = result.check_record
    return V2DataEnvelope(
        data={
            "check_id": record.check_id,
            "status": record.status,
            "correction_event_id": result.correction_event_id,
            "new_quantity": float(result.new_quantity) if result.new_quantity else None,
            "resolved_at": record.resolved_at.isoformat() if record.resolved_at else None,
        }
    )
