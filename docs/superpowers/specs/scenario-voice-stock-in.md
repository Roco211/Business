# Scenario Spec: Voice Stock In

## Overview

语音入库场景 - 用户通过语音描述"昨天进了50箱矿泉水，每瓶2块钱"，系统自动创建入库记录。

## User Story

作为店主，我想直接说话就能录入进货信息，不用手动填写表单。

## Flow

```
┌─────────┐     ┌────────┐     ┌─────────┐     ┌──────────┐     ┌────────┐
│  User   │────>│  ASR   │────>│  NLP    │────>│ Extract │────>│ Commit │
│ (Voice) │     │(Speech)│     │(Entity) │     │ Confirm │     │ Ledger │
└─────────┘     └────────┘     └─────────┘     └──────────┘     └────────┘
                                                                                │
                                                                                v
                                                                         ┌──────────┐
                                                                         │  Event   │
                                                                         │  Saved   │
                                                                         └──────────┘
```

## Technical Design

### Service Layer

**File:** `backend/app/services/v2_voice.py`

```python
async def process_voice_stock_in(
    db_session: Session,
    *,
    tenant_id: str,
    shop_id: str,
    account_id: str,
    audio_data: bytes,
) -> AsyncIterator[VoiceStockInEvent]:
    """
    1. ASR 转录音频
    2. NLP 提取结构化数据
       - item_name: "矿泉水"
       - quantity: 50
       - unit: "箱"
       - price: 2.00
    3. 询问确认
    4. 用户确认后提交
    5. 创建入库事件
    """
```

### Request/Response

Request:
- `audio`: audio/webm 或 audio/wav
- `shop_id`: 门店ID

Response (SSE):
```
event: transcription
data: {"text": "昨天进了50箱矿泉水，每箱24瓶，每瓶2块钱"}

event: extraction
data: {
  "item_name": "矿泉水",
  "quantity": 50,
  "unit": "箱",
  "price": 48.00,
  " confidence": 0.92
}

event: clarification
data: {
  "message": "确认入库：矿泉水50箱，单价48元/箱？",
  "options": ["确认", "修改商品名", "修改数量", "取消"]
}

event: pending_confirm
data: {"confirmation_id": "conf-123"}

event: committed
data: {
  "event_id": "evt-456",
  "item_id": "item-789",
  "snapshot": {...}
}
```

## Implementation Steps

1. [ ] Extend `v2_voice.py` with stock_in logic
2. [ ] Create entity extraction parser
3. [ ] Integration with confirmation flow
4. [ ] Create API endpoint
5. [ ] Write tests

## Estimation

- Service extension: 2h
- Entity extraction: 1h
- Confirmation integration: 1h
- **Total: 4h**
