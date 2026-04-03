# 12. MySQL 施工级 Schema 设计

本文件把 `03-data-models.md` 中的领域对象，继续收束成可直接进入 SQLAlchemy / Alembic 的数据库施工方案。

---

## 1. 统一建模约定

### 1.1 数据库版本

默认：

- `MySQL 8.x`

### 1.2 字符集

统一使用：

- `utf8mb4`

### 1.3 主键策略

当前 MVP 统一使用：

- **带前缀的字符串主键**

建议生成方式：

- `prefix + ULID`

示例：

- `shop_01HY9X...`
- `sess_01HY9X...`
- `msg_01HY9X...`

字段类型统一建议：

- `VARCHAR(40)`

### 1.4 时间字段

统一使用：

- `DATETIME(3)`

统一要求：

- 服务端以 UTC 写入
- API 层再根据店铺时区解释展示

### 1.5 数值字段

库存数量统一建议：

- `DECIMAL(12,3)`

价格统一建议：

- `DECIMAL(12,2)`

原因：

- 库存数量后续可能存在半件、半箱、重量单位扩展
- 价格不需要超过两位小数

### 1.6 JSON 字段

以下类型字段建议直接落为 JSON：

- `participants`
- `media_ids`
- `fields`
- `extracted_fields`
- `low_confidence_fields`
- `metadata`

### 1.7 删除策略

当前 MVP 不做全局软删除。

统一策略：

- 业务状态通过 `status`
- 商品启停通过 `is_active`

而不是：

- 所有表都加 `deleted_at`

---

## 2. 物理表设计

### 2.1 `shops`

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| `shop_id` | `VARCHAR(40)` | PK | 店铺 id |
| `name` | `VARCHAR(120)` | NOT NULL | 店铺名 |
| `owner_name` | `VARCHAR(80)` | NOT NULL | 老板名 |
| `industry` | `VARCHAR(32)` | NOT NULL | 业态 |
| `locale` | `VARCHAR(16)` | NOT NULL | 如 `zh-CN` |
| `timezone` | `VARCHAR(64)` | NOT NULL | 如 `Asia/Shanghai` |
| `require_price_confirmation` | `BOOLEAN` | NOT NULL DEFAULT `1` | 是否价格确认 |
| `require_new_item_confirmation` | `BOOLEAN` | NOT NULL DEFAULT `1` | 是否新商品确认 |
| `low_confidence_threshold` | `DECIMAL(5,4)` | NOT NULL DEFAULT `0.8500` | 低置信阈值 |
| `default_low_stock_threshold` | `DECIMAL(12,3)` | NULL | 默认低库存阈值 |
| `created_at` | `DATETIME(3)` | NOT NULL | 创建时间 |
| `updated_at` | `DATETIME(3)` | NOT NULL | 更新时间 |

### 2.2 `sessions`

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| `session_id` | `VARCHAR(40)` | PK | 会话 id |
| `shop_id` | `VARCHAR(40)` | FK -> `shops.shop_id` | 所属店铺 |
| `session_type` | `VARCHAR(32)` | NOT NULL | MVP 固定 `workgroup` |
| `title` | `VARCHAR(120)` | NOT NULL | 会话标题 |
| `participants` | `JSON` | NOT NULL | 当前参与者列表 |
| `last_event_seq` | `BIGINT` | NOT NULL DEFAULT `0` | 当前 session 最新业务事件序号 |
| `last_message_at` | `DATETIME(3)` | NULL | 最近消息时间 |
| `created_at` | `DATETIME(3)` | NOT NULL | 创建时间 |
| `updated_at` | `DATETIME(3)` | NOT NULL | 更新时间 |

### 2.3 `media_uploads`

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| `media_id` | `VARCHAR(40)` | PK | 媒体 id |
| `shop_id` | `VARCHAR(40)` | FK -> `shops.shop_id` | 所属店铺 |
| `uploader_actor_type` | `VARCHAR(16)` | NOT NULL | `owner / agent / system` |
| `uploader_actor_id` | `VARCHAR(40)` | NOT NULL | 上传人 |
| `media_type` | `VARCHAR(24)` | NOT NULL | `audio / image / receipt-image` |
| `file_name` | `VARCHAR(255)` | NOT NULL | 文件名 |
| `content_type` | `VARCHAR(120)` | NOT NULL | MIME |
| `size_bytes` | `BIGINT` | NOT NULL | 文件大小 |
| `storage_bucket` | `VARCHAR(64)` | NOT NULL | MinIO bucket |
| `storage_key` | `VARCHAR(255)` | NOT NULL | 对象路径 |
| `public_url` | `TEXT` | NULL | 可访问 URL |
| `status` | `VARCHAR(24)` | NOT NULL | `pending / uploaded / failed` |
| `checksum_sha256` | `VARCHAR(64)` | NULL | 校验 |
| `created_at` | `DATETIME(3)` | NOT NULL | 创建时间 |
| `uploaded_at` | `DATETIME(3)` | NULL | 上传完成时间 |

