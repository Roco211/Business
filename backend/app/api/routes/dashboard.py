from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api.deps.auth import AuthenticatedContext, require_authenticated_context
from app.contracts.common import DataEnvelope, ErrorBody, ErrorEnvelope
from app.contracts.dashboard import DashboardSummaryData
from app.db.session import get_db_session
from app.models import Shop
from app.services.dashboard import get_dashboard_summary

router = APIRouter(prefix="/api/v1/dashboard", tags=["dashboard"])


def _not_found() -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content=ErrorEnvelope(
            error=ErrorBody(code="shop_not_found", message="Shop not found", details=[])
        ).model_dump(),
    )


@router.get("/summary", response_model=DataEnvelope[DashboardSummaryData])
def get_dashboard_summary_route(
    auth: AuthenticatedContext = Depends(require_authenticated_context),
    db_session: Session = Depends(get_db_session),
) -> DataEnvelope[DashboardSummaryData] | JSONResponse:
    shop = db_session.get(Shop, auth.shop_id)
    if shop is None:
        return _not_found()
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
