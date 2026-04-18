# AI 原生 SaaS 后端重构设计

## 背景

后端正式采用方案 C：重写核心架构。

该决策已在 2026-04-18 确认，并以原则文档形式固化在：

`docs/architecture/ai-native-saas-architecture-principles.md`

当前后端并非完全不可用，但它的基础边界与目标产品模型不一致，主要问题包括：

- `shop` 实际上承担了租户边界
- 登录态直接绑定单个 `shop_id`
- 认证上下文只有 `actor_id + shop_id + role`
- 认证流程中仍混入默认店铺和默认 owner bootstrap
- 多个服务依赖“先按主键取对象，再回溯推导上下文”的模式

而目标产品的真实模型是：

- 这是一个多租户 SaaS 平台
- `tenant` 是商家组织
- 一个 `tenant` 下可以有多个 `shop`
- 一个 `account` 可以加入多个 `tenant`
- 用户登录后需要显式切换当前 `tenant / shop`
- 多模态 AI 是主交互入口与任务编排核心
- 确定性后端工具才是业务真相的唯一写入者

## 目标

在开始实现之前，先为新后端确定一套干净、稳定、可扩展的架构蓝图。

这份设计的目标不是指导“如何补旧系统”，而是定义：

- 新后端应该有哪些领域边界
- 新数据模型应该如何表达租户、门店、上下文和业务真相
- AI runtime 应该如何成为第一入口而不是外挂能力
- 异步、实时、审计和可观测性应该如何围绕新模型搭建
- 旧系统中哪些能力可以复用，哪些必须废弃，哪些必须重写

设计接受后，应形成这些约束：

- 新架构默认走 `/api/v2`
- 新的后端工作默认不再扩展错误的旧边界
- 旧 `/api/v1` 只作为参考和迁移来源
- 后续实现以该设计和原则文档为准

## 方案对比

### 方案 A：原地修补旧架构

交付方式：

- 增加 `tenant` 表
- 给旧表补 `tenant_id`
- 保留旧登录和会话模型，逐步加上下文切换

优点：

- 代码改动最小
- 可以较快得到短期演示

缺点：

- 继续保留错误语义
- `shop = tenant` 的历史包袱会长期存在
- 权限与上下文会越来越难以推理
- 未来 AI runtime 与多租户边界容易持续冲突

不采用原因：

- 错误边界已经深入 auth、session、service、数据模型，不适合继续打补丁

### 方案 B：在现有结构上做领域化重构

交付方式：

- 重新整理模块
- 新接口逐步带上 tenant 上下文
- 一条服务线一条服务线迁移

优点：

- 比全面重写风险低
- 迁移更平滑

缺点：

- 仍然需要在错误模型上做兼容
- 架构容易长期处于“半新半旧”状态
- 旧概念会不断反向污染新实现

不采用原因：

- 当前业务尚未深度生产化，现在重建基础成本更低

### 方案 C：重写核心架构

交付方式：

- 新领域模型
- 新 `/api/v2`
- 新认证与上下文选择流
- 新 AI runtime 流程
- 新库存账本模型
- 新异步与实时基础设施

优点：

- 与真实产品模型一致
- 避免错误语义遗留
- 能让 AI 原生、多租户、人机共驾成为一等能力
- 为未来 SaaS 扩展打下干净基础

缺点：

- 设计和实现成本更高
- 必须严格规划迁移路径

最终选择：

采用方案 C。

## 总体架构形态

新后端采用：

**模块化单体 + 明确领域边界 + outbox 可靠异步 + 事件驱动投影**

当前阶段不建议一开始就做微服务，原因是：

- 领域模型还在重建
- 先保证边界正确，比先拆服务更重要
- 一个可部署后端更利于快速验证
- 后续如果业务规模扩大，再按领域边界拆服务更自然

## 领域划分

后端建议划分为以下 8 个核心域。

### 1. identity_access

职责：

- 账号身份
- 登录会话
- 密码与 token 生命周期
- 租户成员关系
- 门店访问范围
- 角色与权限计算

拥有：

- `account`
- `auth_session`
- `tenant_membership`
- `shop_access`
- role / permission 规则

不拥有：

- 租户商业信息
- 门店业务配置
- 会话与任务
- 库存真相

### 2. tenant_shop

职责：

- 租户创建与生命周期
- 门店创建与生命周期
- tenant 级配置
- shop 级配置

拥有：

