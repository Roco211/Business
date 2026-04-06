# 02. API 合同草案

## 1. 设计原则

- 资源名用复数、kebab-case
- 所有客户端请求统一走 `/api/v1`
- 成功响应统一返回 `data`
- 失败响应统一返回 `error`
- 写操作尽量返回对应任务或结果卡，减少客户端二次拼装
- 当前施工阶段的 owner 发起写请求必须支持 `client_request_id` 幂等

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

- `auth`
- `dashboard`
- `sessions`
- `messages`
- `media-uploads`
- `inventory-items`
- `inventory-events`
- `confirmations`
- `ocr-documents`
- `alerts`
- `audit-logs`

## 4. 当前阶段鉴权合同

### 4.1 Owner Login

`POST /api/v1/auth/login`

用途：

- 为老板级别的 API 握手返回 opaque bearer token

请求体：

```json
{
  "email": "owner@example.com",
  "password": "dev-password"
}
```

说明：

- 默认 demo 流程使用 `owner@example.com` / `dev-password`，其他环境由实际老板账号填写
- 返回值除了 access_token，还带回老板与店铺上下文 (`owner_actor_id`, `shop_id`, `shop_name`)

响应：

```json
{
  "data": {
    "access_token": "<opaque bearer token>",
    "token_type": "Bearer",
    "owner_actor_id": "owner_default",
    "shop_id": "shop_default",
    "shop_name": "演示店铺"
  }
}
```

使用说明：

- 将 bearer token 通过 `Authorization: Bearer <opaque bearer token>` 发送在老板接口的 REST 请求头中
- WebSocket 连接与重连时通过 `token=<opaque bearer token>` 查询参数携带同一串令牌

### 4.2 REST 鉴权规则

- 除 `/health` 和 `/api/v1/auth/login` 外，其余接口默认都要求：
  - `Authorization: Bearer <opaque bearer token>`

当前阶段约定：

- `401`
  - token 缺失、无效或过期
- `403`
  - token 所属店铺与请求资源店铺不一致

### 4.3 WebSocket 鉴权规则

- WebSocket 使用与 REST 相同的 token
- 当前阶段通过 query 参数传递：
  - `WS /api/v1/ws/sessions/:session_id?token=<opaque bearer token>`

---

## 5. 工作台概览

### 5.1 获取工作台 summary

`GET /api/v1/dashboard/summary`

用途：

- 提供 `DashboardScreen` 顶部概览卡片所需聚合数据

响应：

```json
{
  "data": {
    "shop_id": "shop_default",
    "today_stock_in_count": 6,
    "today_task_completed_count": 12,
    "pending_confirmations_count": 2,
    "open_low_stock_alert_count": 4,
    "last_inventory_event_at": "2026-04-03T13:40:12.000Z"
  }
}
```

说明：

- 低库存列表和待确认列表仍分别通过：
  - `GET /api/v1/alerts?type=low-stock`
  - `GET /api/v1/confirmations?status=pending`
- `summary` 只负责提供工作台总览，不替代列表接口

## 6. 会话与消息

### 6.1 获取或创建默认工作群会话

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

### 6.2 拉取会话消息

`GET /api/v1/sessions/:session_id/messages?cursor=...`

用途：

- 聊天页分页加载消息

### 6.3 发送消息

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
- owner 发起的请求当前阶段必须携带 `client_request_id`
- 当前阶段服务端以 `(session_id, actor_type, actor_id, client_request_id)` 作为幂等键

幂等规则：

- 首次提交成功：
  - 创建 `message_id` 和 `task_run_id`
- 若同一幂等键重复提交且请求体一致：
  - 返回第一次创建的 `message_id` 和 `task_run_id`
- 若同一幂等键重复提交但负载不一致：
  - 返回 `409 idempotency_conflict`

媒体校验规则：

- `media_ids` 中的媒体必须全部处于 `uploaded` 状态
- 若媒体尚未完成上传确认：
  - 返回 `409 media_not_ready`

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

## 7. 媒体上传

