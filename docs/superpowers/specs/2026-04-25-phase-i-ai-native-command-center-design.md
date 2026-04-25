# Phase I：AI-native Command Center 与 AI任务流设计

日期：2026-04-25
项目：Business AI 五金店大管家
分支：hermes/ai-native-saas-rewrite

## 1. 背景与问题

当前 Business 已经完成多租户后端、真实销售/采购/客户/财务闭环、H5 商业页面、关键审计、CSV 导出、错误日志、Docker 部署与 dashboard.jpg 风格 UI 对齐。

但当前用户体验仍偏向“传统进销存 SaaS + AI 助手入口 + AI员工展示”。用户还不能明显感受到“AI 原生应用”的差异，因为：

1. 首页没有一个强主入口让老板直接用自然语言驱动业务。
2. AI 员工卡片更多是展示，不是可感知的工作流入口。
3. AI 建议没有形成“发现问题 → 解释依据 → 生成草稿 → 等待确认 → 执行 → 复盘”的闭环。
4. 现有 confirmation-first 后端能力没有在前端以 AI 任务状态机呈现。
5. SSE/LLM 的流式体验没有成为核心路径，用户看不到 AI 在分工、检查、生成草稿。

Phase I 的目标是把系统从“AI 包装的 SaaS”推进到“AI 员工驱动的经营系统”。

## 2. 产品目标

Phase I 完成后，老板一进入系统应立刻感受到：

> 这个系统不是让我点菜单填表，而是 AI 员工在帮我看店、发现问题、解释原因、生成业务草稿，并在我确认后安全执行。

具体目标：

1. 首页顶部出现 AI Command Center，成为全局主入口。
2. 用户可用自然语言完成查询、分析、销售草稿、库存草稿、采购建议等任务。
3. 每次 AI 动作都显示可理解的分工过程，例如“AI运营协调官 → 销售顾问 → 库存风控专员”。
4. 高风险写操作必须继续 confirmation-first，AI 只能生成草稿，不能直接修改业务事实。
5. AI 任务中心用状态机展示任务生命周期，而不是普通待办列表。
6. AI 建议必须包含依据、风险、下一步动作。
7. 不为了 AI 感伪造业务数据；所有指标和建议必须来自真实后端数据或明确标记为规则生成。

## 3. 范围

### 3.1 本阶段包含

I1：首页 AI Command Center
- 在 dashboard 顶部核心区域加入自然语言输入框。
- 支持快捷指令：查营业额、查库存风险、生成销售单、生成采购建议、查看待确认任务。
- 支持 SSE 流式输出，把后端事件显示成 AI 分工步骤。
- 支持从结果直接进入确认任务或业务页面。

I2：AI 员工真实状态化
- AI 员工卡展示真实计数：今日任务、待确认、已完成、风险数量、关联模块。
- 点击 AI 员工可进入员工详情视图。
- 员工详情展示：今日工作、最近任务、可执行动作、数据依据。

I3：AI 任务中心状态机
- 用统一状态展示任务：discovered、suggested、draft_created、awaiting_confirmation、executing、completed、failed、ignored。
- 聚合 V2TaskRun、V2Confirmation、V2Message、V2AuditLog、inventory ledger、sales/purchase records。
- 每个任务卡显示：负责人、当前状态、业务影响、风险、下一步 CTA。

I4：三类 AI 草稿闭环
- 自然语言生成销售单草稿。
- 自然语言生成库存入/出库草稿。
- 规则/AI 生成采购建议草稿。
- 所有草稿必须经过 confirmation approve 后才落账。

I5：AI 经营参谋日报 MVP
- 在首页生成“今日经营简报”。
- 包含销售总结、库存风险、待确认事项、建议动作。
- 初版可基于规则生成，后续接 LLM 润色。

### 3.2 本阶段不包含

1. 不做微服务拆分。
2. 不做自动交易/自动下单/自动扣库存。
3. 不伪造客服、营销、订阅、外部通知数据。
4. 不把 AI 建议变成无需确认的直接执行。
5. 不要求一次性完成复杂长期记忆或向量知识库；只为任务/意图缓存预留接口。

## 4. 推荐实现顺序

### I1：AI Command Center（第一优先级）

原因：这是用户感知 AI-native 最直接的入口。

前端：
- 在 Dashboard 问候区下方加入大输入框。
- 输入框 placeholder：`老板，想让我帮你查什么、记什么、生成什么？`
- 快捷按钮：
  - 查今日营业额
  - 看库存风险
  - 生成销售单
  - 生成采购建议
  - 处理待确认
- 提交后进入流式 AI 面板。

