from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api.deps.auth import AuthenticatedContext, require_authenticated_context
from app.contracts.alert import ListAlertsMeta, ListLowStockAlertsResponse, LowStockAlertData
from app.contracts.common import ErrorBody, ErrorEnvelope
from app.db.session import get_db_session
from app.models import InventoryItem
from app.services.alerts import LOW_STOCK_ALERT_TYPE, list_low_stock_alerts

router = APIRouter(prefix="/api/v1/alerts", tags=["alerts"])


def _unauthorized() -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content=ErrorEnvelope(
            error=ErrorBody(code="unauthorized", message="Unauthorized", details=[])
        ).model_dump(),
    )


def _unsupported_alert_type() -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=ErrorEnvelope(
            error=ErrorBody(
                code="unsupported_alert_type",
                message="Alert type is not supported",
                details=[],
            )
        ).model_dump(),
    )


@router.get("", response_model=ListLowStockAlertsResponse)
def get_alerts(
    auth: AuthenticatedContext = Depends(require_authenticated_context),
    alert_type: str = Query(default=LOW_STOCK_ALERT_TYPE, alias="type"),
    limit: int = Query(default=20, ge=1, le=50),
    db_session: Session = Depends(get_db_session),
) -> ListLowStockAlertsResponse | JSONResponse:
    if alert_type != LOW_STOCK_ALERT_TYPE:
        return _unsupported_alert_type()

    page = list_low_stock_alerts(db_session, shop_id=auth.shop_id, limit=limit)
    data: list[LowStockAlertData] = []
    for alert in page.items:
        item = db_session.get(InventoryItem, alert.item_id)
        if item is None:
            continue
        data.append(
            LowStockAlertData(
                alert_id=alert.alert_id,
                shop_id=alert.shop_id,
                alert_type=alert.alert_type,
                item_id=alert.item_id,
                item_name=item.name,
                status=alert.status,
                stock=alert.stock,
                threshold=alert.threshold,
                unit=item.default_unit,
                created_at=alert.created_at,
            )
        )
    return ListLowStockAlertsResponse(
        data=data,
        meta=ListAlertsMeta(count=len(data)),
    )