### 7.1 申请上传

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
- 申请上传后，客户端仍需先把文件真正上传到对象存储
- 上传完成后必须调用 `complete` 接口确认上传成功

### 7.2 确认上传完成

`POST /api/v1/media-uploads/:media_id/complete`

请求体：

```json
{
  "checksum_sha256": "abc123...",
  "size_bytes": 102400
}
```

响应：

```json
{
  "data": {
    "media_id": "media_001",
    "status": "uploaded"
  }
}
```

说明：

- 服务端在该接口中把 `media_uploads.status` 从 `pending` 切到 `uploaded`
- 只有 `uploaded` 状态的媒体才允许被挂到 `messages` 接口中
- 如果对象不存在、校验失败或尺寸不符，应返回：
  - `409 media_upload_incomplete`

## 8. 库存查询

### 8.1 搜索商品

`GET /api/v1/inventory-items?query=红牛`

### 8.2 获取商品详情

`GET /api/v1/inventory-items/:item_id`

### 8.3 获取低库存列表

`GET /api/v1/alerts?type=low-stock`

## 9. 库存写操作

### 9.1 创建库存事件

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

## 10. 确认链路

### 10.1 拉取待确认列表

`GET /api/v1/confirmations?status=pending&limit=20`

### 10.2 提交确认

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

说明：

- 普通补货确认继续使用单条字段：
  - `item_name | item_id`
  - `quantity`
  - `unit`
  - `price`
- 当 `confirmation_type = receipt-stock-in-batch` 时，`fields` 改为批量行项目：

```json
{
  "fields": {
    "items": [
      {
        "line_id": "line_1",
        "item_name": "Red Bull 250ml",
        "quantity": 3,
        "unit": "can",
        "price": 41.0
      },
      {
        "line_id": "line_2",
        "item_name": "Coca Cola 500ml",
        "quantity": 2,
        "unit": "bottle",
        "price": 12.0
      }
    ]
  }
}
```

- receipt 批量确认约束：
  - 所有行项目在同一个事务中一起落账
  - 任一行校验失败时，整次 approval 失败，不写入任何库存真相
  - 每一行都会生成独立 `inventory_event` 和 `audit_log`

### 10.3 拒绝确认

`POST /api/v1/confirmations/:confirmation_id/reject`

## 11. OCR 与多模态

### 11.1 触发单据 OCR

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

### 11.2 获取 OCR 结果

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

### 11.3 触发拍照查询

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

## 12. 外部 DTO 命名与映射规则

为了避免 API、领域模型和物理 schema 之间命名漂移，当前阶段统一约定：

- API 返回 OCR 字段时统一使用：
  - `fields`
- 数据库物理字段命名使用：
  - `extracted_fields`

- API 返回商品主图时统一使用：
  - `image_url`
- 数据库物理字段使用：
  - `image_media_id`
- 服务端负责把 `image_media_id -> media_uploads.public_url -> image_url`

- API 在任务回执中可以直接返回：
  - `confirmation_id`
- 数据库中的真实关系通过：
  - `confirmations.task_run_id`

也就是说：

- API 命名优先对前端友好
- DB 命名优先对关系清晰
- 服务端必须显式承担 DTO / Mapper 转换，不允许前端猜字段来源

## 13. 账本纠错

### 13.1 提交人工修正

`POST /api/v1/inventory-events/corrections`

请求体：

```json
{
  "item_id": "item_001",
  "expected_quantity": 5,
  "corrected_quantity": 3,
  "reason": "实际清点数量与 AI 入库结果不一致"
}
```

说明：

- `expected_quantity` 用于乐观并发校验
- 如果商品当前库存已不是提交方看到的数量，返回 `409 inventory_conflict`

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

## 14. 审计记录

### 14.1 拉取审计时间线

`GET /api/v1/audit-logs?scope=inventory&limit=20`

## 15. 状态码建议

- `200` 查询成功
- `201` 创建成功
- `400` 请求格式错误
- `401` 未认证
- `403` 无权限
- `404` 资源不存在
- `409` 状态冲突
- `422` 字段校验失败
- `500` 未知错误

