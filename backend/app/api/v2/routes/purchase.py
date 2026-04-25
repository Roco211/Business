"""V2 Purchase Suggestion API routes."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api.deps.v2_context import (
    V2AuthenticatedAccount,
    V2ExecutionContext,
    require_v2_authenticated_account,
    require_v2_execution_context,
)
from app.contracts.v2.common import V2DataEnvelope, V2ErrorBody, V2ErrorEnvelope
from app.db.session import get_db_session
from app.services.v2_purchase import (
    get_purchase_suggestion_summary,
    get_purchase_suggestions,
)

router = APIRouter(prefix="/api/v2/purchase", tags=["v2-purchase"])


def _context_account_mismatch() -> JSONResponse:
    return JSONResponse(
        status_code=403,
        content=V2ErrorEnvelope(
            error=V2ErrorBody(code="context_account_mismatch", message="Context account mismatch")
        ).model_dump(),
    )


@router.get("/suggestions", response_model=V2DataEnvelope[dict])
def get_purchase_suggestions_v2(
    account: V2AuthenticatedAccount = Depends(require_v2_authenticated_account),
    context: V2ExecutionContext = Depends(require_v2_execution_context),
    days_of_sales: int = Query(default=30, ge=7, le=90),
    safety_days: int = Query(default=7, ge=1, le=30),
    limit: int = Query(default=20, ge=1, le=50),
    db_session: Session = Depends(get_db_session),
) -> V2DataEnvelope[dict] | JSONResponse:
    """Get purchase suggestions based on low stock and sales velocity.

    Args:
        days_of_sales: Days of sales history for velocity calculation
        safety_days: Extra safety stock days
        limit: Max suggestions
    """
    if account.account_id != context.account_id:
        return _context_account_mismatch()

    suggestions = get_purchase_suggestions(
        db_session,
        tenant_id=context.tenant_id,
        shop_id=context.shop_id,
        days_of_sales=days_of_sales,
        safety_days=safety_days,
        limit=limit,
    )

    return V2DataEnvelope(
        data={
            "suggestions": [
                {
                    "item_id": s.item_id,
                    "item_name": s.item_name,
                    "sku": s.sku,
                    "current_quantity": s.current_quantity,
                    "threshold": s.threshold,
                    "shortage": s.shortage,
                    "unit": s.unit,
                    "suggested_quantity": s.suggested_quantity,
                    "reason": s.reason,
                    "priority": s.priority,
                    "estimated_cost": s.estimated_cost,
                }
                for s in suggestions
            ],
            "count": len(suggestions),
            "summary": {
                "high_priority": sum(1 for s in suggestions if s.priority == "high"),
                "medium_priority": sum(1 for s in suggestions if s.priority == "medium"),
                "low_priority": sum(1 for s in suggestions if s.priority == "low"),
                "total_estimated_cost": sum(s.estimated_cost for s in suggestions),
            },
        }
    )


@router.get("/summary", response_model=V2DataEnvelope[dict])
def get_purchase_summary_v2(
    account: V2AuthenticatedAccount = Depends(require_v2_authenticated_account),
    context: V2ExecutionContext = Depends(require_v2_execution_context),
    db_session: Session = Depends(get_db_session),
) -> V2DataEnvelope[dict] | JSONResponse:
    """Get a quick summary of purchase needs."""
    if account.account_id != context.account_id:
        return _context_account_mismatch()

    summary = get_purchase_suggestion_summary(
        db_session,
        tenant_id=context.tenant_id,
        shop_id=context.shop_id,
    )

    return V2DataEnvelope(data=summary)
