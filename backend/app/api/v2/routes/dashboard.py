"""V2 Dashboard API — single endpoint for home screen data aggregation."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps.v2_context import (
    V2AuthenticatedAccount,
    V2ExecutionContext,
    require_v2_authenticated_account,
    require_v2_execution_context,
)
from app.contracts.v2.common import V2DataEnvelope
from app.db.session import get_db_session
from app.services.v2_analytics import (
    get_revenue_summary,
    get_sales_ranking,
    get_low_stock_alerts,
    get_daily_revenue_series,
)

router = APIRouter(prefix="/api/v2/dashboard", tags=["v2-dashboard"])


@router.get("/summary", response_model=V2DataEnvelope[dict])
def get_dashboard_summary_v2(
    account: V2AuthenticatedAccount = Depends(require_v2_authenticated_account),
    context: V2ExecutionContext = Depends(require_v2_execution_context),
    days: int = Query(default=30, ge=1, le=365),
    db_session: Session = Depends(get_db_session),
) -> V2DataEnvelope[dict]:
    """Aggregate all dashboard data for the home screen.

    Returns:
        - revenue_summary: total revenue / cost / profit / tx count
        - sales_ranking: top 5 selling items
        - low_stock: items below threshold with shortage counts
        - daily_series: last 7 days revenue trend
        - pending_tasks: actionable items count
    """
    revenue = get_revenue_summary(
        db_session,
        tenant_id=context.tenant_id,
        shop_id=context.shop_id,
        days=days,
    )

    ranking = get_sales_ranking(
        db_session,
        tenant_id=context.tenant_id,
        shop_id=context.shop_id,
        days=days,
        limit=5,
    )

    alerts = get_low_stock_alerts(
        db_session,
        tenant_id=context.tenant_id,
        shop_id=context.shop_id,
        limit=20,
    )

    daily = get_daily_revenue_series(
        db_session,
        tenant_id=context.tenant_id,
        shop_id=context.shop_id,
        days=7,
    )

    return V2DataEnvelope(
        data={
            "revenue_summary": {
                "period": revenue.period,
                "total_revenue": revenue.total_revenue,
                "total_cost": revenue.total_cost,
                "gross_profit": revenue.gross_profit,
                "transaction_count": revenue.transaction_count,
                "items_sold": revenue.items_sold,
            },
            "sales_ranking": [
                {
                    "rank": item.rank,
                    "item_id": item.item_id,
                    "item_name": item.item_name,
                    "sku": item.sku,
                    "total_sold": item.total_sold,
                    "total_revenue": item.total_revenue,
                    "avg_price": item.avg_price,
                }
                for item in ranking
            ],
            "low_stock": {
                "count": len(alerts),
                "items": [
                    {
                        "item_id": alert.item_id,
                        "item_name": alert.item_name,
                        "sku": alert.sku,
                        "current_quantity": alert.current_quantity,
                        "threshold": alert.threshold,
                        "shortage": alert.shortage,
                        "unit": alert.unit,
                    }
                    for alert in alerts
                ],
            },
            "daily_revenue_series": daily,
            "pending_tasks": {
                "low_stock_count": len(alerts),
                "recent_tx_count": revenue.transaction_count,
            },
        }
    )