后端：
- 优先复用现有 `/api/v2/chat/stream`。
- 如果现有返回事件不足，新增/扩展事件类型：
  - `agent_step`：某个 AI 员工正在处理
  - `business_context`：读取到的真实业务数据摘要
  - `draft_created`：生成草稿
  - `awaiting_confirmation`：等待确认
  - `done`：结束
  - `error`：错误

前端显示：
- 每个 SSE 事件渲染成一条“AI员工工作步骤”。
- 最终结果如果包含 confirmation_id，显示确认卡片。

### I3：AI 任务中心状态机（第二优先级）

原因：让用户看到 AI 是持续工作的，不只是一次聊天。

后端新增 BFF：
- `GET /api/v2/ai-workflows`
- 聚合当前租户/门店下：
  - V2TaskRun
  - V2Confirmation
  - V2Message
  - V2AuditLog
  - 销售/采购/库存相关业务记录

返回结构建议：

```json
{
  "workflows": [
    {
      "workflow_id": "wf_xxx",
      "title": "张三销售单草稿等待确认",
      "owner_agent": "销售顾问",
      "status": "awaiting_confirmation",
      "risk_level": "medium",
      "evidence": ["识别到2个商品", "库存充足", "确认后将扣库存"],
      "next_action": {
        "type": "open_confirmation",
        "label": "查看并确认",
        "confirmation_id": "conf_xxx"
      },
      "timeline": [
        {"status": "discovered", "actor": "AI运营协调官", "summary": "识别为销售出库操作"},
        {"status": "draft_created", "actor": "销售顾问", "summary": "已生成销售单草稿"},
        {"status": "awaiting_confirmation", "actor": "AI运营协调官", "summary": "等待老板确认"}
      ]
    }
  ]
}
```

前端：
- 任务中心不再只是 confirmation 列表。
- 使用时间线/状态胶囊展示 AI 工作流。
- 支持筛选：全部、待确认、已完成、失败、已忽略。

### I4：三类 AI 草稿闭环（第三优先级）

销售单：
- 输入：`张三买了2把螺丝刀和1个插座`
- 输出：销售单草稿 confirmation。
- approve 后创建销售单、扣库存、写 ledger、写财务流水、写审计。

库存入/出库：
- 输入：`今天进了10箱螺丝`
- 输出：库存入库草稿 confirmation。
- approve 后写库存 ledger 与 snapshot。

采购建议：
- 输入：`帮我看看今天要补什么货`
- 输出：采购建议草稿，基于低库存、销量、供应商信息。
- approve 后创建采购单；是否自动入库沿用当前采购 MVP 逻辑，必须在确认卡上说明。

### I2：AI 员工真实状态化（第四优先级）

每个员工状态来自真实数据：

AI运营协调官：
- pending confirmations
- failed task runs
- 今日待办

经营数据分析员：
- 今日销售额
- 销售笔数
- 财务流水摘要

库存风控专员：
- 低库存商品
- 库存变动
- 库存相关待确认任务

商品档案管理员：
- 商品数量
- 最近新增/修改商品
- 商品审计事件

经营策略顾问：
- AI suggestions
- 采购建议
- 经营简报

### I5：AI 经营参谋日报 MVP（第五优先级）

首页增加“AI参谋日报”：
- 今日销售表现
- 商品/库存变化
- 待处理事项
- 风险提示
- 明日建议

初版使用规则生成，不调用外部 LLM；后续可以接 LLM 润色，但必须保留数据依据。

## 5. AI 任务状态定义

统一状态机：

1. `discovered`：AI 发现问题或识别到用户意图。
2. `suggested`：AI 给出建议，但尚未生成业务草稿。
3. `draft_created`：AI 已生成草稿。
4. `awaiting_confirmation`：草稿等待老板确认。
5. `executing`：确认后正在执行。
6. `completed`：执行完成。
7. `failed`：执行失败，可查看 request_id/error。
8. `ignored`：老板忽略或暂不处理。

状态来源映射：
- V2Confirmation.status=pending → awaiting_confirmation
- V2Confirmation.status=approved + 关联业务成功 → completed
- V2Confirmation.status=rejected → ignored
- V2TaskRun.status=failed → failed
- V2TaskRun.status=running → executing
- 规则生成但无草稿 → suggested

## 6. 安全与业务边界

1. AI 不直接修改库存、销售、采购、财务事实。
2. 所有写操作必须走 confirmation-first。
3. 确认卡必须展示：影响对象、数量、金额、库存变化、风险、操作者。
4. 每次 approve/reject 必须写审计日志。
5. 所有 BFF 查询必须限定 tenant_id + shop_id。
6. 错误响应必须带 request_id，不泄露敏感信息。
7. Provider trial 继续显式 opt-in，不默认读取真实凭证。

