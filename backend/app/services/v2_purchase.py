"""V2 Purchase Suggestion services based on inventory alerts and sales velocity."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.models.v2_inventory import V2InventoryItem, V2InventoryLedgerEvent, V2InventoryStockSnapshot
from app.services.v2_analytics import get_low_stock_alerts


@dataclass
class PurchaseSuggestion:
    item_id: str
    item_name: str
    sku: str | None
    current_quantity: float
    threshold: float
    shortage: float
    unit: str
    suggested_quantity: float
    reason: str
    priority: str  # "high" | "medium" | "low"
    estimated_cost: float


def get_purchase_suggestions(
    db_session: Session,
    *,
    tenant_id: str,
    shop_id: str,
    days_of_sales: int = 30,
    safety_days: int = 7,
    limit: int = 20,
) -> list[PurchaseSuggestion]:
    """Generate purchase suggestions based on low stock alerts and sales velocity.

    Algorithm:
    1. Find items below threshold (low stock alerts)
    2. Calculate average daily sales velocity from stock_out events
    3. Suggest quantity = shortage + (velocity * safety_days)
    4. Estimate cost from last known price

    Args:
        db_session: Database session
        tenant_id: Tenant ID
        shop_id: Shop ID
        days_of_sales: How many days of sales history to use for velocity
        safety_days: Extra stock to cover this many days of sales
        limit: Max suggestions to return

    Returns:
        List of purchase suggestions sorted by priority
    """
    since = datetime.utcnow() - timedelta(days=days_of_sales)

    # Get low stock alerts
    alerts = get_low_stock_alerts(
        db_session,
        tenant_id=tenant_id,
        shop_id=shop_id,
        limit=limit,
    )

    if not alerts:
        return []

    suggestions: list[PurchaseSuggestion] = []

    for alert in alerts:
        # Calculate sales velocity (average daily stock_out)
        velocity_result = db_session.execute(
            select(
                func.sum(V2InventoryLedgerEvent.quantity_delta).label("total_sold"),
                func.count(V2InventoryLedgerEvent.event_id).label("tx_count"),
            )
            .where(
                V2InventoryLedgerEvent.tenant_id == tenant_id,
                V2InventoryLedgerEvent.shop_id == shop_id,
                V2InventoryLedgerEvent.inventory_item_id == alert.item_id,
                V2InventoryLedgerEvent.event_type == "stock_out",
                V2InventoryLedgerEvent.occurred_at >= since,
            )
        ).one_or_none()

        total_sold = abs(Decimal(velocity_result.total_sold or 0))
        tx_count = velocity_result.tx_count or 0

        # Daily velocity
        daily_velocity = float(total_sold) / days_of_sales if days_of_sales > 0 else 0

        # Suggested quantity = shortage + safety stock
        shortage = alert.shortage
        safety_stock = daily_velocity * safety_days
        suggested = shortage + safety_stock

        # Round up to reasonable amount
        if suggested < 10:
            suggested = max(suggested, 5)  # Minimum order
        elif suggested < 50:
            suggested = round(suggested / 5) * 5  # Round to nearest 5
        else:
            suggested = round(suggested / 10) * 10  # Round to nearest 10

        # Get last price for cost estimation
        last_price_row = db_session.execute(
            select(V2InventoryLedgerEvent.price)
            .where(
                V2InventoryLedgerEvent.tenant_id == tenant_id,
                V2InventoryLedgerEvent.shop_id == shop_id,
                V2InventoryLedgerEvent.inventory_item_id == alert.item_id,
                V2InventoryLedgerEvent.price.isnot(None),
            )
            .order_by(V2InventoryLedgerEvent.occurred_at.desc())
            .limit(1)
        ).one_or_none()

        last_price = float(last_price_row.price or 0) if last_price_row else 0
        estimated_cost = suggested * last_price if last_price > 0 else 0

        # Determine priority
        if shortage > alert.threshold * 0.5 or alert.current_quantity == 0:
            priority = "high"
        elif shortage > alert.threshold * 0.2:
            priority = "medium"
        else:
            priority = "low"

        # Build reason
        if alert.current_quantity == 0:
            reason = f"已缺货，建议立即进货{suggested:.0f}{alert.unit}"
        elif daily_velocity > 0:
            days_until_empty = alert.current_quantity / daily_velocity if daily_velocity > 0 else float('inf')
            reason = f"库存不足，按日均销量{daily_velocity:.1f}{alert.unit}/天，约{days_until_empty:.0f}天售罄，建议进货{suggested:.0f}{alert.unit}"
        else:
            reason = f"库存低于阈值，建议进货{suggested:.0f}{alert.unit}"

        suggestions.append(
            PurchaseSuggestion(
                item_id=alert.item_id,
                item_name=alert.item_name,
                sku=alert.sku,
                current_quantity=alert.current_quantity,
                threshold=alert.threshold,
                shortage=shortage,
                unit=alert.unit,
                suggested_quantity=suggested,
                reason=reason,
                priority=priority,
                estimated_cost=estimated_cost,
            )
        )

    # Sort by priority (high first) then by shortage
    priority_order = {"high": 0, "medium": 1, "low": 2}
    suggestions.sort(key=lambda s: (priority_order.get(s.priority, 3), -s.shortage))

    return suggestions[:limit]


def get_purchase_suggestion_summary(
    db_session: Session,
    *,
    tenant_id: str,
    shop_id: str,
) -> dict:
    """Get a quick summary of purchase needs."""
    suggestions = get_purchase_suggestions(
        db_session,
        tenant_id=tenant_id,
        shop_id=shop_id,
        limit=50,
    )

    if not suggestions:
        return {
            "needs_purchase": False,
            "total_items": 0,
            "total_estimated_cost": 0,
            "high_priority_count": 0,
            "message": "库存充足，暂无进货需求",
        }

    high_priority = sum(1 for s in suggestions if s.priority == "high")
    total_cost = sum(s.estimated_cost for s in suggestions)

    return {
        "needs_purchase": True,
        "total_items": len(suggestions),
        "total_estimated_cost": total_cost,
        "high_priority_count": high_priority,
        "message": f"有{len(suggestions)}个商品需要进货，其中{high_priority}个紧急",
    }
