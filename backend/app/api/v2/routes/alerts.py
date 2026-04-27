"""V2 Alerts API routes backed by V2 inventory stock snapshots."""

from typing import Annotated

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
from app.services.v2_alerts import generate_v2_low_stock_alerts

router = APIRouter(prefix="/api/v2/alerts", tags=["v2-alerts"])


def _context_mismatch() -> JSONResponse:
    return JSONResponse(
        status_code=403,
        content=V2ErrorEnvelope(
            error=V2ErrorBody(code="context_account_mismatch", message="Context account mismatch")
        ).model_dump(),
    )


@router.get("")
async def list_alerts(
    shop_id: Annotated[str, Query()],
    status: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
    account: V2AuthenticatedAccount = Depends(require_v2_authenticated_account),
    context: V2ExecutionContext = Depends(require_v2_execution_context),
    db_session: Session = Depends(get_db_session),
):
    if account.account_id != context.account_id or context.shop_id != shop_id:
        return _context_mismatch()

    generated = generate_v2_low_stock_alerts(db_session, shop_id)
    if status and status not in {"pending", "open"}:
        generated = []
    paged = generated[offset : offset + limit]

    return V2DataEnvelope(
        data={
            "alerts": [
                {
                    "alert_id": f"v2_low_stock_{alert.item_id}",
                    "alert_type": alert.alert_type,
                    "item_id": alert.item_id,
                    "item_name": alert.item_name,
                    "sku": alert.sku,
                    "status": "pending",
                    "severity": alert.severity,
                    "message": alert.message,
                    "stock": alert.stock,
                    "threshold": alert.threshold,
                    "created_at": None,
                }
                for alert in paged
            ],
            "pagination": {
                "limit": limit,
                "offset": offset,
                "count": len(paged),
                "total": len(generated),
            },
        }
    ).model_dump()


@router.patch("/{alert_id}/ack")
async def acknowledge_alert(
    alert_id: str,
    shop_id: Annotated[str, Query()],
    account: V2AuthenticatedAccount = Depends(require_v2_authenticated_account),
    context: V2ExecutionContext = Depends(require_v2_execution_context),
):
    if account.account_id != context.account_id or context.shop_id != shop_id:
        return _context_mismatch()

    return JSONResponse(
        status_code=410,
        content=V2ErrorEnvelope(
            error=V2ErrorBody(
                code="dynamic_alert_ack_not_supported",
                message="V2 alerts are generated dynamically from inventory snapshots and do not require acknowledgement.",
                details=[{"field": "alert_id", "message": alert_id}],
            )
        ).model_dump(),
    )