## 16. 客户端必须处理的错误码

- `media_upload_failed`
- `media_upload_incomplete`
- `media_not_ready`
- `asr_failed`
- `ocr_failed`
- `recognition_low_confidence`
- `confirmation_required`
- `inventory_conflict`
- `item_not_found`
- `idempotency_conflict`

## 16.1 Manual Stock-Out Addendum

`POST /api/v1/inventory-events/stock-out`

Request body:

```json
{
  "item_id": "item_001",
  "expected_quantity": 6,
  "stock_out_quantity": 2,
  "reason": "Walk-in sale"
}
```

Response:

```json
{
  "data": {
    "stock_out_event_id": "inv_evt_123",
    "item_id": "item_001",
    "new_quantity": 4
  }
}
```

Notes:

- this route is used by `LedgerScreen` for manual owner-triggered stock-out
- `expected_quantity` provides optimistic concurrency protection
- when inventory changed after the ledger was loaded, the server returns `409 inventory_conflict`
- when `stock_out_quantity <= 0` or exceeds current stock, the server returns `422 validation_error`
- success also writes `inventory_events(event_type = stock-out)`, `audit_logs(action = inventory.stock_out_submitted)`, refreshed low-stock alerts, and realtime events

## 16.2 Runtime Stock-Out Confirmation Addendum

`POST /api/v1/confirmations/{confirmation_id}/approve`

When `confirmation_type = stock-out`, the approval payload uses stock-out-specific fields:

```json
{
  "fields": {
    "item_id": "item_001",
    "item_name": "Cola",
    "stock_out_quantity": 2,
    "reason": "Walk-in sale"
  }
}
```

Notes:

- `item_id` is optional when `item_name` uniquely resolves to one active inventory item in the shop
- `stock_out_quantity` must be numeric and greater than 0
- `reason` is required
- if the item cannot be uniquely resolved, the server returns:
  - `404 inventory_item_not_found`
  - `409 inventory_item_ambiguous`
  - `409 inventory_item_inactive`
- if requested quantity exceeds current stock, the server returns `422 confirmation_fields_invalid`
- successful approval resolves the pending confirmation and task run, writes one durable `inventory_events(event_type = stock-out)` row, writes `audit_logs(action = inventory.stock_out_submitted)`, refreshes low-stock alerts, and appends the usual realtime projections

## 16.3 Session Stream Replay Addendum

`GET /api/v1/sessions/{session_id}/stream-events?after_seq=12&limit=50`

Response:

```json
{
  "data": [
    {
      "event_id": "evt_123",
      "seq": 13,
      "event_type": "message.created",
      "session_id": "sess_default",
      "task_run_id": "task_123",
      "message_id": "msg_123",
      "occurred_at": "2026-04-05T14:10:00.000Z",
      "data": {
        "preview_text": "restock cola"
      }
    }
  ]
}
```

Notes:

- this route replays only durable business events from `session_stream_events`
- transport events such as `session.ready` and `stream.keepalive` are not included
- events are returned in ascending `seq` order
- `after_seq` defaults to `0`
- `limit` is clamped to a safe upper bound
- auth matches the rest of the current owner-only surface:
  - `Authorization: Bearer <opaque bearer token>`

WebSocket reconnect addendum:

- websocket clients may now reconnect with:
  - `WS /api/v1/ws/sessions/{session_id}?token=<opaque bearer token>&after_seq=<last_durable_seq>`
- when `after_seq` is provided, the server replays durable events with `seq > after_seq`
- when `after_seq` is omitted, the server preserves the earlier MVP behavior and starts from the session's current tail
- replay state is tracked per websocket connection rather than per session

## 17. Trial Readiness Addendum

### 17.1 System Readiness

`GET /api/v1/system/readiness`

Auth:

- `Authorization: Bearer <opaque bearer token>`

Response:

