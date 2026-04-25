# Business F1 销售单/订单模块完成报告

生成时间：2026-04-25 19:09:59 CST

## 结论

F1「销售单/订单」模块已完成第一版真实闭环：

- 新增销售单与销售单明细数据模型
- 新增 Alembic 迁移，当前版本升级到 `20260425_01`
- 新增销售单创建 API 与列表 API
- 创建销售单会同步扣减库存快照
- 创建销售单会写入库存 ledger，`source_type=sales_order`
- 销售单按 tenant_id + shop_id 隔离
- 库存不足、跨租户商品均无副作用拒绝
- PC/H5 已新增「销售单」导航、快速开单、真实订单列表
- Docker 全链路验收通过

## 后端新增能力

### 数据表

1. `v2_sales_orders`
   - 销售单主表
   - 字段包含：租户、门店、订单号、状态、客户名、支付方式、总金额、备注、创建人、时间

2. `v2_sales_order_lines`
   - 销售单明细表
   - 字段包含：订单、商品、商品名快照、数量、单位、单价、行金额

### API

1. `POST /api/v2/sales/orders`
   - 创建销售单
   - 请求字段：`customer_name`、`payment_method`、`items`、`note`
   - 每个 item 包含：`inventory_item_id`、`quantity`、`unit_price`
   - 成功后返回完整订单与明细
   - 同步扣减库存并写 ledger

2. `GET /api/v2/sales/orders?limit=50`
   - 当前门店销售单列表
   - 严格限定当前 `tenant_id` + `shop_id`

### 错误处理

- 库存不足：409，`insufficient_stock`
- 跨租户/不存在商品：404，`inventory_item_not_found`
- 参数错误：422，`validation_error`
- 上下文账号不一致：403，`context_account_mismatch`

## PC/H5 新增能力

新增「销售单」导航页：

- F1 已开放标识
- 快速开销售单
- 自动选择当前有库存商品
- 输入客户、数量、单价
- 创建后刷新订单列表与库存
- 订单列表展示：订单号、客户、支付方式、金额、明细数、状态

## 测试结果

### Focused F1 测试

命令：

```bash
PYTHONPATH=backend pytest backend/tests/test_v2_sales_orders_http_flow.py -q
```

结果：

```text
4 passed in 8.53s
```

覆盖：

1. 创建销售单写入订单、明细、库存出库 ledger，并扣减库存
2. 销售单列表按租户和门店隔离
3. 库存不足时 409 且不写入任何 ledger/订单副作用
4. 跨租户商品 404 且不泄露资源

### 默认 preflight

命令：

```bash
RUN_DOCKER_ACCEPTANCE=0 RUN_PROVIDER_TRIAL_PREFLIGHT=0 bash backend/scripts/run_backend_preflight.sh
```

结果：

```text
34 passed in 54.23s
H5 build passed
readiness overall_status=ready ready_count=15 missing_count=0
preflight passed
```

### 完整 Docker preflight

命令：

```bash
RUN_DOCKER_ACCEPTANCE=1 RUN_PROVIDER_TRIAL_PREFLIGHT=0 bash backend/scripts/run_backend_preflight.sh
```

结果：

```text
34 passed in 54.01s
H5 build passed
readiness overall_status=ready ready_count=15 missing_count=0
ALEMBIC_VERSION 20260425_01
TABLE_COUNT 42
Phase8 8/8 passed
Phase9 5/5 passed
Phase10 6/6 tests passed
Docker backend acceptance passed
preflight passed
```

## Docker 手动销售单链路

在运行中的 Docker 容器 `business-backend` 上完成真实 API 链路：

1. 登录
2. 获取租户
3. 获取门店
4. 选择上下文
5. 查询库存
6. 创建销售单
7. 查询销售单列表
8. 查询库存流水

结果摘要：

```text
order_no: SO2026042511090168BEC9
total_amount: 25.00
orders_count: 1
latest_event_source: sales_order
```

## 浏览器 QA

访问：`http://127.0.0.1:8001/`

验证结果：

- 登录成功
- 左侧出现「销售单」导航
- 销售单页面加载成功
- 可点击「创建销售单」
- 创建后库存从 94 减到 93
- 订单列表新增记录
- 浏览器 console：0 JS error

## 修复项

完整 Docker 验收首次失败，原因是新增 F1 迁移后验收脚本仍硬编码旧 Alembic 版本 `20260419_05` 与旧表数量阈值。

已修复为：

- Alembic 期望版本：`20260425_01`
- 表数量阈值：`>= 42`

修复后完整 Docker preflight 通过。

## 当前边界

F1 第一版已完成「销售交易产生真实订单 + 扣库存 + 写流水」闭环，但还未包含：

- 订单取消/退款/退货
- 多支付方式对账
- 客户档案关联
- 应收应付/赊账
- 小票打印
- 销售单详情页
- AI 自然语言生成销售单草稿并走确认审批

这些建议进入后续 F1.1/F2 继续推进。
