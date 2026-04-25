# Phase I4 AI 草稿闭环增强计划

## 背景

Phase I1 已完成首页 AI Command Center，I3 已完成 AI Task Flow 第一版。当前销售草稿已有正式 confirmation-first 后端闭环，但采购草稿仍是直接创建采购单，库存草稿主要藏在 Chat 入口里，用户对“销售/采购/库存三类 AI 草稿闭环”的感知还不完整。

## 目标

1. 销售、采购、库存三类高风险动作都能从 AI 入口生成待确认草稿。
2. AI 不直接创建销售单、采购入库、扣减/增加库存；所有写操作先进入 `V2Confirmation(status=pending)`。
3. 老板在 AI Task Flow 点击“确认并执行”后，才调用既有确定性服务落账。
4. H5 首页 Command Center 能明确识别并展示三类草稿结果。
5. 任务中心能用商户可读方式展示采购草稿摘要、影响、风险和证据。

## 非目标

- 不引入微服务。
- 不做真实 LLM provider 调用。
- 不绕过现有 tenant_id/shop_id 隔离。
- 不伪造订单、客户、财务或库存数据。

## Task 1：后端采购草稿 TDD

- [x] 扩展商业 HTTP 回归：调用 `/api/v2/purchasing/order-drafts/from-text` 后只生成 pending confirmation，不立即创建采购单/入库/财务。
- [x] 验证 approval 后创建真实采购单、库存入库 ledger、采购支出财务流水。
- [x] 验证 confirmation 类型为 `purchase.order_create`。

## Task 2：后端采购草稿实现

- [x] 新增 `purchase.order_create` 到允许的 message intent 和 task draft type。
- [x] 新增 deterministic parser：从文本匹配供应商、商品、数量、单价。
- [x] 新增服务 `create_purchase_order_confirmation_from_text`。
- [x] 新增路由 `POST /api/v2/purchasing/order-drafts/from-text`。
- [x] 扩展 confirmation approval：`purchase.order_create` approval 调用 `create_purchase_order`。

## Task 3：H5 API 与 Command Center

- [x] 新增 `api.createPurchaseOrderDraft`。
- [x] Command Center 增加采购草稿快捷指令。
- [x] Command Center 能识别采购/补货/进货语句并生成采购待确认草稿。
- [x] Command Center 能识别库存入库/出库语句，通过现有 chat confirmation-first 生成库存待确认草稿。

## Task 4：AI Task Flow 展示增强

- [x] `buildTaskViewModel` 增加 `purchase.order_create`。
- [x] 优化 inventory stock-in 字段兼容：`item_id` 和 `inventory_item_id` 都能展示。
- [x] 展示采购供应商、明细数、预计金额、影响模块。

## Task 5：验证、部署与提交

- [x] focused pytest：商业模块 HTTP 回归。
- [x] `cd apps/h5 && npm run build`。
- [x] 浏览器验证：销售/采购/库存草稿至少各生成一个 pending task，任务中心可见。
- [x] console errors = 0，无横向溢出。
- [x] 热更新 8001 容器静态资源。
- [x] `git diff --check`，只 stage 相关文件，提交并推送。
