"""V2 Alerts API routes for low-stock alerts."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps.v2_context import (
    V2AuthenticatedAccount,
    V2ExecutionContext,
    require_v2_authenticated_account,
    require_v2_execution_context,
)
from app.contracts.v2.common import V2DataEnvelope, V2ErrorBody, V2ErrorEnvelope
from app.db.session import get_db_session
from app.models import Alert

router = APIRouter(prefix="/api/v2/alerts", tags=["v2-alerts"])


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
    """List low-stock alerts for a shop.
    
    Args:
        shop_id: Shop ID to filter alerts
        status: Filter by alert status (pending, acknowledged, resolved)
        limit: Max results per page
        offset: Pagination offset
    """
    if account.account_id != context.account_id:
        return JSONResponse(
            status_code=403,
            content=V2ErrorEnvelope(
                error=V2ErrorBody(code="context_account_mismatch", message="Context account mismatch")
            ).model_dump(),
        )

    query = select(Alert).where(Alert.shop_id == shop_id)
    
    if status:
        query = query.where(Alert.status == status)
    
    query = query.order_by(Alert.created_at.desc()).limit(limit).offset(offset)
    
    result = db_session.execute(query)
    alerts = result.scalars().all()
    
    return V2DataEnvelope(
        data={
            "alerts": [
                {
                    "alert_id": a.alert_id,
                    "alert_type": a.alert_type,
                    "item_id": a.item_id,
                    "status": a.status,
                    "stock": float(a.stock) if a.stock else None,
                    "threshold": float(a.threshold) if a.threshold else None,
                    "created_at": a.created_at.isoformat() if a.created_at else None,
                }
                for a in alerts
            ],
            "pagination": {
                "limit": limit,
                "offset": offset,
                "count": len(alerts),
            },
        }
    ).model_dump()


@router.patch("/{alert_id}/ack")
async def acknowledge_alert(
    alert_id: str,
    shop_id: Annotated[str, Query()],
    account: V2AuthenticatedAccount = Depends(require_v2_authenticated_account),
    context: V2ExecutionContext = Depends(require_v2_execution_context),
    db_session: Session = Depends(get_db_session),
):
    """Acknowledge an alert."""
    if account.account_id != context.account_id:
        return JSONResponse(
            status_code=403,
            content=V2ErrorEnvelope(
                error=V2ErrorBody(code="context_account_mismatch", message="Context account mismatch")
            ).model_dump(),
        )

    query = select(Alert).where(
        Alert.alert_id == alert_id,
        Alert.shop_id == shop_id
    )
    result = db_session.execute(query)
    alert = result.scalar_one_or_none()
    
    if not alert:
        return JSONResponse(
            status_code=404,
            content=V2ErrorEnvelope(
                error=V2ErrorBody(code="alert_not_found", message="Alert not found")
            ).model_dump(),
        )
    
    alert.status = "acknowledged"
    db_session.commit()
    
    return V2DataEnvelope(
        data={"alert_id": alert_id, "status": "acknowledged"}
    ).model_dump()
