# 10. Runtime 合同与执行状态机

本文件把 `07` 和 `08` 里的 AI 原生控制平面思路，继续压到“可编码”的施工层。

它回答的问题是：

- 员工到底在代码里是什么
- 工具如何声明
- 守门规则如何执行
- 任务状态如何流转

---

## 1. MVP runtime 的默认形态

当前 MVP 的 runtime 统一按下面原则实现：

- 对外只暴露 `小雅` 和 `老李`
- 对内默认拆成：
  - `Router`
  - `PolicyGuard`
  - `ToolRunner`
  - `Summarizer`
  - `Reviewer`（只在高风险场景启用）
- 不做开放式多智能体自由协作
- 不允许模型直接触碰数据库
- 所有业务写入都必须通过受控 tool 完成

当前阶段的核心结论是：

**MVP 不是“多开几个 agent”，而是“一个受控 orchestrator loop + 一组结构化合同”。**

---

## 2. 核心合同

### 2.1 EmployeeProfile

```ts
type EmployeeProfile = {
  employee_id: string
  visible_name: string
  role: string
  visible_to_user: boolean
  domain_scope: string[]
  skill_ids: string[]
  tool_ids: string[]
  disallowed_actions: string[]
  confirmation_rules: string[]
  handoff_targets: string[]
  memory_scope: "session" | "shop" | "task"
}
```

实现要求：

- 员工配置必须结构化存放
- 不允许把完整角色边界只写在 prompt 文案里
- `tool_ids` 是白名单，而不是提示建议

### 2.2 ToolSpec

```ts
type ToolSpec = {
  tool_id: string
  name: string
  description: string
  risk_level: "read_only" | "needs_confirmation" | "committable" | "forbidden"
  input_schema_id: string
  output_schema_id: string
  writes_audit_log: boolean
  requires_confirmation: boolean
  allowed_roles: string[]
}
```

实现要求：

- 每个 tool 都必须有输入输出边界
- 每个 tool 都必须有风险等级
- `committable` tool 不允许绕过 `PolicyGuard`

### 2.3 PolicyRule

```ts
type PolicyRule = {
  rule_id: string
  name: string
  applies_to_task_types: string[]
  when: string
  outcome: "allow" | "require-confirmation" | "block" | "escalate-review"
  reason_code: string
}
```

实现要求：

- 规则必须显式可枚举
- 不允许把所有守门逻辑写死在分支判断里而没有规则名
- 每次被触发的规则都应可写入审计或 debug 日志

### 2.4 RuntimeTurnContext

```ts
type RuntimeTurnContext = {
  shop_id: string
  session_id: string
  source_message_id: string
  task_run_id: string
  input_kind: "voice" | "image" | "receipt-image" | "manual-correction"
  locale: string
  timezone: string
  shop_rules: Record<string, unknown>
  recent_messages: Array<Record<string, unknown>>
  pending_confirmation_id: string | null
}
```

实现要求：

- Runtime 永远只消费结构化上下文
- Provider 和 tool 不直接自己查散落上下文

---

## 3. MVP 员工与内部角色分工

### 3.1 用户可见员工

#### 小雅

职责：

- 接收老板输入
- 判断任务类型
- 组织回执
- 需要时转交老李
- 触发确认卡

禁止：

- 直接写库存
- 跳过确认链
- 自行宣布账本真相

#### 老李

职责：

- 处理库存域任务
- 组织库存结果
- 执行确认后的入库
- 生成低库存相关回执

禁止：

- 自由接管所有对话
- 做经营分析扩写
- 对低置信识别直接落账

### 3.2 系统内部角色

#### Router

负责：

- 从输入判断 `task_type`
- 决定是否需要多步执行

#### PolicyGuard

负责：

- 判断是否允许继续
- 判断是否必须确认
- 判断是否需要 Reviewer

#### ToolRunner

负责：

- 执行 provider 调用
- 执行库存查询与写入
- 执行审计记录

#### Summarizer

负责：

- 生成任务摘要
- 对长会话压缩出可恢复摘要

#### Reviewer

负责：

- 在高风险写入前做最终拦截

---

## 4. MVP 工具目录

当前阶段最小工具集建议固定为：

| tool_id | 用途 | risk_level | 允许角色 |
|---|---|---|---|
| `transcribe_audio` | 把语音转成文本 | `read_only` | `xiaoya`, `router`, `tool_runner` |
| `recognize_product` | 识别商品候选 | `read_only` | `xiaoya`, `laoli`, `tool_runner` |
| `extract_receipt_fields` | 提取进货单字段 | `read_only` | `xiaoya`, `laoli`, `tool_runner` |
| `query_inventory` | 查询库存和商品详情 | `read_only` | `xiaoya`, `laoli`, `tool_runner` |
| `create_confirmation` | 创建确认卡 | `needs_confirmation` | `xiaoya`, `tool_runner` |
| `append_inventory_event` | 写库存事件 | `committable` | `laoli`, `tool_runner` |
| `create_correction_event` | 写人工纠错事件 | `committable` | `laoli`, `tool_runner` |
| `write_audit_log` | 追加审计记录 | `committable` | `tool_runner` |
| `push_session_update` | 向 WebSocket 推送事件 | `read_only` | `tool_runner`, `summarizer` |

