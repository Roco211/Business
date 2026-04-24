# Scenario Spec: Audit Browsing

## Overview

审计浏览 - 查看库存历史、交易记录、操作日志。

## User Story

作为店主，我想知道最近30天谁改了什么库存。

## Flow

```
┌─────────┐     ┌──────────┐     ┌─────────┐
│ Filter  │────>│  Query   │────>│ Display │
│ Request │     │  Events  │     │  List   │
└─────────┘     └──────────┘     └─────────┘
```

## Technical Design

### Service Layer

**File:** `backend/app/services/v2_inventory.py` (extend)

```python
def list_inventory_events(
    db_session: Session,
    *,
    tenant_id: str,
    shop_id: str | None,
    inventory_item_id: str | None,
    event_type: str | None,  # stock_in, stock_out, correction
    start_date: datetime,
    end_date: datetime,
    limit: int,
    offset: int,
) -> PaginatedEvents:
    """查询库存事件历史"""

def get_inventory_audit_trail(
    db_session: Session,
    *,
    tenant_id: str,
    inventory_item_id: str,
) -> list[AuditEvent]:
    """获取单个商品的完整变更历史"""
```

### API Endpoint

**File:** `backend/app/api/v2/routes/inventory.py` (extend)

```python
@router.get("/events")
def list_events(
    shop_id: str | None = None,
    item_id: str | None = None,
    event_type: str | None = None,
    start: datetime = Query(...),
    end: datetime = Query(...),
    limit: int = 50,
    offset: int = 0,
) -> PaginatedEventList:
    """查询库存事件"""

@router.get("/items/{item_id}/audit")
def get_item_audit(
    item_id: str,
) -> list[AuditEvent]:
    """获取商品审计日志"""
```

## Implementation Steps

1. [ ] Extend query methods in `v2_inventory.py`
2. [ ] Create audit trail aggregation logic
3. [ ] Add API endpoints
4. [ ] Write tests

## Estimation

- Queries: 1.5h
- API: 1h
- Tests: 0.5h
- **Total: 3h**