## 7. 前端体验设计

### Dashboard 顶部 AI Command Center

布局：
- 在问候区和 KPI 区之间加入大卡片。
- 白底圆角，紫色渐变边缘/按钮，保持 dashboard.jpg 风格。
- 左侧文案：`AI运营协调官在线`
- 主输入框：`老板，想让我帮你查什么、记什么、生成什么？`
- 下方快捷指令。

### 流式响应面板

用户提交后：
- 输入框下方出现 AI 工作步骤。
- 每条步骤带 AI 员工名称、状态、摘要。
- 最终出现结果卡片或确认卡片。

示例：

```text
AI运营协调官：我判断这是销售出库任务。
销售顾问：识别客户 张三，商品 螺丝刀 x2、插座 x1。
库存风控专员：库存检查通过。
销售顾问：已生成销售单草稿，等待老板确认。
```

### 任务中心

页面改为三段：
1. AI任务统计：待确认、进行中、已完成、失败。
2. 任务状态筛选。
3. 工作流卡片列表。

## 8. 后端 API 设计

### 8.1 AI Command Center

优先复用：
- `POST /api/v2/chat/stream`

如需增强，事件格式：

```json
{"event":"agent_step","data":{"agent":"AI运营协调官","summary":"识别为销售出库任务","status":"discovered"}}
{"event":"business_context","data":{"summary":"找到2个匹配商品，库存充足"}}
{"event":"draft_created","data":{"draft_type":"sales.order_create","confirmation_id":"conf_xxx"}}
{"event":"awaiting_confirmation","data":{"confirmation_id":"conf_xxx","message":"等待老板确认后执行"}}
{"event":"done","data":{"message_id":"msg_xxx"}}
```

### 8.2 AI Workflows BFF

新增：
- `GET /api/v2/ai-workflows`
- `GET /api/v2/ai-workflows/{workflow_id}` 可后置。

### 8.3 AI Employees Summary

可复用现有 pc-dashboard overview；如拆分新增：
- `GET /api/v2/ai-employees/summary`

## 9. 数据来源

必须使用真实数据：
- V2TaskRun
- V2Confirmation
- V2Message
- V2AuditLog
- V2InventoryLedgerEvent
- V2InventoryStockSnapshot
- V2SalesOrder / V2SalesOrderLine
- V2PurchaseOrder
- V2Customer
- V2FinanceTransaction

规则建议可以由服务层生成，但必须返回 evidence。

## 10. 测试计划

后端：
1. AI workflows BFF 需要 HTTP 回归测试。
2. 测试 tenant/shop 隔离。
3. 测试 pending confirmation 映射为 awaiting_confirmation。
4. 测试 approved/rejected/failed 状态映射。
5. 测试 high-risk action 不直接落账。
6. 测试 SSE 事件格式稳定。

前端：
1. `npm run build` 必须通过。
2. 浏览器登录后首页能看到 AI Command Center。
3. 输入自然语言后能看到流式步骤。
4. 生成草稿后能打开确认卡。
5. 任务中心能看到 AI 工作流状态。
6. Console errors 为 0。

验收：
1. 默认 preflight 通过。
2. 必要 focused pytest 通过。
3. Docker 8001 能访问新 UI。
4. 写阶段报告。
5. commit + push。

## 11. 成功标准

Phase I 至少满足：

1. 首页有醒目的 AI Command Center。
2. 用户能用自然语言触发至少 3 类任务：查询经营、查询库存、生成销售草稿。
3. AI 响应展示多步骤、多员工协作过程。
4. 销售/库存/采购写操作仍需确认。
5. AI任务中心能展示真实 workflow 状态。
6. AI建议和任务卡都有 evidence/risk/CTA。
7. 不出现伪造业务数据。
8. 外网 8001 可体验新 AI-native 入口。

## 12. 实施分解建议

建议分成 4 个提交：

1. `feat: add ai command center shell`
   - 前端首页输入框、快捷指令、基础状态。

2. `feat: stream ai command center steps`
   - SSE 接入、事件展示、确认卡入口。

3. `feat: add ai workflow bff`
   - 后端聚合 API、任务状态机映射、测试。

4. `feat: connect ai workflow center`
   - 前端任务中心改造、员工状态增强、浏览器验收。

## 13. 自检结论

本设计没有要求新增伪造数据；没有绕过 confirmation-first；没有引入微服务拆分；没有要求默认真实 Provider 调用；范围可以拆成多个小提交逐步实现。
