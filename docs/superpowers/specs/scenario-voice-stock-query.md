# Scenario Spec: Voice Stock Query

## Overview

语音库存查询场景 - 用户通过语音询问商品库存，系统转录后查询并流式返回结果。

## User Story

作为店主，我想通过语音询问"螺丝刀还有几个"，系统立即告诉我当前库存量。

## Flow

```
┌─────────┐     ┌────────┐     ┌─────────┐     ┌────────┐     ┌─────────┐
│  User   │────>│  ASR   │────>│   NLP   │────>│ Query  │────>│  SSE    │
│ (Voice) │     │(Speech)│     │(Intent) │     │(DB)    │     │(Stream) │
└─────────┘     └────────┘     └─────────┘     └────────┘     └─────────┘
```

## Technical Design

### Service Layer

**File:** `backend/app/services/v2_voice.py`

```python
async def process_voice_stock_query(
    db_session: Session,
    *,
    tenant_id: str,
    shop_id: str,
    audio_data: bytes,
    mime_type: str,
) -> AsyncIterator[VoiceQueryEvent]:
    """
    1. ASR 转录音频 -> 文本
    2. NLP 解析意图 -> 查询参数
    3. 查询库存快照
    4. 流式返回结果
    """
```

### API Endpoint

**File:** `backend/app/api/v2/routes/voice.py`

```python
@router.post("/voice/stock-query")
async def voice_stock_query(
    audio: UploadFile = File(...),
    shop_id: str = Form(...),
    current_user: V2Account = Depends(get_current_user),
) -> StreamingResponse:
    """语音库存查询 - SSE 流式响应"""
```

### Request/Response

Request:
- `audio`: audio/webm 或 audio/wav
- `shop_id`: 门店ID

Response (SSE):
```
event: transcription
data: {"text": "螺丝刀还有几个"}

event: intent
data: {"intent": "stock_query", "item_name": "螺丝刀"}

event: result
data: {"item": {...}, "stock": {"quantity": 45}}

event: complete
data: {}
```

## Dependencies

- ✅ `v2_conversation.py` - 会话管理
- ✅ `v2_inventory.py` - 库存查询
- ✅ `v2_media_assets.py` - 音频存储
- ⏳ ASR Provider (Volcano Engine)
- ⏳ NLP Intent Parser

## Implementation Steps

1. [ ] Create `v2_voice.py` service with ASR integration
2. [ ] Create `v2_voice_query.py` for stock query logic
3. [ ] Create API route `voice.py` with SSE streaming
4. [ ] Write tests `test_v2_voice_stock_query.py`
5. [ ] Create CLI demo script

## Acceptance Criteria

- [ ] 用户上传语音文件，系统正确转录
- [ ] 从转录文本提取商品名称和意图
- [ ] 查询返回当前库存数量
- [ ] SSE 流式响应，延迟 < 2s
- [ ] 支持错误处理和重试

## Estimation

- Service: 2h
- API Route: 1h
- Tests: 1h
- **Total: 4h**
