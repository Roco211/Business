# Scenario Spec: Photo Stock In

## Overview

照片入库 - 用户拍摄进货单据，系统自动提取信息创建入库记录。

## User Story

作为店主，我拍张进货单的照片，系统自动录入商品信息。

## Flow

```
┌─────────┐     ┌────────┐     ┌─────────┐     ┌──────────┐
│  Photo  │────>│  OCR   │────>│ Extract │────>│ Confirm  │
│ (Upload)│     │(Vision)│     │ Receipt │     │  Save   │
└─────────┘     └────────┘     └─────────┘     └──────────┘
```

## Technical Design

### Service Layer

**File:** `backend/app/services/v2_photo.py`

```python
async def process_photo_stock_in(
    db_session: Session,
    *,
    tenant_id: str,
    shop_id: str,
    account_id: str,
    image_data: bytes,
) -> AsyncIterator[PhotoStockInEvent]:
    """
    1. OCR / Vision API 识别票据
    2. 提取结构化数据
       - supplier
       - items[]
       - total_amount
    3. 确认流程
    4. 创建入库事件
    """
```

## Dependencies

- ✅ `v2_receipt_documents.py` - Receipt OCR 已实现
- ⏳ `v2_photo.py` - 照片上传入口

## Implementation Steps

1. [ ] Reuse `v2_receipt_documents.py` logic
2. [ ] Create photo upload endpoint wrapper
3. [ ] SSE stream for extraction → confirmation
4. [ ] Write tests

## Estimation

- Reuse receipt logic: 1h
- Create wrapper: 1h
- Tests: 1h
- **Total: 3h**