- `tenant`
- `shop`
- tenant 配置
- shop 配置

### 3. workspace_context

职责：

- 当前租户 / 门店上下文选择
- context session 创建
- 权限快照生成
- 上下文 token 校验

拥有：

- `context_session`
- context 校验逻辑

### 4. conversation_runtime

职责：

- 会话
- 消息
- 任务流
- 追问
- 确认
- 任务状态机
- runtime 编排

拥有：

- `conversation_session`
- `message`
- `task_run`
- `confirmation`
- runtime 流程引擎

### 5. inventory_ledger

职责：

- tenant 级商品档案
- shop 级库存账本
- 库存投影
- 入库、出库、纠错工具

拥有：

- `inventory_item`
- `inventory_stock_snapshot`
- `inventory_ledger_event`

### 6. media_ai_platform

职责：

- 媒体资产
- 文档抽取
- ASR / OCR / Vision / LLM / Retrieval / Evaluation
- 模型调用记录
- prompt / schema 版本治理

拥有：

- `media_asset`
- `document`
- `model_call_log`
- provider 抽象层

### 7. audit_governance

职责：

- 审计记录
- 风险策略
- 可解释性输出
- 治理报表

拥有：

- `audit_log`
- risk policy

### 8. async_realtime

职责：

- outbox
- worker 派发
- projection 更新
- websocket / push 分发
- replay / catch-up

拥有：

- `outbox_event`
- 异步执行与投影基础设施

## 核心数据模型

### account

用途：

平台级自然人登录身份。

关键字段：

- `account_id`
- `email`
- `display_name`
- `password_hash`
- `status`
- `created_at`
- `updated_at`

归属原则：

- 平台级
- 不属于任何 tenant

### tenant

用途：

商家组织，是第一业务边界。

关键字段：

- `tenant_id`
- `name`
- `slug`
- `status`
- `plan_code`
- `owner_account_id`
- `created_at`
- `updated_at`

### shop

用途：

租户下的门店或经营单元。

关键字段：

- `shop_id`
- `tenant_id`
- `code`
- `name`
- `locale`
- `timezone`
- `status`
- `created_at`
- `updated_at`

约束：

- `shop` 永远属于一个 `tenant`
- `shop` 不再表达租户边界

### tenant_membership

用途：

账号在某个租户中的成员关系。

关键字段：

- `membership_id`
- `tenant_id`
- `account_id`
- `role_key`
- `status`
- `joined_at`
- `updated_at`

### shop_access

用途：

租户成员可访问的门店范围。

关键字段：

- `shop_access_id`
- `tenant_id`
- `shop_id`
- `membership_id`
- `access_level`
- `status`
- `created_at`

约束：

- `shop_access.tenant_id` 必须与 `shop.tenant_id` 一致

### auth_session

用途：

账号登录态。

关键字段：

- `auth_session_id`
- `account_id`
- `refresh_token_hash`
- `status`
- `expires_at`
- `revoked_at`
- `last_seen_at`
- `created_at`

约束：

- 只绑定账号，不绑定 tenant 和 shop

### context_session

用途：

当前工作上下文。

关键字段：

- `context_session_id`
- `auth_session_id`
- `account_id`
- `tenant_id`
- `shop_id`
- `membership_id`
- `permission_snapshot`
- `expires_at`
- `created_at`

约束：

- 这是“当前租户 / 门店工作态”
- 业务接口依赖它，而不是直接依赖 auth_session

### conversation_session

用途：

业务上下文容器，而不是普通聊天记录。

关键字段：

- `session_id`
- `tenant_id`
- `shop_id`
- `session_type`
- `title`
- `status`
- `initiated_by_account_id`
- `created_at`
- `updated_at`

### message

用途：

会话中的用户、AI、系统、工具消息。

关键字段：

- `message_id`
- `tenant_id`
- `shop_id`
- `session_id`
- `actor_type`
- `actor_id`
- `message_kind`
- `payload_json`
- `client_request_id`
- `created_at`

### task_run

用途：

一次 AI 驱动业务任务的运行状态。

关键字段：

- `task_run_id`
- `tenant_id`
- `shop_id`
- `session_id`
- `source_message_id`
- `intent_type`
- `status`
- `risk_level`
- `trace_id`
- `result_summary`
- `error_code`
- `created_at`
- `updated_at`
- `completed_at`

### confirmation

用途：

高风险或低置信度写操作的人机确认边界。