```json
{
  "data": {
    "overall_status": "ready",
    "runtime_mode": "trial",
    "checks": {
      "object_storage": {
        "status": "ready",
        "mode": "s3-compatible",
        "message": "object storage is configured with a live provider.",
        "details": {
          "provider": "s3-compatible"
        }
      },
      "asr": {
        "status": "ready",
        "mode": "real-provider",
        "message": "asr is configured with a live provider.",
        "details": {
          "provider": "real-provider",
          "allow_mock_fallback": "false"
        }
      },
      "ocr": {
        "status": "ready",
        "mode": "real-provider",
        "message": "ocr is configured with a live provider.",
        "details": {
          "provider": "real-provider",
          "allow_mock_fallback": "false"
        }
      },
      "vision": {
        "status": "ready",
        "mode": "real-provider",
        "message": "vision is configured with a live provider.",
        "details": {
          "provider": "real-provider",
          "allow_mock_fallback": "false"
        }
      }
    }
  }
}
```

Notes:

- in trial mode, any mock/unset/unsupported dependency or missing live configuration reports degraded readiness
- for ASR/OCR/Vision in trial mode, `*_ALLOW_MOCK_FALLBACK` must be `0`, otherwise readiness degrades with `reason=trial_guardrail`

### 17.2 Demo Bootstrap Clarification

`POST /api/v1/system/demo/bootstrap`

Auth:

- `Authorization: Bearer <opaque bearer token>`

Notes:

- this endpoint is for local demo reset/bootstrap only
- it remains protected and only works for the default seeded shop context
- operators should use `/api/v1/system/readiness` for trial checks and must not treat demo bootstrap as a trial readiness signal

### 17.3 Upload Completion Clarification

`POST /api/v1/media-uploads/{media_id}/complete`

Notes:

- this call now requires that object storage already contains the uploaded bytes for the requested media object
- issuing `complete` before the file bytes are uploaded returns `409 media_upload_conflict`
- checksum and size validation happen against the uploaded object before the record can transition to `uploaded`

### 17.4 Local Demo Mock Upload URL Clarification

`POST /api/v1/media-uploads`

Notes:

- in local-demo mock object-storage mode, `upload_url` is backend-served and writable through:
  - `PUT /api/v1/media-uploads/mock/{object_key}`
- clients should still follow the standard flow:
  - `create` -> `PUT upload_url` with real bytes -> `complete`
- this keeps local-demo behavior aligned with trial object-storage flow, where bytes must exist before `complete`

## 17.5 Pilot Summary Addendum

`GET /api/v1/system/pilot-summary?hours=24`

Auth:

- `Authorization: Bearer <opaque bearer token>`

Query:

- `hours`: optional integer, min `1`, max `168`, default `24`

Response:

```json
{
  "data": {
    "time_window": {
      "hours": 24,
      "started_at": "2026-04-07T00:00:00",
      "ended_at": "2026-04-08T00:00:00"
    },
    "task_totals": {
      "voice-stock-query": {
        "completed": 2,
        "failed": 1
      },
      "photo-stock-in": {
        "awaiting-confirmation": 1,
        "completed": 1
      }
    },
    "confirmations": {
      "created": 3,
      "approved": 1,
      "rejected": 1
    },
    "telemetry_task_count": 4,
    "low_confidence_count": 1,
    "fallback_count": 1,
    "provider_failures": {
      "vision_unavailable": 1
    },
    "trial_provider_profile": "pilot-v1"
  }
}
```

Notes:

- the route is protected with the same owner auth model as `/api/v1/system/readiness`
- `task_totals` is grouped by `task_type` and then by task `status`
- counts are scoped to the authenticated shop and the requested rolling time window
- `confirmations.created` is counted by `confirmations.created_at`
- `confirmations.approved` and `confirmations.rejected` are counted by `confirmations.resolved_at`
- `telemetry_task_count` counts distinct `task_run_id` values from matching pilot telemetry rows in the requested window
- `low_confidence_count`, `fallback_count`, and `provider_failures` are derived from `audit_logs(scope = pilot, action = runtime.provider_telemetry)`
- telemetry rows from a different `trial_provider_profile` are ignored
- an empty `trial_provider_profile` should be treated by operator tooling as a degraded pilot summary signal
