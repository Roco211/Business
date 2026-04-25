# Business H5 商用硬化验收报告（审计 / 导出 / 稳定性）

日期：2026-04-25
分支：`hermes/ai-native-saas-rewrite`

## 本阶段目标

完成 H1-H4 之后的 H5 商用硬化切片：

1. 关键操作审计：取消、退货退款、销售、采购、客户、导出等关键动作必须可追溯。
2. CSV 导出：销售单、采购单、财务流水、库存流水支持后端真实数据导出。
3. 稳定性与错误日志：未处理异常带 request_id 记录日志并返回统一错误结构。
4. 生产演练覆盖：轻量稳定性检查纳入生产试运行演练与 readiness summary。
5. 完整验收：默认 preflight、Docker 验收、浏览器冒烟通过。

## 已完成内容

### 1. 关键操作审计

新增统一审计写入 helper：

- `backend/app/services/v2_audit.py`

已接入以下关键动作：

- `sales_order_create`
- `sales_order_cancel`
- `sales_order_return_refund`
- `supplier_create`
- `purchase_order_create`
- `customer_create`
- `export_sales_orders`
- `export_purchase_orders`
- `export_finance_transactions`
- `export_inventory_ledger`

审计日志继续使用 `V2AuditLog`，并记录：

- `tenant_id`
- `shop_id`
- `account_id`
- `action`
- `resource_type`
- `resource_id`
- `metadata_json`
- `created_at`

同时修正 `/api/v2/audit-logs` 查询，确保按当前执行上下文限定 `tenant_id` 与 `shop_id`。

### 2. CSV 导出

新增导出路由：

- `backend/app/api/v2/routes/exports.py`

新增接口：

- `GET /api/v2/exports/sales-orders`
- `GET /api/v2/exports/purchase-orders`
- `GET /api/v2/exports/finance-transactions`
- `GET /api/v2/exports/inventory-ledger`

导出行为：

- 使用后端真实数据，不从 H5 本地状态拼 CSV。
- 所有查询均限定当前租户与门店。
- 返回 `text/csv`。
- 导出动作本身写入审计日志。

H5 已增加导出入口：

- 销售单页面：导出销售单 CSV
- 采购单页面：导出采购单 CSV
- 财务流水页面：导出财务 CSV
- 库存管理页面：导出库存流水 CSV

涉及文件：

- `apps/h5/src/api.ts`
- `apps/h5/src/App.tsx`

### 3. 错误日志与 request_id

`backend/app/main.py` 新增未处理异常日志能力：

- 接收或生成 `X-Request-ID`
- 未处理异常日志包含 `request_id`、HTTP method、path
- 500 响应返回统一 `V2ErrorEnvelope`
- 响应头返回 `X-Request-ID`
- CORS 允许并暴露 `X-Request-ID`

新增回归测试：

- `backend/tests/test_production_readiness_config.py::test_app_logs_unhandled_errors_with_request_id`

### 4. 轻量稳定性检查

新增脚本：

- `backend/scripts/run_lightweight_stability_check.py`

检查内容：

- 连续 25 次 `/api/v2/health`
- `/openapi.json` 可访问
- OpenAPI 中存在四个 CSV 导出接口

已纳入：

- `backend/scripts/run_production_trial_rehearsal.sh`
- `backend/app/devtools/backend_readiness_summary.py`
- `backend/tests/test_backend_readiness_summary.py`

readiness summary 结果：

- `overall_status=ready`
- `ready_count=18`
- `missing_count=0`

## 验证记录

### 1. focused 回归

命令：

```bash
python3 -m compileall -q backend/app
PYTHONPATH=backend pytest backend/tests/test_v2_commercial_modules_http_flow.py backend/tests/test_production_readiness_config.py backend/tests/test_backend_readiness_summary.py -q
```

结果：

- `7 passed`

### 2. H5 构建

命令：

```bash
cd apps/h5 && npm run build
```

结果：

- TypeScript build 通过
- Vite build 通过

### 3. 生产演练（不含 Docker）

命令：

```bash
RUN_DOCKER_ACCEPTANCE=0 bash backend/scripts/run_production_trial_rehearsal.sh
```

结果：

- 生产 compose YAML 检查通过
- backup/restore 脚本语法检查通过
- production readiness 回归通过：`3 passed`
- lightweight stability check 通过
- readiness summary：`ready_count=18`、`missing_count=0`
- `production trial rehearsal passed`

### 4. 默认 preflight

命令：

```bash
RUN_DOCKER_ACCEPTANCE=0 RUN_PROVIDER_TRIAL_PREFLIGHT=0 bash backend/scripts/run_backend_preflight.sh
```

结果：

- pytest：`37 passed`
- H5 build passed
- readiness：`overall_status=ready`、`ready_count=18`、`missing_count=0`
- `preflight passed`

### 5. 完整 Docker preflight

命令：

```bash
RUN_DOCKER_ACCEPTANCE=1 RUN_PROVIDER_TRIAL_PREFLIGHT=0 bash backend/scripts/run_backend_preflight.sh
```

结果：

- backend preflight passed
- Docker backend acceptance passed
- Phase 8：`8/8 passed`
- Phase 9：`5/5 passed`
- Phase 10：`6/6 tests passed`
- 容器：`business-backend`
- 地址：`http://127.0.0.1:8001`

### 6. 浏览器 H5 冒烟

访问地址：

- `http://127.0.0.1:8001/`

验证：

- 页面标题：`Business AI 五金店大管家`
- 演示登录成功
- 工作台正常
- 销售单页面存在 `导出销售单CSV`
- 采购单页面存在 `导出采购单CSV`
- 财务流水页面存在 `导出财务CSV`
- 库存管理页面存在 `导出库存流水CSV`
- 库存快照与库存流水表格正常展示真实后端数据
- 浏览器 console：`0` messages，`0` errors

## 风险与后续建议

1. 当前 rate limiting 仍为单进程 in-memory，适合单实例试运行；多实例生产应迁移到 Redis 或网关限流。
2. CSV 导出当前是 MVP 同步导出；大数据量时建议升级为异步导出任务与下载中心。
3. 审计日志已覆盖核心商业动作，后续可扩展到商品删除、权限变更、价格调整等高风险动作。
4. 当前错误日志已包含 request_id；正式生产建议接入结构化日志采集与告警系统。

## 结论

本阶段 H5 商用硬化目标完成。Business 当前已具备：

- 核心商业闭环真实后端数据流
- 关键操作审计追溯
- 四类 CSV 导出
- request_id 级错误日志
- 轻量稳定性检查
- 默认 preflight 与 Docker preflight 验收证据
- Docker 服务 H5 与 API 的浏览器冒烟证据

可以进入下一阶段：更细粒度权限/RBAC、异步导出、生产日志采集、真实服务器试运行。