关键字段：

- `confirmation_id`
- `tenant_id`
- `shop_id`
- `task_run_id`
- `confirmation_type`
- `status`
- `draft_payload`
- `approved_by_account_id`
- `resolution_payload`
- `created_at`
- `resolved_at`

约束：

- 不能只靠 `task_run_id` 间接回溯租户边界

### inventory_item

用途：

tenant 级商品档案。

关键字段：

- `inventory_item_id`
- `tenant_id`
- `sku`
- `name`
- `barcode`
- `default_unit`
- `status`
- `created_at`
- `updated_at`

关键决策：

- 商品档案默认提升到 tenant 级
- 同一商家租户下多个门店默认共享商品身份

### inventory_stock_snapshot

用途：

门店当前库存投影。

关键字段：

- `snapshot_id`
- `tenant_id`
- `shop_id`
- `inventory_item_id`
- `current_quantity`
- `current_price`
- `low_stock_threshold`
- `updated_at`

### inventory_ledger_event

用途：

库存变化的不可变业务事实。

关键字段：

- `event_id`
- `tenant_id`
- `shop_id`
- `inventory_item_id`
- `event_type`
- `quantity_delta`
- `quantity_after`
- `unit`
- `price`
- `source_type`
- `source_id`
- `reason`
- `created_by_account_id`
- `occurred_at`

### media_asset

用途：

租户拥有的媒体资产。

关键字段：

- `media_asset_id`
- `tenant_id`
- `shop_id`
- `uploaded_by_account_id`
- `media_type`
- `content_type`
- `storage_key`
- `sha256`
- `status`
- `created_at`

### document

用途：

从媒体中抽取出的结构化文档结果。

关键字段：

- `document_id`
- `tenant_id`
- `shop_id`
- `media_asset_id`
- `document_type`
- `extraction_status`
- `extracted_fields`
- `confidence_summary`
- `created_at`
- `updated_at`

### model_call_log

用途：

AI 调用可观测记录。

关键字段：

- `model_call_id`
- `tenant_id`
- `shop_id`
- `task_run_id`
- `capability`
- `provider`
- `model`
- `prompt_version`
- `schema_version`
- `latency_ms`
- `cost`
- `confidence`
- `used_fallback`
- `error_code`
- `created_at`

### audit_log

用途：

关键动作可解释审计记录。

关键字段：

- `audit_log_id`
- `tenant_id`
- `shop_id`
- `actor_id`
- `session_id`
- `task_run_id`
- `action`
- `target_type`
- `target_id`
- `metadata_json`
- `created_at`

### outbox_event

用途：

可靠异步投递记录。

关键字段：

- `outbox_event_id`
- `tenant_id`
- `shop_id`
- `aggregate_type`
- `aggregate_id`
- `event_type`
- `payload_json`
- `status`
- `attempt_count`
- `available_at`
- `created_at`

## 认证与授权

认证与上下文选择必须拆开。

### 登录流程

1. `POST /api/v2/auth/login`
2. 校验账号凭证
3. 创建 `auth_session`
4. 返回账号登录态
5. 不直接绑定 tenant 或 shop

### 租户与门店选择流程

1. `GET /api/v2/me/tenants`
2. 用户选择 tenant
3. `GET /api/v2/tenants/{tenant_id}/shops`
4. 用户选择 shop
5. `POST /api/v2/context/select`
6. 系统验证 membership 和 shop access
7. 创建 `context_session`
8. 后续业务接口使用 context token 或 context session

### 权限模型

权限裁决由以下几层共同决定：

- tenant membership
- shop access
- role-based permission
- risk policy
- 具体动作校验

原则：

- AI 不能绕过权限系统
- 工具执行前必须完成权限与风险检查

## 执行上下文

每个业务动作至少需要这些上下文字段：

```text
account_id
tenant_id
shop_id
membership_id
role_key
permissions
context_session_id
session_id
input_channel
locale
timezone
trace_id
```

规则：

- service 方法应优先接收上下文对象
- 查询必须按 `tenant_id` 限定
- shop 级动作必须同时按 `shop_id` 限定
- AI 解释、确认、工具执行、账本提交都不能跳过上下文

## AI Runtime 设计

runtime 的标准流水线应为：

```text
capture
interpret
assess
clarify
draft
confirm
execute
commit
correct
```

### capture

落库：

- text
- audio
- image
- receipt
- document

