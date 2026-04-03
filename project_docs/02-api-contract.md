# 02. API 合同草案

## 1. 设计原则

- 资源名用复数、kebab-case
- 所有客户端请求统一走 `/api/v1`
- 成功响应统一返回 `data`
- 失败响应统一返回 `error`
- 写操作尽量返回对应任务或结果卡，减少客户端二次拼装

## 2. 通用响应结构

### 成功

```json
{
  "data": {}
}
```

### 列表

```json
{
  "data": [],
  "meta": {
    "next_cursor": "abc123"
  }
}
```

### 错误

```json
{
  "error": {
    "code": "validation_error",
    "message": "Request validation failed",
    "details": [
      {
        "field": "price",
        "message": "Price is required"
      }
    ]
  }
}
```

## 3. 核心资源

- `sessions`
- `messages`
- `media-uploads`
- `inventory-items`
- `inventory-events`
- `confirmations`
- `ocr-documents`
- `alerts`
- `audit-logs`

## 4. 会话与消息

### 4.1 获取或创建默认工作群会话

`POST /api/v1/sessions/bootstrap`

用途：

- App 启动时拿到当前店铺默认工作群

响应：

```json
{
  "data": {
    "session_id": "sess_001",
    "session_type": "workgroup",
    "title": "数字员工工作群",
    "participants": ["xiaoya", "laoli"]
  }
}
```

### 4.2 拉取会话消息

`GET /api/v1/sessions/:session_id/messages?cursor=...`

用途：

- 聊天页分页加载消息

### 4.3 发送消息

`POST /api/v1/sessions/:session_id/messages`

请求体：

```json
{
  "message_type": "voice",
  "text": null,
  "media_ids": ["media_001"],
  "client_request_id": "msg_local_001"
}
```

说明：

- `message_type` 可为 `text | voice | image | receipt-image`
- 语音消息先上传音频，再走此接口
- 图片和单据也走此接口，保持统一入口

响应：

```json
{
  "data": {
    "message_id": "msg_123",
    "task_run_id": "task_123",
    "status": "processing"
  }
}
```

## 5. 媒体上传

### 5.1 申请上传

`POST /api/v1/media-uploads`

请求体：

```json
{
  "media_type": "audio",
  "file_name": "voice.m4a",
  "content_type": "audio/m4a",
  "size_bytes": 102400
}
```

响应：

```json
{
  "data": {
    "media_id": "media_001",
    "upload_url": "https://...",
    "public_url": "https://..."
  }
}
```

说明：

- 首版建议走预签名上传
- 上传完成后再用 `messages` 接口提交业务消息

## 6. 库存查询

### 6.1 搜索商品

`GET /api/v1/inventory-items?query=红牛`

### 6.2 获取商品详情

`GET /api/v1/inventory-items/:item_id`

### 6.3 获取低库存列表

`GET /api/v1/alerts?type=low-stock`

## 7. 库存写操作

### 7.1 创建库存事件

`POST /api/v1/inventory-events`

请求体：

```json
{
  "task_run_id": "task_123",
  "event_type": "stock-in",
  "item_id": "item_001",
  "quantity": 3,
  "unit": "箱",
  "price": 41,
  "source": "voice-confirmed"
}
```

说明：

- 客户端正常情况下不直接调用这个接口
- 更常见的路径是通过确认接口驱动服务端内部落账

## 8. 确认链路

### 8.1 拉取待确认列表

`GET /api/v1/confirmations`

### 8.2 提交确认

`POST /api/v1/confirmations/:confirmation_id/approve`

请求体：

```json
{
  "fields": {
    "item_name": "得力活动扳手 12 寸",
    "quantity": 1,
    "unit": "件",
    "price": 18.5
  }
}
```

### 8.3 拒绝确认

`POST /api/v1/confirmations/:confirmation_id/reject`

## 9. OCR 与多模态

### 9.1 触发单据 OCR

`POST /api/v1/ocr-documents`

请求体：

```json
{
  "media_id": "media_receipt_001",
  "document_type": "purchase-receipt"
}
```

响应：

```json
{
  "data": {
    "ocr_document_id": "ocr_001",
    "status": "processing"
  }
}
```

### 9.2 获取 OCR 结果

`GET /api/v1/ocr-documents/:ocr_document_id`

响应：

```json
{
  "data": {
    "ocr_document_id": "ocr_001",
    "status": "completed",
    "fields": {
      "items": [
        { "name": "可乐", "quantity": 3, "unit": "箱", "price": 41 },
        { "name": "活动扳手", "quantity": 1, "unit": "件", "price": 18.5 }
      ],
      "total_amount": 141.5
    },
    "low_confidence_fields": ["items[1].name"]
  }
}
```

### 9.3 触发拍照查询

`POST /api/v1/inventory-items/recognize-and-query`

请求体：

```json
{
  "media_id": "media_img_001"
}
```

响应：

```json
{
  "data": {
    "recognized_item": {
      "item_id": "item_redbull",
      "name": "红牛 250ml",
      "confidence": 0.93
    },
    "inventory": {
      "stock": 2,
      "unit": "罐",
      "is_low_stock": true
    }
  }
}
```

## 10. 账本纠错

### 10.1 提交人工修正

`POST /api/v1/inventory-events/corrections`

请求体：

```json
{
  "item_id": "item_001",
  "corrected_quantity": 3,
  "reason": "实际清点数量与 AI 入库结果不一致"
}
```

响应：

```json
{
  "data": {
    "correction_event_id": "corr_001",
    "item_id": "item_001",
    "new_quantity": 3
  }
}
```

## 11. 审计记录

### 11.1 拉取审计时间线

`GET /api/v1/audit-logs?scope=inventory&limit=20`

## 12. 状态码建议

- `200` 查询成功
- `201` 创建成功
- `400` 请求格式错误
- `401` 未认证
- `403` 无权限
- `404` 资源不存在
- `409` 状态冲突
- `422` 字段校验失败
- `500` 未知错误

## 13. 客户端必须处理的错误码

- `media_upload_failed`
- `asr_failed`
- `ocr_failed`
- `recognition_low_confidence`
- `confirmation_required`
- `inventory_conflict`
- `item_not_found`