### 2.4 `messages`

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| `message_id` | `VARCHAR(40)` | PK | 消息 id |
| `session_id` | `VARCHAR(40)` | FK -> `sessions.session_id` | 会话 id |
| `actor_type` | `VARCHAR(16)` | NOT NULL | `owner / agent / system` |
| `actor_id` | `VARCHAR(40)` | NOT NULL | 发言人 |
| `message_type` | `VARCHAR(32)` | NOT NULL | 消息类型 |
| `text` | `TEXT` | NULL | 文本内容 |
| `media_ids` | `JSON` | NOT NULL | 媒体 id 列表 |
| `client_request_id` | `VARCHAR(64)` | NULL | 客户端幂等键 |
| `task_run_id` | `VARCHAR(40)` | NULL | 软引用，用于加速查询 |
| `created_at` | `DATETIME(3)` | NOT NULL | 创建时间 |

说明：

- `messages.task_run_id` 当前阶段建议作为**软引用字段**
- 不强制加外键，避免与 `task_runs.source_message_id` 形成过强循环依赖
- 当前阶段 owner 发起消息的幂等键唯一约束建议为：
  - `UNIQUE(session_id, actor_type, actor_id, client_request_id)`
- `client_request_id` 允许为空；为空时不参与幂等

### 2.5 `task_runs`

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| `task_run_id` | `VARCHAR(40)` | PK | 任务 id |
| `session_id` | `VARCHAR(40)` | FK -> `sessions.session_id` | 会话 id |
| `source_message_id` | `VARCHAR(40)` | FK -> `messages.message_id` | 来源消息 |
| `task_type` | `VARCHAR(32)` | NOT NULL | 任务类型 |
| `status` | `VARCHAR(32)` | NOT NULL | 任务状态 |
| `assigned_employee_id` | `VARCHAR(40)` | NULL | 当前负责员工 |
| `result_summary` | `TEXT` | NULL | 结果摘要 |
| `error_code` | `VARCHAR(64)` | NULL | 错误码 |
| `error_message` | `VARCHAR(255)` | NULL | 错误说明 |
| `created_at` | `DATETIME(3)` | NOT NULL | 创建时间 |
| `updated_at` | `DATETIME(3)` | NOT NULL | 更新时间 |
| `completed_at` | `DATETIME(3)` | NULL | 完成时间 |

说明：

- 领域模型里的 `confirmation_id` 在物理 schema 中不单独存储
- 当前阶段通过 `confirmations.task_run_id` 反查得到

### 2.6 `inventory_items`

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| `item_id` | `VARCHAR(40)` | PK | 商品 id |
| `shop_id` | `VARCHAR(40)` | FK -> `shops.shop_id` | 所属店铺 |
| `sku` | `VARCHAR(64)` | NULL | SKU |
| `name` | `VARCHAR(160)` | NOT NULL | 商品名 |
| `category` | `VARCHAR(64)` | NULL | 分类 |
| `barcode` | `VARCHAR(64)` | NULL | 条码 |
| `default_unit` | `VARCHAR(24)` | NOT NULL | 默认单位 |
| `current_stock` | `DECIMAL(12,3)` | NOT NULL DEFAULT `0` | 当前库存 |
| `current_price` | `DECIMAL(12,2)` | NULL | 当前价格 |
| `low_stock_threshold` | `DECIMAL(12,3)` | NULL | 低库存阈值 |
| `image_media_id` | `VARCHAR(40)` | NULL | 主图媒体 id |
| `is_active` | `BOOLEAN` | NOT NULL DEFAULT `1` | 是否启用 |
| `created_at` | `DATETIME(3)` | NOT NULL | 创建时间 |
| `updated_at` | `DATETIME(3)` | NOT NULL | 更新时间 |