输出：

- `message`
- 可选 `media_asset`
- 可选 `document`
- 初始 `task_run`

### interpret

多模态 AI 生成结构化候选结果：

- intent
- extracted fields
- confidence
- ambiguity
- missing fields
- possible tool call

输出：

- 结构化解释结果
- `model_call_log`

### assess

系统评估：

- 置信度
- 缺失字段
- 风险等级
- 当前权限
- tenant policy
- shop policy

可能结果：

- 直接回答
- 发起追问
- 生成草稿
- 要求确认
- 拒绝
- 失败

### clarify

若信息缺失或歧义，系统发起定向追问，而不是直接失败。

### draft

生成结构化业务草稿，但不直接写入业务真相。

### confirm

对写操作、中高风险操作、低置信度操作创建 `confirmation`。

### execute

由确定性工具执行实际业务动作。

### commit

提交：

- 账本事件
- 当前状态投影
- 审计日志
- outbox 事件
- 系统结果消息

### correct

若发现错误，通过 correction event 追加修正，不覆盖历史。

## 任务状态机

建议 `task_run.status` 包括：

- `captured`
- `interpreting`
- `needs_clarification`
- `drafted`
- `awaiting_confirmation`
- `executing`
- `committed`
- `rejected`
- `failed`
- `corrected`

规则：

- 写操作未通过工具执行前不得进入 `committed`
- 拒绝必须显式
- 纠错必须尽量链接原始事件或原始任务

## 工具边界

初始工具族建议：

- `inventory.query`
- `inventory.stock_in.create_draft`
- `inventory.stock_in.commit`
- `inventory.stock_out.create_draft`
- `inventory.stock_out.commit`
- `inventory.correction.commit`
- `catalog.item.match`
- `catalog.item.create`
- `document.receipt.extract`
- `session.message.append_system_result`

每个工具都必须定义：

- tool name
- input schema
- output schema
- required context
- required permissions
- risk level
- idempotency key
- audit behavior
- mutation behavior
- error codes

## API 分层

新后端默认走 `/api/v2`。

### Public Auth

- `POST /api/v2/auth/login`
- `POST /api/v2/auth/logout`
- `POST /api/v2/auth/refresh`

### Identity / Context

- `GET /api/v2/me`
- `GET /api/v2/me/tenants`
- `GET /api/v2/tenants/{tenant_id}/shops`
- `POST /api/v2/context/select`
- `GET /api/v2/context/current`

### Conversation Runtime

- `POST /api/v2/sessions`
- `GET /api/v2/sessions`
- `POST /api/v2/sessions/{session_id}/messages`
- `GET /api/v2/sessions/{session_id}/messages`
- `GET /api/v2/task-runs/{task_run_id}`
- `GET /api/v2/confirmations`
- `POST /api/v2/confirmations/{confirmation_id}/approve`
- `POST /api/v2/confirmations/{confirmation_id}/reject`

### Media / Document

- `POST /api/v2/media-assets`
- `POST /api/v2/media-assets/{media_asset_id}/complete`
- `POST /api/v2/documents`
- `GET /api/v2/documents/{document_id}`

### Operations

- `GET /api/v2/inventory/items`
- `GET /api/v2/inventory/stock`
- `GET /api/v2/inventory/events`
- `POST /api/v2/inventory/corrections`
- `GET /api/v2/dashboard/summary`
- `GET /api/v2/alerts`

### Admin / Internal

- `GET /api/v2/internal/provider-health`
- `GET /api/v2/internal/worker-health`
- `POST /api/v2/internal/projections/replay`
- `GET /api/v2/internal/model-calls`

## 异步与实时

重要异步链路必须基于 outbox。

写事务的正确顺序：

1. 写入业务对象或任务状态
2. 写入 `outbox_event`
3. 提交事务

后台执行顺序：

1. dispatcher 读取 outbox
2. worker 执行任务
3. 写入结果、审计、投影和后续 outbox
4. notification worker 推送实时更新

实时原则：

- 数据库事件是真相
- websocket 是投影分发
- 客户端必须支持 replay / catch-up
- 多实例 fanout 使用 Redis pub/sub 或消息总线
- 不再依赖单进程内存态连接管理作为唯一状态源

## 可观测与 AI 评估

系统至少应持续记录：