约束：

- `append_inventory_event`
- `create_correction_event`
- `write_audit_log`

这三个工具必须由服务端受控代码实现，不允许由 LLM 直接拼 SQL 或拼 ORM 调用。

---

## 5. 路由合同

### 5.1 输入到任务类型的映射

| 输入类型 | 路由结果 |
|---|---|
| `voice` 且语义为入库 | `voice-stock-in` |
| `voice` 且语义为查询 | `voice-stock-query` |
| `image` 且为商品建档 / 入库 | `photo-stock-in` |
| `image` 且为库存查询 | `photo-stock-query` |
| `receipt-image` | `receipt-ocr` |
| ledger 纠错表单提交 | `manual-correction` |

### 5.2 信息不足时的处理

当前 MVP **不新增** `awaiting-user-input` 这种 TaskRun 状态。

统一处理方式：

- 当前任务返回一条澄清型结果卡
- 引导用户补图、补数量或补价格
- 用户下一次输入视为新的 `source_message_id` 和新的 `TaskRun`

这样做的好处是：

- 当前状态机更简单
- 前端消息渲染更稳定

---

## 6. PolicyGuard 规则矩阵

当前阶段最少实现下面这些规则：

| 规则名 | 条件 | 结果 |
|---|---|---|
| `new_item_requires_confirmation` | 识别结果不存在现有商品档案 | `require-confirmation` |
| `low_confidence_requires_confirmation` | 识别或 OCR 置信度低于店铺阈值 | `require-confirmation` |
| `missing_price_requires_confirmation` | 入库任务缺价格且店铺要求价格确认 | `require-confirmation` |
| `manual_correction_requires_reason` | 人工纠错未填写原因 | `block` |
| `inventory_write_requires_task_run` | 写库存时没有 `task_run_id` | `block` |
| `very_low_confidence_escalates_review` | 识别置信度低于 `0.60` | `escalate-review` |
| `ocr_many_uncertain_fields_escalates_review` | OCR 关键低置信字段超过 2 个 | `escalate-review` |

补充说明：

- 一般低置信阈值沿用 `StoreRuleProfile.low_confidence_threshold`
- 当前默认阈值建议为 `0.85`
- `Reviewer` 只处理 `escalate-review`，不替代确认链

---

## 7. TaskRun 状态机

### 7.1 状态定义

沿用 `03-data-models.md` 中的状态：

- `created`
- `processing`
- `awaiting-confirmation`
- `completed`
- `rejected`
- `failed`

### 7.2 允许的迁移

| 当前状态 | 下一个状态 | 触发条件 |
|---|---|---|
| `created` | `processing` | runtime 开始处理 |
| `processing` | `awaiting-confirmation` | PolicyGuard 触发确认 |
| `processing` | `completed` | 只读任务完成或低风险写入完成 |
| `processing` | `failed` | provider 失败、校验失败、系统异常 |
| `awaiting-confirmation` | `completed` | 用户确认后写入成功 |
| `awaiting-confirmation` | `rejected` | 用户拒绝确认 |
| `awaiting-confirmation` | `failed` | 确认后提交失败或冲突 |

### 7.3 当前阶段的实现约束

- 一个 `TaskRun` 在 MVP 中最多只挂一个待处理 `Confirmation`
- `Confirmation` 是显式对象，不嵌在消息文本里
- `TaskRun` 结束后必须写 `result_summary` 或 `error_code`

---

## 8. Handoff 合同

当前 MVP 的 handoff 必须显式发生，不能靠自然语言“顺便转一下”。

最小结构建议：

```ts
type HandoffDecision = {
  from_employee_id: string
  to_employee_id: string
  reason: string
  task_run_id: string
}
```

当前只允许：

- `小雅 -> 老李`

当前不允许：

- `老李 -> 小雅` 之外的多跳协作
- 任意子代理自行再拉起新代理

---

## 9. Summarizer 触发条件

当前阶段 Summarizer 不做复杂长上下文系统，只要满足下面两个触发条件即可：

- 单个 `TaskRun` 完成时生成 `result_summary`
- 单个 session 消息数超过 `100` 时生成 session summary

总结内容至少包含：

- 当前任务类型
- 当前结果
- 是否写入库存
- 是否产生确认
- 最近一次库存事件

---

## 10. 当前阶段明确不做的 runtime 复杂度

- 自由子代理树
- 插件型工具自动发现
- 任意角色调用任意工具
- 长链路自动反思重试
- 无约束 LLM 直接生成数据库写入参数

本文件的落点是：

**先把 runtime 做成“规则明确、状态可追、工具受控”的业务 orchestrator，而不是追求炫技式 agent 感。**
