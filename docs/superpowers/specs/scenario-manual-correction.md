# Scenario Spec: Manual Stock Correction

## Overview

手动库存纠错 - 当发现账面库存与实物不符时，人工修正库存数量。

## User Story

作为店主，盘点时发现实际有100个螺丝刀但系统显示95个，需要手动修正。

## Flow

```
┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
│ Review   │────>│ Adjust   │────>│ Approve  │────>│ Record   │
│ Inventory│     │ Quantity │     │ (Owner)  │     │ Event    │
└──────────┘     └──────────┘     └──────────┘     └──────────┘
```

## Technical Design

### Service Layer

**File:** `backend/app/services/v2_inventory.py` (extend)

```python
def create_manual_correction(
    db_session: Session,
    *,
    tenant_id: str,
    shop_id: str,
    inventory_item_id: str,
    old_quantity: Decimal,
    new_quantity: Decimal,
    reason: str,
    initiated_by: str,
) -> ManualCorrectionResult:
    """
    1. Create correction record
    2. Create ledger event (correction type)
    3. Update snapshot
    4. Log audit trail
    """
```

### API Endpoint

**File:** `backend/app/api/v2/routes/inventory.py` (extend)

```python
@router.post("/corrections")
def create_correction(
    correction: ManualCorrectionCreate,
    current_user: V2Account = Depends(get_current_user),
) -> CorrectionResponse:
    """创建库存纠错"""
```

## Implementation Steps

1. [ ] Extend `v2_inventory.py` with correction logic
2. [ ] Add correction table/model
3. [ ] Create API endpoint
4. [ ] Write tests

## Estimation

- Service: 2h
- Model: 0.5h
- API: 0.5h
- **Total: 3h**