### 2.7 `inventory_events`

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| `inventory_event_id` | `VARCHAR(40)` | PK | 事件 id |
| `shop_id` | `VARCHAR(40)` | FK -> `shops.shop_id` | 店铺 id |
| `item_id` | `VARCHAR(40)` | FK -> `inventory_items.item_id` | 商品 id |
| `event_type` | `VARCHAR(24)` | NOT NULL | `stock-in / stock-out / correction` |
| `quantity_delta` | `DECIMAL(12,3)` | NOT NULL | 变化值 |
| `quantity_after` | `DECIMAL(12,3)` | NOT NULL | 变化后库存 |
| `unit` | `VARCHAR(24)` | NOT NULL | 单位 |
| `price` | `DECIMAL(12,2)` | NULL | 价格 |
| `source` | `VARCHAR(32)` | NOT NULL | 写入来源 |
| `task_run_id` | `VARCHAR(40)` | NULL | 来源任务 |
| `created_by` | `VARCHAR(40)` | NOT NULL | 创建者 |
| `reason` | `VARCHAR(255)` | NULL | 纠错原因 |
| `created_at` | `DATETIME(3)` | NOT NULL | 创建时间 |

### 2.8 `confirmations`

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| `confirmation_id` | `VARCHAR(40)` | PK | 确认 id |
| `task_run_id` | `VARCHAR(40)` | FK -> `task_runs.task_run_id`, UNIQUE | 对应任务 |
| `confirmation_type` | `VARCHAR(32)` | NOT NULL | 确认类型 |
| `status` | `VARCHAR(16)` | NOT NULL | `pending / approved / rejected` |
| `fields` | `JSON` | NOT NULL | 待确认字段 |
| `resolution_payload` | `JSON` | NULL | 通过或拒绝时的提交内容 |
| `requested_by_employee_id` | `VARCHAR(40)` | NULL | 触发确认的员工 |
| `approved_by_actor_id` | `VARCHAR(40)` | NULL | 审批者 |
| `created_at` | `DATETIME(3)` | NOT NULL | 创建时间 |
| `resolved_at` | `DATETIME(3)` | NULL | 解决时间 |

### 2.9 `ocr_documents`

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| `ocr_document_id` | `VARCHAR(40)` | PK | OCR 文档 id |
| `shop_id` | `VARCHAR(40)` | FK -> `shops.shop_id` | 所属店铺 |
| `task_run_id` | `VARCHAR(40)` | NULL | 来源任务 |
| `media_id` | `VARCHAR(40)` | NOT NULL | 单据图片 |
| `document_type` | `VARCHAR(32)` | NOT NULL | 当前 MVP 为 `purchase-receipt` |
| `status` | `VARCHAR(24)` | NOT NULL | `processing / completed / failed` |
| `provider_name` | `VARCHAR(64)` | NULL | 供应商标识 |
| `raw_text` | `MEDIUMTEXT` | NULL | 调试用原始文本 |
| `extracted_fields` | `JSON` | NULL | 结构化字段 |
| `low_confidence_fields` | `JSON` | NOT NULL | 低置信字段路径列表 |
| `created_at` | `DATETIME(3)` | NOT NULL | 创建时间 |
| `updated_at` | `DATETIME(3)` | NOT NULL | 更新时间 |

### 2.10 `alerts`

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| `alert_id` | `VARCHAR(40)` | PK | 提醒 id |
| `shop_id` | `VARCHAR(40)` | FK -> `shops.shop_id` | 店铺 id |
| `alert_type` | `VARCHAR(24)` | NOT NULL | 当前 MVP 为 `low-stock` |
| `item_id` | `VARCHAR(40)` | FK -> `inventory_items.item_id` | 商品 id |
| `status` | `VARCHAR(16)` | NOT NULL | `open / resolved` |
| `stock` | `DECIMAL(12,3)` | NOT NULL | 当前库存快照 |
| `threshold` | `DECIMAL(12,3)` | NOT NULL | 阈值 |
| `created_at` | `DATETIME(3)` | NOT NULL | 创建时间 |
| `resolved_at` | `DATETIME(3)` | NULL | 解决时间 |

