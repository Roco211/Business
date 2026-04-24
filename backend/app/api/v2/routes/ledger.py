"""V2 Ledger API for inventory transaction ledger queries."""
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
from app.services.v2_inventory import list_v2_inventory_events
from app.services.v2_analytics import (
    get_revenue_summary,
    get_sales_ranking,
    get_low_stock_alerts,
    get_daily_revenue_series,
)

router = APIRouter(prefix="/api/v2/ledger", tags=["v2-ledger"])


@router.get("/events", response_model=V2DataEnvelope[dict])
def list_ledger_events_v2(
    account: V2AuthenticatedAccount = Depends(require_v2_authenticated_account),
    context: V2ExecutionContext = Depends(require_v2_execution_context),
    item_id: str | None = Query(default=None),
    event_type: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=50),
    db_session: Session = Depends(get_db_session),
) -> V2DataEnvelope[dict]:
    """List inventory ledger events."""
    results = list_v2_inventory_events(
        db_session=db_session,
        tenant_id=context.tenant_id,
        shop_id=context.shop_id,
        limit=limit,
    )
    events_data = []
    for event, item in results:
        events_data.append({
            "event_id": event.event_id,
            "inventory_item_id": event.inventory_item_id,
            "item_name": item.name if item else None,
            "event_type": event.event_type,
            "quantity_delta": float(event.quantity_delta) if event.quantity_delta else 0,
            "quantity_after": float(event.quantity_after) if event.quantity_after else 0,
            "unit": event.unit,
            "price": float(event.price) if event.price else None,
            "source_type": event.source_type,
            "source_id": event.source_id,
            "reason": event.reason,
            "occurred_at": event.occurred_at.isoformat() if event.occurred_at else None,
        })
    return V2DataEnvelope(
        data={
            "events": events_data,
            "count": len(events_data),
        }
    )


@router.get("/revenue", response_model=V2DataEnvelope[dict])
def get_revenue_v2(
    account: V2AuthenticatedAccount = Depends(require_v2_authenticated_account),
    context: V2ExecutionContext = Depends(require_v2_execution_context),
    days: int = Query(default=30, ge=1, le=365),
    db_session: Session = Depends(get_db_session),
) -> V2DataEnvelope[dict]:
    """Get revenue summary for the shop."""
    summary = get_revenue_summary(
        db_session,
        tenant_id=context.tenant_id,
        shop_id=context.shop_id,
        days=days,
    )
    return V2DataEnvelope(
        data={
            "period": summary.period,
            "total_revenue": summary.total_revenue,
            "total_cost": summary.total_cost,
            "gross_profit": summary.gross_profit,
            "transaction_count": summary.transaction_count,
            "items_sold": summary.items_sold,
        }
    )


@router.get("/revenue/daily", response_model=V2DataEnvelope[dict])
def get_daily_revenue_v2(
    account: V2AuthenticatedAccount = Depends(require_v2_authenticated_account),
    context: V2ExecutionContext = Depends(require_v2_execution_context),
    days: int = Query(default=7, ge=1, le=30),
    db_session: Session = Depends(get_db_session),
) -> V2DataEnvelope[dict]:
    """Get daily revenue series."""
    series = get_daily_revenue_series(
        db_session,
        tenant_id=context.tenant_id,
        shop_id=context.shop_id,
        days=days,
    )
    return V2DataEnvelope(
        data={
            "days": days,
            "series": series,
        }
    )


@router.get("/sales-ranking", response_model=V2DataEnvelope[dict])
def get_sales_ranking_v2(
    account: V2AuthenticatedAccount = Depends(require_v2_authenticated_account),
    context: V2ExecutionContext = Depends(require_v2_execution_context),
    days: int = Query(default=30, ge=1, le=365),
    limit: int = Query(default=10, ge=1, le=50),
    db_session: Session = Depends(get_db_session),
) -> V2DataEnvelope[dict]:
    """Get top selling items ranking."""
    ranking = get_sales_ranking(
        db_session,
        tenant_id=context.tenant_id,
        shop_id=context.shop_id,
        days=days,
        limit=limit,
    )
    return V2DataEnvelope(
        data={
            "days": days,
            "ranking": [
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
        }
    )


@router.get("/low-stock-alerts", response_model=V2DataEnvelope[dict])
def get_low_stock_alerts_v2(
    account: V2AuthenticatedAccount = Depends(require_v2_authenticated_account),
    context: V2ExecutionContext = Depends(require_v2_execution_context),
    limit: int = Query(default=20, ge=1, le=50),
    db_session: Session = Depends(get_db_session),
) -> V2DataEnvelope[dict]:
    """Get low stock alert items."""
    alerts = get_low_stock_alerts(
        db_session,
        tenant_id=context.tenant_id,
        shop_id=context.shop_id,
        limit=limit,
    )
    return V2DataEnvelope(
        data={
            "alerts": [
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
            "count": len(alerts),
        }
    )
