# Phase K5 异步导出与大数据量保护计划

## 背景

当前 `/api/v2/exports/*` CSV 导出为同步接口，适合 demo 和小数据量验证；正式商用后，销售、财务、采购、库存流水数据量上来时，同步导出可能阻塞 Web 请求、影响 API 可用性，也缺少导出任务状态、下载审计和过期清理边界。

## 目标

1. 新增 V2 export job 任务表，所有任务严格绑定 `tenant_id` + `shop_id` + `account_id`。
2. 新增异步导出 API：创建任务、查询任务状态、下载已完成 CSV。
3. 继续保留现有同步导出兼容接口，但新增大数据量保护提示与更明确的 limit 上限。
4. 导出创建/完成/下载写入 `V2AuditLog`，便于商用审计。
5. 继续复用 K1 RBAC：不同 export_type 映射到 `exports:sales|purchasing|finance|inventory`。
6. 不新增真实外部队列；本阶段采用 FastAPI BackgroundTasks + 数据库任务表，后续可替换为 Redis/RQ/Celery。
7. H5 “商用试运行验收”页展示 K5 已完成能力。

## API 设计

- `POST /api/v2/exports/jobs`
  - body: `{ export_type, limit? }`
  - export_type: `sales_orders | purchase_orders | finance_transactions | inventory_ledger`
  - 返回 job 摘要；后台生成 CSV。
- `GET /api/v2/exports/jobs`
  - 返回当前 tenant/shop 下本账号或本店铺导出任务列表。
- `GET /api/v2/exports/jobs/{job_id}`
  - 查询单个任务状态；跨租户/跨门店统一 404。
- `GET /api/v2/exports/jobs/{job_id}/download`
  - 仅 completed 可下载 CSV；写下载审计。

## 状态机

- `queued`：已创建，等待处理。
- `running`：处理中。
- `completed`：已生成 CSV，可下载。
- `failed`：失败，记录安全错误摘要。
- `expired`：预留，后续定时清理。

## 安全与隔离

- 所有查询必须限定 `tenant_id` + `shop_id`。
- 权限按 export_type 检查，不允许通过 job_id 泄露跨租户资源。
- CSV 内容只来自真实数据库，不伪造数据。
- 审计 metadata 不写 token、secret、连接串。

## 验收

1. 新增失败契约测试：异步销售导出创建、完成、下载、审计。
2. 新增失败契约测试：无权限角色创建敏感导出返回 403。
3. 新增失败契约测试：跨租户/跨门店 job 查询返回 404。
4. 后端 compileall、相关 pytest、H5 build、git diff check 通过。
5. Docker 热更新后 `/api/v2/health` 正常，浏览器 “试运行验收” 页展示 K5。