### 2.11 `audit_logs`

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| `audit_log_id` | `VARCHAR(40)` | PK | 审计 id |
| `shop_id` | `VARCHAR(40)` | FK -> `shops.shop_id` | 店铺 id |
| `scope` | `VARCHAR(32)` | NOT NULL | 当前 MVP 为 `inventory` |
| `action` | `VARCHAR(64)` | NOT NULL | 行为名 |
| `actor_type` | `VARCHAR(16)` | NOT NULL | `owner / agent / system` |
| `actor_id` | `VARCHAR(40)` | NOT NULL | 执行者 |
| `task_run_id` | `VARCHAR(40)` | NULL | 来源任务 |
| `target_type` | `VARCHAR(32)` | NULL | 目标对象类型 |
| `target_id` | `VARCHAR(40)` | NULL | 目标对象 id |
| `metadata` | `JSON` | NOT NULL | 结构化附加信息 |
| `created_at` | `DATETIME(3)` | NOT NULL | 创建时间 |

### 2.12 `session_stream_events`

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| `event_id` | `VARCHAR(40)` | PK | 事件 id |
| `session_id` | `VARCHAR(40)` | FK -> `sessions.session_id` | 所属会话 |
| `seq` | `BIGINT` | NOT NULL | 单 session 严格递增序号 |
| `event_type` | `VARCHAR(64)` | NOT NULL | 事件类型 |
| `task_run_id` | `VARCHAR(40)` | NULL | 来源任务 |
| `message_id` | `VARCHAR(40)` | NULL | 来源消息 |
| `payload` | `JSON` | NOT NULL | 结构化事件体 |
| `occurred_at` | `DATETIME(3)` | NOT NULL | 事件发生时间 |

说明：

- 这是**专用 session 事件流表**
- 它不是通用事件总线，也不承担跨域集成职责
- 只用于：
  - WebSocket 顺序发布
  - session 内断档排查
  - 调试与回溯

---

## 3. 关键关系与实现说明

### 3.1 `TaskRun` 与 `Confirmation`

当前 MVP 约定：

- 一个 `TaskRun` 最多只对应一个 `Confirmation`
- 关系主键落在 `confirmations.task_run_id`

原因：

- 可以避免双向冗余和循环维护

### 3.2 `InventoryItem.current_stock`

当前阶段建议：

- 作为投影字段保留在 `inventory_items`
- 每次写 `inventory_events` 时在同一事务内更新

原因：

- 工作台和账本查询更快
- 不必每次运行聚合

### 3.3 `alerts`

当前阶段建议：

- `alerts` 作为派生状态表存在
- 由库存事件写入后同步维护

### 3.4 `messages`

当前阶段建议：

- 结果卡、确认卡、OCR 卡都落成真正消息
- 不额外维护复杂 patch 表

### 3.5 `session_stream_events`

当前阶段建议：

- 所有业务事件先写数据库，再发布 WebSocket
- `seq` 通过 `sessions.last_event_seq` 在事务中递增
- `session.ready` 和 `stream.keepalive` 不落库，不占用新序号

---

## 4. 必要索引

首批迁移至少加上：

- `messages(session_id, created_at desc)`
- `UNIQUE messages(session_id, actor_type, actor_id, client_request_id)`
- `task_runs(session_id, updated_at desc)`
- `task_runs(source_message_id)`
- `inventory_items(shop_id, name)`
- `inventory_items(shop_id, barcode)`
- `inventory_events(shop_id, item_id, created_at desc)`
- `confirmations(status, created_at desc)`
- `alerts(shop_id, status, alert_type)`
- `audit_logs(shop_id, created_at desc)`
- `UNIQUE session_stream_events(session_id, seq)`

---

## 5. Alembic 首批迁移顺序建议

### Migration 001

- `shops`
- `sessions`
- `media_uploads`

### Migration 002

- `messages`
- `task_runs`

### Migration 003

- `inventory_items`
- `inventory_events`

### Migration 004

- `confirmations`
- `ocr_documents`
- `alerts`
- `audit_logs`
- `session_stream_events`

---

## 6. 当前阶段明确不做的 schema 复杂度

- 多租户隔离表
- 通用事件总线表
- 复杂软删除体系
- 分库分表
- 向量数据库耦合字段
- 通用插件注册表

本文件的目标不是追求未来十年的极致扩展性，而是：

**把当前 MVP 的消息、任务、确认、库存和审计，稳定落成第一版关系型业务骨架。**
