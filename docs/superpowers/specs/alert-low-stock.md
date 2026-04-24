# Scenario Spec: Low-Stock Alerts

## Overview

低库存警报 - 自动监控库存低于阈值时发送通知。

## User Story

作为店主，当螺丝刀库存少于10个时，系统自动提醒我补货。

## Flow

```
┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
│ Periodic │────>│ Compare  │────>│ Generate │────>│ Notify   │
│  Check   │     │ Threshold│     │  Alert   │     │ User    │
└──────────┘     └──────────┘     └──────────┘     └──────────┘
```

## Technical Design

### Service Layer

**File:** `backend/app/services/v2_inventory.py` (extend)

```python
def check_low_stock(
    db_session: Session,
    *,
    tenant_id: str,
    shop_id: str | None,
) -> list[LowStockAlert]:
    """检查低库存商品"""

def set_low_stock_threshold(
    db_session: Session,
    *,
    tenant_id: str,
    shop_id: str,
    inventory_item_id: str,
    threshold: Decimal,
) -> None:
    """设置商品低库存阈值"""
```

**File:** `backend/app/services/v2_alerts.py` (new)

```python
async def generate_low_stock_alerts(
    db_session: Session,
    *,
    tenant_id: str,
) -> None:
    """
    1. 扫描所有商品
    2. 对比 stock_threshold
    3. 低于阈值：创建 Alert 事件
    4. 发送通知（Web push/Feishu）
    """

async def send_alert_notification(
    alert: LowStockAlert,
) -> None:
    """发送警报通知"""
```

### Alert Table

```python
class V2InventoryAlert(Base):
    __tablename__ = "v2_inventory_alerts"
    
    alert_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(...)
    shop_id: Mapped[str] = mapped_column(...)
    inventory_item_id: Mapped[str] = mapped_column(...)
    alert_type: Mapped[str] = mapped_column(String(32))  # low_stock
    current_quantity: Mapped[Decimal]
    threshold: Mapped[Decimal]
    status: Mapped[str] = mapped_column(String(20))  # active, acknowledged, resolved
    created_at: Mapped[datetime]
    acknowledged_at: Mapped[datetime | None]
    resolved_at: Mapped[datetime | None]
```

### Worker Job

**File:** `backend/app/workers/alert_checker.py`

```python
@periodic_task(cron="0 */2 * * *")  # 每2小时
def check_all_low_stock():
    """定期检查所有租户的低库存"""
```

## Implementation Steps

1. [ ] Create `V2InventoryAlert` model
2. [ ] Extend `v2_inventory.py` with threshold set/get
3. [ ] Create `v2_alerts.py` service
4. [ ] Create alert worker
5. [ ] Create API endpoints
6. [ ] Write tests

## Estimation

- Model: 0.5h
- Service: 1.5h
- Worker: 1h
- API: 1h
- **Total: 4h**
