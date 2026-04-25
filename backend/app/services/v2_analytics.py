"""V2 Analytics services for revenue, sales ranking, and inventory alerts."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.models.v2_inventory import V2InventoryItem, V2InventoryLedgerEvent, V2InventoryStockSnapshot


@dataclass
class RevenueSummary:
    period: str
    total_revenue: float
    total_cost: float
    gross_profit: float
    transaction_count: int
    items_sold: float


@dataclass
class SalesRankItem:
    item_id: str
    item_name: str
    sku: str | None
    total_sold: float
    total_revenue: float
    avg_price: float
    rank: int


@dataclass
class LowStockAlert:
    item_id: str
    item_name: str
    sku: str | None
    current_quantity: float
    threshold: float
    shortage: float
    unit: str


def get_revenue_summary(
    db_session: Session,
    *,
    tenant_id: str,
    shop_id: str,
    days: int = 30,
) -> RevenueSummary:
    """Aggregate revenue from stock_out events over the last N days."""
    since = datetime.utcnow() - timedelta(days=days)

    # Aggregate stock_out events for active items only. Dashboard is a current
    # business view, so soft-deleted items must not leak into home analytics.
    result = db_session.execute(
        select(
            func.sum(V2InventoryLedgerEvent.quantity_delta * V2InventoryLedgerEvent.price).label("revenue"),
            func.sum(V2InventoryLedgerEvent.quantity_delta).label("items_sold"),
            func.count(V2InventoryLedgerEvent.event_id).label("tx_count"),
        )
        .join(
            V2InventoryItem,
            V2InventoryItem.inventory_item_id == V2InventoryLedgerEvent.inventory_item_id,
        )
        .where(
            V2InventoryLedgerEvent.tenant_id == tenant_id,
            V2InventoryLedgerEvent.shop_id == shop_id,
            V2InventoryItem.tenant_id == tenant_id,
            V2InventoryItem.status == "active",
            V2InventoryLedgerEvent.event_type == "stock_out",
            V2InventoryLedgerEvent.occurred_at >= since,
        )
    ).one_or_none()

    total_revenue = Decimal(result.revenue or 0)
    items_sold = Decimal(result.items_sold or 0)
    tx_count = result.tx_count or 0

    # Estimate cost from stock_in events (same period, same items)
    cost_result = db_session.execute(
        select(
            func.sum(V2InventoryLedgerEvent.quantity_delta * V2InventoryLedgerEvent.price).label("cost"),
        )
        .join(
            V2InventoryItem,
            V2InventoryItem.inventory_item_id == V2InventoryLedgerEvent.inventory_item_id,
        )
        .where(
            V2InventoryLedgerEvent.tenant_id == tenant_id,
            V2InventoryLedgerEvent.shop_id == shop_id,
            V2InventoryItem.tenant_id == tenant_id,
            V2InventoryItem.status == "active",
            V2InventoryLedgerEvent.event_type == "stock_in",
            V2InventoryLedgerEvent.occurred_at >= since,
        )
    ).scalar()

    total_cost = Decimal(cost_result or 0)
    normalized_revenue = abs(total_revenue)
    gross_profit = normalized_revenue - total_cost

    return RevenueSummary(
        period=f"last_{days}_days",
        total_revenue=float(normalized_revenue),
        total_cost=float(total_cost),
        gross_profit=float(gross_profit),
        transaction_count=tx_count,
        items_sold=float(abs(items_sold)),
    )


def get_sales_ranking(
    db_session: Session,
    *,
    tenant_id: str,
    shop_id: str,
    days: int = 30,
    limit: int = 10,
) -> list[SalesRankItem]:
    """Rank items by sales volume over the last N days."""
    since = datetime.utcnow() - timedelta(days=days)

    rows = db_session.execute(
        select(
            V2InventoryItem.inventory_item_id,
            V2InventoryItem.name,
            V2InventoryItem.sku,
            func.sum(V2InventoryLedgerEvent.quantity_delta).label("total_sold"),
            func.sum(V2InventoryLedgerEvent.quantity_delta * V2InventoryLedgerEvent.price).label("total_revenue"),
            func.avg(V2InventoryLedgerEvent.price).label("avg_price"),
        )
        .join(
            V2InventoryLedgerEvent,
            V2InventoryLedgerEvent.inventory_item_id == V2InventoryItem.inventory_item_id,
        )
        .where(
            V2InventoryLedgerEvent.tenant_id == tenant_id,
            V2InventoryLedgerEvent.shop_id == shop_id,
            V2InventoryItem.tenant_id == tenant_id,
            V2InventoryItem.status == "active",
            V2InventoryLedgerEvent.event_type == "stock_out",
            V2InventoryLedgerEvent.occurred_at >= since,
        )
        .group_by(
            V2InventoryItem.inventory_item_id,
            V2InventoryItem.name,
            V2InventoryItem.sku,
        )
        .order_by(desc("total_sold"))
        .limit(limit)
    ).all()

    ranked: list[SalesRankItem] = []
    for idx, row in enumerate(rows, start=1):
        ranked.append(
            SalesRankItem(
                item_id=row.inventory_item_id,
                item_name=row.name,
                sku=row.sku,
                total_sold=float(abs(row.total_sold or 0)),
                total_revenue=float(abs(row.total_revenue or 0)),
                avg_price=float(row.avg_price or 0),
                rank=idx,
            )
        )
    return ranked


def get_low_stock_alerts(
    db_session: Session,
    *,
    tenant_id: str,
    shop_id: str,
    limit: int = 20,
) -> list[LowStockAlert]:
    """Find items below their low-stock threshold."""
    rows = db_session.execute(
        select(
            V2InventoryItem.inventory_item_id,
            V2InventoryItem.name,
            V2InventoryItem.sku,
            V2InventoryStockSnapshot.current_quantity,
            V2InventoryStockSnapshot.low_stock_threshold,
            V2InventoryItem.default_unit,
        )
        .join(
            V2InventoryStockSnapshot,
            V2InventoryStockSnapshot.inventory_item_id == V2InventoryItem.inventory_item_id,
        )
        .where(
            V2InventoryItem.tenant_id == tenant_id,
            V2InventoryItem.status == "active",
            V2InventoryStockSnapshot.tenant_id == tenant_id,
            V2InventoryStockSnapshot.shop_id == shop_id,
            V2InventoryStockSnapshot.low_stock_threshold.isnot(None),
            V2InventoryStockSnapshot.current_quantity < V2InventoryStockSnapshot.low_stock_threshold,
        )
        .order_by(
            (V2InventoryStockSnapshot.low_stock_threshold - V2InventoryStockSnapshot.current_quantity).desc()
        )
        .limit(limit)
    ).all()

    alerts: list[LowStockAlert] = []
    for row in rows:
        threshold = row.low_stock_threshold or Decimal(0)
        current = row.current_quantity or Decimal(0)
        alerts.append(
            LowStockAlert(
                item_id=row.inventory_item_id,
                item_name=row.name,
                sku=row.sku,
                current_quantity=float(current),
                threshold=float(threshold),
                shortage=float(threshold - current),
                unit=row.default_unit or "个",
            )
        )
    return alerts


def get_daily_revenue_series(
    db_session: Session,
    *,
    tenant_id: str,
    shop_id: str,
    days: int = 7,
) -> list[dict]:
    """Return daily revenue for the last N days."""
    since = datetime.utcnow() - timedelta(days=days)

    rows = db_session.execute(
        select(
            func.date(V2InventoryLedgerEvent.occurred_at).label("day"),
            func.sum(V2InventoryLedgerEvent.quantity_delta * V2InventoryLedgerEvent.price).label("revenue"),
            func.sum(V2InventoryLedgerEvent.quantity_delta).label("items_sold"),
            func.count(V2InventoryLedgerEvent.event_id).label("tx_count"),
        )
        .join(
            V2InventoryItem,
            V2InventoryItem.inventory_item_id == V2InventoryLedgerEvent.inventory_item_id,
        )
        .where(
            V2InventoryLedgerEvent.tenant_id == tenant_id,
            V2InventoryLedgerEvent.shop_id == shop_id,
            V2InventoryItem.tenant_id == tenant_id,
            V2InventoryItem.status == "active",
            V2InventoryLedgerEvent.event_type == "stock_out",
            V2InventoryLedgerEvent.occurred_at >= since,
        )
        .group_by(func.date(V2InventoryLedgerEvent.occurred_at))
        .order_by("day")
    ).all()

    return [
        {
            "date": str(row.day),
            "revenue": float(abs(row.revenue or 0)),
            "items_sold": float(abs(row.items_sold or 0)),
            "transactions": row.tx_count or 0,
        }
        for row in rows
    ]
