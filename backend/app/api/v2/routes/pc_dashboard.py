from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps.v2_context import (
    V2AuthenticatedAccount,
    V2ExecutionContext,
    require_v2_authenticated_account,
    require_v2_execution_context,
)
from app.contracts.v2.common import V2DataEnvelope
from app.db.session import get_db_session
from app.services.v2_pc_dashboard import (
    get_pc_dashboard_daily_report,
    get_pc_dashboard_daily_report_history,
    get_pc_dashboard_execution_recaps,
    get_pc_dashboard_overview,
)

router = APIRouter(prefix="/api/v2/pc-dashboard", tags=["v2-pc-dashboard"])


@router.get("/overview", response_model=V2DataEnvelope[dict])
def get_pc_dashboard_overview_v2(
    account: V2AuthenticatedAccount = Depends(require_v2_authenticated_account),
    context: V2ExecutionContext = Depends(require_v2_execution_context),
    db_session: Session = Depends(get_db_session),
) -> V2DataEnvelope[dict]:
    _ensure_context_account_match(account=account, context=context)
    return V2DataEnvelope(
        data=get_pc_dashboard_overview(
            db_session,
            account_id=account.account_id,
            tenant_id=context.tenant_id,
            shop_id=context.shop_id,
        )
    )


@router.get("/daily-reports/today", response_model=V2DataEnvelope[dict])
def get_pc_dashboard_daily_report_today_v2(
    account: V2AuthenticatedAccount = Depends(require_v2_authenticated_account),
    context: V2ExecutionContext = Depends(require_v2_execution_context),
    db_session: Session = Depends(get_db_session),
) -> V2DataEnvelope[dict]:
    _ensure_context_account_match(account=account, context=context)
    return V2DataEnvelope(
        data=get_pc_dashboard_daily_report(
            db_session,
            account_id=account.account_id,
            tenant_id=context.tenant_id,
            shop_id=context.shop_id,
        )
    )


@router.get("/daily-reports/history", response_model=V2DataEnvelope[dict])
def get_pc_dashboard_daily_report_history_v2(
    days: int = 7,
    account: V2AuthenticatedAccount = Depends(require_v2_authenticated_account),
    context: V2ExecutionContext = Depends(require_v2_execution_context),
    db_session: Session = Depends(get_db_session),
) -> V2DataEnvelope[dict]:
    _ensure_context_account_match(account=account, context=context)
    return V2DataEnvelope(
        data=get_pc_dashboard_daily_report_history(
            db_session,
            tenant_id=context.tenant_id,
            shop_id=context.shop_id,
            days=days,
        )
    )


@router.get("/execution-recaps", response_model=V2DataEnvelope[dict])
def get_pc_dashboard_execution_recaps_v2(
    limit: int = 20,
    account: V2AuthenticatedAccount = Depends(require_v2_authenticated_account),
    context: V2ExecutionContext = Depends(require_v2_execution_context),
    db_session: Session = Depends(get_db_session),
) -> V2DataEnvelope[dict]:
    _ensure_context_account_match(account=account, context=context)
    return V2DataEnvelope(
        data=get_pc_dashboard_execution_recaps(
            db_session,
            tenant_id=context.tenant_id,
            shop_id=context.shop_id,
            limit=limit,
        )
    )


def _ensure_context_account_match(*, account: V2AuthenticatedAccount, context: V2ExecutionContext) -> None:
    if account.account_id != context.account_id:
        from fastapi import HTTPException

        raise HTTPException(status_code=403, detail="Context account mismatch")
