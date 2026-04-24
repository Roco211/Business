"""V2 Alert generation from inventory stock snapshots.

Generates low-stock alerts dynamically from V2InventoryStockSnapshot
instead of relying on a separate Alert table.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.models.v2_inventory import V2InventoryStockSnapshot, V2InventoryItem


@dataclass
class V2Alert:
    alert_type: str
    item_id: str
    item_name: str
    sku: str
    stock: float
    threshold: float
    severity: str
    message: str


def generate_v2_low_stock_alerts(db_session: Session, shop_id: str) -> list[V2Alert]:
    """Generate low-stock alerts from V2 inventory snapshots.
    
    Args:
        db_session: Database session
        shop_id: Shop ID to check
        
    Returns:
        List of V2Alert objects for items below threshold
    """
    alerts: list[V2Alert] = []
    
    # Query snapshots with item info
    stmt = (
        select(V2InventoryStockSnapshot, V2InventoryItem)
        .join(V2InventoryItem, V2InventoryItem.inventory_item_id == V2InventoryStockSnapshot.inventory_item_id)
        .where(
            V2InventoryStockSnapshot.shop_id == shop_id,
            V2InventoryStockSnapshot.low_stock_threshold.isnot(None),
        )
    )
    
    for snapshot, item in db_session.execute(stmt).all():
        qty = snapshot.current_quantity or Decimal("0")
        threshold = snapshot.low_stock_threshold or Decimal("0")
        
        if qty < threshold:
            severity = "critical" if qty == 0 else "warning"
            alerts.append(V2Alert(
                alert_type="low_stock",
                item_id=snapshot.inventory_item_id,
                item_name=item.name,
                sku=item.sku or "",
                stock=float(qty),
                threshold=float(threshold),
                severity=severity,
                message=f"库存不足: 当前 {qty} {item.default_unit}, 阈值 {threshold}",
            ))
    
    return alerts
