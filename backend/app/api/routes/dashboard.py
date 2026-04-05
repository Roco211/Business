from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps.auth import AuthenticatedContext, require_authenticated_context
from app.contracts.common import DataEnvelope
from app.contracts.dashboard import DashboardSummaryData
from app.db.session import get_db_session
from app.models import Shop
from app.services.dashboard import get_dashboard_summary

router = APIRouter(prefix="/api/v1/dashboard", tags=["dashboard"])


@router.get("/summary", response_model=DataEnvelope[DashboardSummaryData])
def get_dashboard_summary_route(
    auth: AuthenticatedContext = Depends(require_authenticated_context),
    db_session: Session = Depends(get_db_session),
) -> DataEnvelope[DashboardSummaryData]:
    shop = db_session.get(Shop, auth.shop_id)
    if shop is None:
        raise LookupError(auth.shop_id)
    summary = get_dashboard_summary(db_session, shop=shop)
    return DataEnvelope(
        data=DashboardSummaryData(
            shop_id=summary.shop_id,
            today_stock_in_count=summary.today_stock_in_count,
            today_task_completed_count=summary.today_task_completed_count,
            pending_confirmations_count=summary.pending_confirmations_count,
            open_low_stock_alert_count=summary.open_low_stock_alert_count,
            last_inventory_event_at=summary.last_inventory_event_at,
        )
    )
