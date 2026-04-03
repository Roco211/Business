# 03. 数据模型

## 1. 目标

这份文档定义首版必须落地的数据对象，避免客户端、服务端、模型编排对同一个概念理解不一致。

## 2. 核心对象

### 2.1 ShopProfile

```ts
type ShopProfile = {
  shop_id: string
  name: string
  owner_name: string
  industry: "grocery" | "convenience" | "hardware" | "general"
  locale: string
  timezone: string
  rules: StoreRuleProfile
}
```

### 2.2 StoreRuleProfile

```ts
type StoreRuleProfile = {
  require_price_confirmation: boolean
  require_new_item_confirmation: boolean
  low_confidence_threshold: number
  low_stock_strategy: {
    default_threshold_enabled: boolean
  }
}
```

### 2.3 ConversationSession

```ts
type ConversationSession = {
  session_id: string
  shop_id: string
  session_type: "workgroup"
  title: string
  participants: string[]
  last_message_at: string
}
```

### 2.4 SessionMessage

```ts
type SessionMessage = {
  message_id: string
  session_id: string
  actor_type: "owner" | "agent" | "system"
  actor_id: string
  message_type: "text" | "voice" | "image" | "receipt-image" | "result-card" | "confirmation-card"
  text: string | null
  media_ids: string[]
  task_run_id: string | null
  created_at: string
}
```

### 2.5 TaskRun

```ts
type TaskRun = {
  task_run_id: string
  session_id: string
  task_type:
    | "voice-stock-in"
    | "voice-stock-query"
    | "photo-stock-in"
    | "photo-stock-query"
    | "receipt-ocr"
    | "manual-correction"
  status:
    | "created"
    | "processing"
    | "awaiting-confirmation"
    | "completed"
    | "rejected"
    | "failed"
  source_message_id: string
  confirmation_id: string | null
  result_summary: string | null
  created_at: string
  updated_at: string
}
```

### 2.6 InventoryItem

```ts
type InventoryItem = {
  item_id: string
  shop_id: string
  sku: string | null
  name: string
  category: string | null
  barcode: string | null
  default_unit: string
  current_stock: number
  current_price: number | null
  low_stock_threshold: number | null
  image_url: string | null
  is_active: boolean
  created_at: string
  updated_at: string
}
```

### 2.7 InventoryEvent

```ts
type InventoryEvent = {
  inventory_event_id: string
  shop_id: string
  item_id: string
  event_type: "stock-in" | "stock-out" | "correction"
  quantity_delta: number
  quantity_after: number
  unit: string
  price: number | null
  source:
    | "voice-confirmed"
    | "photo-confirmed"
    | "receipt-confirmed"
    | "manual-correction"
  task_run_id: string | null
  created_by: string
  created_at: string
}
```

### 2.8 Confirmation

```ts
type Confirmation = {
  confirmation_id: string
  task_run_id: string
  confirmation_type:
    | "new-item"
    | "low-confidence-recognition"
    | "missing-price"
    | "quantity-review"
    | "ocr-field-review"
  status: "pending" | "approved" | "rejected"
  fields: Record<string, unknown>
  created_at: string
  resolved_at: string | null
}
```

### 2.9 OcrDocument

```ts
type OcrDocument = {
  ocr_document_id: string
  shop_id: string
  media_id: string
  document_type: "purchase-receipt"
  status: "processing" | "completed" | "failed"
  extracted_fields: Record<string, unknown> | null
  low_confidence_fields: string[]
  created_at: string
}
```

### 2.10 Alert

```ts
type Alert = {
  alert_id: string
  shop_id: string
  alert_type: "low-stock"
  item_id: string
  status: "open" | "resolved"
  stock: number
  threshold: number
  created_at: string
}
```

### 2.11 AuditLog

```ts
type AuditLog = {
  audit_log_id: string
  shop_id: string
  scope: "inventory"
  action: string
  actor_type: "owner" | "agent" | "system"
  actor_id: string
  task_run_id: string | null
  metadata: Record<string, unknown>
  created_at: string
}
```

## 3. 服务端存储建议

首版建议使用关系型数据库即可，例如：

- `shops`
- `sessions`
- `messages`
- `media_uploads`
- `task_runs`
- `inventory_items`
- `inventory_events`
- `confirmations`
- `ocr_documents`
- `alerts`
- `audit_logs`

原因：

- 库存和审计更适合结构化查询
- 写操作和确认链需要明确事务边界
- 首版不需要为了灵活性过早引入事件总线型复杂存储

## 4. 客户端本地数据建议

React Native 端建议只保留轻量本地缓存：

- 当前用户信息
- 当前店铺信息
- 最近会话消息缓存
- 最近库存列表缓存
- 上传中的媒体草稿
- 最近一次 OCR 结果缓存

不建议首版本地持久化：

- 库存真相数据
- 待确认最终状态
- 审计真相数据

## 5. 关键索引建议

- `messages(session_id, created_at desc)`
- `task_runs(session_id, updated_at desc)`
- `inventory_items(shop_id, name)`
- `inventory_events(shop_id, item_id, created_at desc)`
- `alerts(shop_id, status, alert_type)`
- `audit_logs(shop_id, created_at desc)`

## 6. 数据一致性原则

- `InventoryItem.current_stock` 来自 `InventoryEvent` 汇总结果
- `Correction` 不是覆盖，而是追加一条 `correction` 事件
- `Confirmation` 一旦通过，必须绑定对应 `TaskRun`
- OCR 结果不直接写库存，必须转成确认链

