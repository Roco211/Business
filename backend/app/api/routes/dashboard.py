from fastapi import APIRouter, Depends, Header, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.contracts.common import DataEnvelope, ErrorBody, ErrorEnvelope
from app.contracts.dashboard import DashboardSummaryData
from app.db.session import get_db_session
from app.services.bootstrap import ensure_default_shop
from app.services.dashboard import get_dashboard_summary

router = APIRouter(prefix="/api/v1/dashboard", tags=["dashboard"])


def _unauthorized() -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content=ErrorEnvelope(
            error=ErrorBody(code="unauthorized", message="Unauthorized", details=[])
        ).model_dump(),
    )


@router.get("/summary", response_model=DataEnvelope[DashboardSummaryData])
def get_dashboard_summary_route(
    authorization: str | None = Header(default=None),
    db_session: Session = Depends(get_db_session),
) -> DataEnvelope[DashboardSummaryData] | JSONResponse:
    if authorization != "Bearer mock_owner_token":
        return _unauthorized()

    shop = ensure_default_shop(db_session)
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