- intent accuracy
- extraction accuracy
- clarification rate
- confirmation approval rate
- confirmation rejection rate
- correction rate
- low-confidence rate
- provider latency
- provider cost
- fallback rate
- task failure rate
- prompt version performance
- schema version performance

原则：

- 无法评估的 AI 能力，不应成为核心竞争力

## 迁移路线

### 阶段 0：原则冻结

状态：

- 已完成

产出：

- `docs/architecture/ai-native-saas-architecture-principles.md`

### 阶段 1：新 v2 骨架

建设：

- 新模块布局
- `/api/v2`
- 共享响应模型
- 执行上下文基础设施
- 新测试基线

### 阶段 2：Identity / Tenant / Shop / Context

建设：

- `account`
- `tenant`
- `shop`
- `tenant_membership`
- `shop_access`
- `auth_session`
- `context_session`
- 登录、列出 tenant、列出 shop、上下文选择

### 阶段 3：Conversation / Runtime Skeleton

建设：

- `conversation_session`
- `message`
- `task_run`
- clarification
- confirmation
- runtime 状态机骨架

### 阶段 4：Inventory Ledger V2

建设：

- tenant 级商品档案
- shop 级库存投影
- 库存事件账本
- 入库、出库、纠错工具

### 阶段 5：Media / AI Platform

建设：

- `media_asset`
- `document`
- ASR / OCR / Vision / LLM / Retrieval
- `model_call_log`
- prompt / schema version 管理

### 阶段 6：Outbox / Worker / Projection / Realtime

建设：

- `outbox_event`
- dispatcher worker
- runtime worker
- projection worker
- notification worker
- websocket replay

### 阶段 7：场景迁移

迁移这些核心业务场景：

- voice stock query
- voice stock in
- photo stock query
- photo stock in
- receipt OCR stock in
- manual correction
- audit browsing
- low-stock alerts

### 阶段 8：v1 退场

移除或隔离：

- auth 中的 default shop bootstrap
- auth 中的 default owner bootstrap
- `shop = tenant` 假设
- 旧 session stream 单例式假设

## 复用、重写、废弃

### 可复用的经验

- 库存事件账本思想
- confirmation 工作流经验
- task-run 生命周期经验
- provider gateway 抽象经验
- 现有验收场景

### 必须重写

- identity 和 access
- tenant / shop 模型
- context 选择
- conversation session 模型
- runtime pipeline
- inventory 模型
- outbox 与异步投递
- AI 可观测能力

### 必须废弃

- `shop` 作为租户边界
- 登录直接绑定单个 shop
- 默认 shop / owner auth bootstrap
- 主键直取后再回溯上下文
- 仅靠进程内存做实时分发

## 测试策略

测试应围绕新行为，而不是旧实现细节。

初始验收测试建议覆盖：

- 一个 account 能加入两个 tenant
- 一个 tenant 能拥有两个 shop
- context selection 拒绝无权访问的 shop
- 无上下文时业务接口拒绝执行
- AI task 能进入 `needs_clarification`
- AI task 能进入 `awaiting_confirmation`
- 入库确认后写入 ledger event、stock projection、audit log、outbox event
- 拒绝确认不会修改库存
- correction 通过追加事件修复
- model call 会记录 provider 与 schema 元数据
- 跨租户对象访问被拒绝

## 非目标

本设计当前不包含：

- UI 重写
- billing
- plugin marketplace
- 初期多服务部署
- 完整财务系统
- 自动供应商下单
- 全量旧数据迁移工具

这些能力应在核心 AI 原生 SaaS 后端稳定后再进入规划。

## 开放决策

以下问题可以留到 implementation planning 阶段决定：

- context session 的具体 token 形式
- 权限 key 的精确命名
- role preset 的具体集合
- 首版 outbox 使用 Redis 还是数据库轮询
- v2 首版是否只支持 MySQL，还是继续兼容 SQLite 测试
- prompt registry 的最终存储模型

这些开放项不会改变当前架构方向。

## 设计验收标准

当以下条件成立时，这份设计视为通过：

- tenant 成为一等边界
- shop 仅作为 tenant 下业务单元
- account 能加入多个 tenant
- 上下文切换是显式行为
- AI 是主交互入口与编排核心
- AI 不能直接修改业务真相
- 不确定性、追问、确认、纠错、审计是基础能力
- 库存真相采用事件账本表达
- 异步链路基于可靠 outbox
- 实时更新是已提交事实的投影
- 旧系统被视为参考，而不是新架构的约束

