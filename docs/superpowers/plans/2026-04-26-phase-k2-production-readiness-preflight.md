# Phase K2：生产数据库与配置预检

## 背景

K1 已完成 RBAC 权限角色补强。正式商用前的下一项高优先级短板是：系统必须能明确区分“本地演示/商用试运行”和“正式生产配置”，避免 SQLite、开放 CORS、关闭安全头、无限流等配置被误认为可以正式上线。

## 目标

新增生产级 readiness/preflight 检查，覆盖：

1. 生产数据库连接配置
   - `APP_ENV=production` 时必须使用 PostgreSQL/PostgreSQL-compatible URL。
   - SQLite 只允许 local-demo/dev，不允许被标记为正式生产 ready。
   - 不输出数据库密码、连接串或凭证。

2. 生产安全配置
   - `APP_ENV=production` 时必须显式配置 `APP_CORS_ORIGINS`。
   - 不允许 `*` 作为生产 CORS origin。
   - 生产必须启用安全头。
   - 生产建议配置非 0 限流。

3. H5 商用验收页可见性
   - 在“商用硬化与部署/生产前补强”里展示 K1 RBAC 已完成。
   - 展示 K2 生产预检已纳入 readiness，而不是继续停留在泛化“生产前补强”。

## 安全边界

- 不读取或输出 `.env` 内容。
- 不输出 DATABASE_URL 原文。
- 不访问真实 PostgreSQL，不做破坏性数据库操作；本阶段是配置级 preflight。
- 不伪造生产完成：未配置生产要求时状态为 degraded。

## TDD 契约

新增/扩展 `backend/tests/test_system_readiness_api.py`：

1. `test_readiness_endpoint_degrades_production_when_database_is_sqlite`
   - `APP_ENV=production`
   - `DATABASE_URL=sqlite:///...`
   - 期望 `checks.production_database.status == degraded`
   - 期望 details 只包含 dialect/provider，不包含 secret/URL。

2. `test_readiness_endpoint_reports_ready_for_production_postgres_and_safe_config`
   - `APP_ENV=production`
   - PostgreSQL URL + 显式 CORS + 安全头 + 限流
   - 期望 `production_database` 与 `production_config` ready。

## 验收命令

```bash
cd /root/business-clone
python3 -m compileall -q backend/app
PYTHONPATH=backend pytest backend/tests/test_system_readiness_api.py -q
PYTHONPATH=backend pytest backend/tests/test_v2_identity_context.py -q
PYTHONPATH=backend pytest backend/tests/test_v2_pc_dashboard_overview_http_flow.py -q backend/tests/test_v2_commercial_modules_http_flow.py -q backend/tests/test_v2_chat_http_confirmation_flow.py -q
cd apps/h5 && npm run build
cd /root/business-clone && git diff --check
```

## Docker / 浏览器验收

- 热更新 `business-backend` 后端 Python 文件与 H5 dist。
- 重启容器。
- `/api/v2/health` 返回 200。
- 浏览器访问 8001，进入“试运行验收”，页面展示 RBAC 与生产预检进展，无 console error、无横向溢出。
