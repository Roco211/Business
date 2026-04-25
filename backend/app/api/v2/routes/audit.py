"""V2 Audit API routes for browsing operation logs."""

from datetime import datetime, timedelta
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
from app.models import V2AuditLog

router = APIRouter(prefix="/api/v2/audit-logs", tags=["v2-audit"])


@router.get("")
async def list_audit_logs(
    shop_id: Annotated[str, Query()],
    action: Annotated[str | None, Query()] = None,
    start_at: Annotated[datetime | None, Query()] = None,
    end_at: Annotated[datetime | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
    account: V2AuthenticatedAccount = Depends(require_v2_authenticated_account),
    context: V2ExecutionContext = Depends(require_v2_execution_context),
    db_session: Session = Depends(get_db_session),
):
    """List audit logs for a shop.
    
    Args:
        shop_id: Shop ID to filter logs
        action: Filter by action type (e.g., stock_in, stock_out, item_create)
        start_at: Filter logs after this time
        end_at: Filter logs before this time
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
    if shop_id != context.shop_id:
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content=V2ErrorEnvelope(
                error=V2ErrorBody(code="context_shop_mismatch", message="Shop does not match current context")
            ).model_dump(),
        )

    # Default to last 7 days if not specified
    if not end_at:
        end_at = datetime.utcnow()
    if not start_at:
        start_at = end_at - timedelta(days=7)

    query = select(V2AuditLog).where(
        V2AuditLog.tenant_id == context.tenant_id,
        V2AuditLog.shop_id == context.shop_id,
        V2AuditLog.created_at >= start_at,
        V2AuditLog.created_at <= end_at
    )
    
    if action:
        query = query.where(V2AuditLog.action == action)
    
    query = query.order_by(V2AuditLog.created_at.desc()).limit(limit).offset(offset)
    
    result = db_session.execute(query)
    logs = result.scalars().all()
    
    return V2DataEnvelope(
        data={
            "logs": [
                {
                    "audit_log_id": log.audit_log_id,
                    "action": log.action,
                    "actor_type": log.actor_type,
                    "actor_id": log.actor_id,
                    "target_type": log.target_type,
                    "target_id": log.target_id,
                    "metadata": log.metadata_json,
                    "created_at": log.created_at.isoformat() if log.created_at else None,
                }
                for log in logs
            ],
            "pagination": {
                "limit": limit,
                "offset": offset,
                "count": len(logs),
            },
        }
    ).model_dump()
