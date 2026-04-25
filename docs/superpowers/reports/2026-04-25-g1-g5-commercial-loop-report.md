# Business G1-G5 商业闭环模块完成报告

生成时间：2026-04-25 19:30:43 CST

## 结论

已按用户要求的 1～5 顺序推进并完成后端商业闭环第一版：

1. F1.1 销售单详情、取消、退货/退款
2. F2 采购单/供应商模块
3. F3 客户档案与复购分析
4. F4 财务流水/收支对账
5. AI 自然语言生成销售单草稿，并通过 confirmation 审批后落账

本轮重点是把 Business 从“销售单创建 + 扣库存”继续推进到“销售、退货、采购、客户、财务、AI 草稿审批”的真实商业闭环基础。

## 1. F1.1 销售单详情、取消、退货/退款

新增能力：

- `GET /api/v2/sales/orders/{sales_order_id}`
  - 查看销售单详情与明细
  - 严格限定当前 `tenant_id + shop_id`
- `POST /api/v2/sales/orders/{sales_order_id}/cancel`
  - 取消已支付销售单
  - 自动把销售单明细库存回补到当前门店库存快照
  - 写入库存 ledger：`source_type=sales_order_cancel`
  - 写入财务退款流水：`transaction_type=sales_refund`
- `POST /api/v2/sales/orders/{sales_order_id}/returns`
  - 支持按销售单明细部分退货
  - 自动库存回补
  - 写入库存 ledger：`source_type=sales_return`
  - 写入销售退货记录
  - 写入财务退款流水
  - 销售单状态更新为 `partially_refunded` 或 `refunded`

## 2. F2 采购单/供应商模块

新增数据模型：

- `v2_suppliers`
- `v2_purchase_orders`
- `v2_purchase_order_lines`

新增 API：

- `POST /api/v2/purchasing/suppliers`
  - 创建供应商
- `POST /api/v2/purchasing/orders`
  - 创建采购单
  - 采购单第一版按“已收货 received”处理
  - 自动增加库存
  - 写库存 ledger：`source_type=purchase_order`
  - 写财务支出流水：`transaction_type=purchase_payment`

## 3. F3 客户档案与复购分析

新增数据模型：

- `v2_customers`

新增 API：

- `POST /api/v2/customers`
  - 创建客户档案
- `GET /api/v2/customers/repurchase-analysis`
  - 基于客户姓名与销售单 `customer_name` 做第一版复购统计
  - 返回客户数量、匹配订单数、客户订单数、累计金额

说明：

- 当前是轻量 MVP 分析，不引入复杂 CRM 关系表。
- 后续可升级为销售单 `customer_id` 外键、客户标签、欠款、复购周期、沉睡客户提醒。

## 4. F4 财务流水/收支对账

新增数据模型：

- `v2_finance_transactions`

新增 API：

- `GET /api/v2/finance/transactions?limit=50`
  - 查询当前门店财务流水
- `GET /api/v2/finance/summary`
  - 汇总收入、支出、净现金流

已接入的业务来源：

- 销售单创建：收入流水 `sales_revenue`
- 销售单取消：支出流水 `sales_refund`
- 销售退货：支出流水 `sales_refund`
- 采购单入库：支出流水 `purchase_payment`

## 5. AI 销售单草稿 + confirmation 审批

新增 API：

- `POST /api/v2/sales/order-drafts/from-text`

能力：

- 接收自然语言，例如：`卖出2把销售单测试电钻，单价150，客户老王`
- 解析商品、数量、单价、客户
- 生成真实 `V2ConversationSession`
- 生成真实 `V2Message`
- 生成真实 `V2TaskRun(intent_type="sales.order_create")`
- 生成真实 `V2Confirmation(type="sales.order_create", status="pending")`
- 审批 `POST /api/v2/confirmations/{confirmation_id}/approve` 后，自动创建销售单并扣库存、写销售流水、写财务收入流水

关键边界：

- AI 不直接创建销售单
- AI 只生成待确认草稿
- 只有 confirmation approve path 才落账

## 新增迁移与表

新增迁移：

- `backend/alembic/versions/20260425_02_create_v2_commercial_modules.py`

当前 Alembic head：

- `20260425_02`

Docker 验收表数量：

- `TABLE_COUNT 48`

## 多租户隔离

本轮所有新增 API 均要求：

- `Authorization: Bearer <accessToken>`
- `X-Context-Token: <contextToken>`

所有业务读写均限定：

- `tenant_id == context.tenant_id`
- `shop_id == context.shop_id`

跨租户商品、供应商、销售单默认 404 或不可见，避免资源泄露。

## 回归测试

新增测试：

- `backend/tests/test_v2_commercial_modules_http_flow.py`

覆盖：

- 销售单详情
- 销售单取消，库存回补，财务退款流水
- 销售退货，库存回补，财务退款流水
- 供应商创建
- 采购单创建，库存入库，财务采购支出
- 客户创建
- 客户复购分析
- 财务汇总
- AI 销售单草稿 confirmation
- confirmation approve 后自动创建销售单

## 验收结果

### Focused 回归

命令：

```bash
PYTHONPATH=backend pytest backend/tests/test_v2_sales_orders_http_flow.py backend/tests/test_v2_commercial_modules_http_flow.py backend/tests/test_backend_readiness_summary.py -q
```

结果：

- `8 passed in 13.85s`

### 默认 preflight

命令：

```bash
RUN_DOCKER_ACCEPTANCE=0 RUN_PROVIDER_TRIAL_PREFLIGHT=0 bash backend/scripts/run_backend_preflight.sh
```

结果：

- `36 passed in 64.68s`
- H5 build passed
- readiness：`overall_status=ready`
- readiness：`ready_count=16`
- readiness：`missing_count=0`

### 完整 Docker preflight

命令：

```bash
RUN_DOCKER_ACCEPTANCE=1 RUN_PROVIDER_TRIAL_PREFLIGHT=0 bash backend/scripts/run_backend_preflight.sh
```

结果：

- `36 passed in 65.26s`
- H5 build passed
- Docker build passed
- Alembic：`20260425_02`
- Table count：`48`
- Phase8：`8/8 passed`
- Phase9：`5/5 passed`
- Phase10：`6/6 passed`

## 本轮主要文件

- `backend/app/models/v2_commercial.py`
- `backend/app/services/v2_commercial.py`
- `backend/app/api/v2/routes/commercial.py`
- `backend/alembic/versions/20260425_02_create_v2_commercial_modules.py`
- `backend/tests/test_v2_commercial_modules_http_flow.py`
- `backend/app/services/v2_sales.py`
- `backend/app/api/v2/routes/sales.py`
- `backend/app/services/v2_conversation.py`
- `backend/scripts/run_backend_preflight.sh`
- `backend/scripts/run_docker_backend_acceptance.sh`
- `backend/app/devtools/backend_readiness_summary.py`

## 后续建议

1. 把 F2/F3/F4 做到 PC/H5 页面，不再只停留在 API 层。
2. 将销售单绑定 `customer_id`，替代当前 MVP 的 `customer_name` 关联。
3. 采购单增加状态流：草稿、待收货、已收货、部分收货、取消。
4. 财务增加日/月报、支付方式汇总、应收应付、欠款。
5. AI 草稿解析从规则解析升级为 LLM structured output，但继续保持 confirmation-first 安全边界。
