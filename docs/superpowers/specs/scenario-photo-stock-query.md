# Scenario Spec: Photo Stock Query

## Overview

照片库存查询 - 用户拍摄商品照片，系统识别商品后查询库存。

## User Story

作为店主，我不记得商品名称，拍张照片就能查到库存。

## Flow

```
┌─────────┐     ┌────────┐     ┌─────────┐     ┌────────┐
│  Photo  │────>│  OCR/  │────>│  Match  │────>│ Query  │
│ (Upload)│     │ Vision │     │  Item   │     │ Result │
└─────────┘     └────────┘     └─────────┘     └────────┘
```

## Technical Design

### Service Layer

**File:** `backend/app/services/v2_photo.py`

```python
async def process_photo_stock_query(
    db_session: Session,
    *,
    tenant_id: str,
    shop_id: str,
    image_data: bytes,
    mime_type: str,
) -> PhotoQueryResult:
    """
    1. OCR / Vision API 识别图片文字和物体
    2. 匹配库存商品 (fuzzy matching)
    3. 查询库存快照
    4. 返回结果
    """
```

### API Endpoint

**File:** `backend/app/api/v2/routes/photo.py`

```python
@router.post("/photo/stock-query")
async def photo_stock_query(
    image: UploadFile = File(...),
    shop_id: str = Form(...),
) -> StockQueryResponse:
    """照片库存查询"""
```

## Implementation Steps

1. [ ] Create `v2_photo.py` service
2. [ ] Integrate with v2_media_assets for image processing
3. [ ] Add OCR + item matching logic
4. [ ] Create API route
5. [ ] Write tests

## Estimation

- Service: 2h
- OCR integration: 1h
- **Total: 3h**
