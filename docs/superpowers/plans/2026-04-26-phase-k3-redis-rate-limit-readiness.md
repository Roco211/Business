# Phase K3：Redis 限流与生产稳定性补强

## 背景

K1 已完成 RBAC，K2 已完成 PostgreSQL 与生产安全配置预检。当前限流仍是单进程 in-memory，适合单容器试运行，但多进程/多容器正式生产会失效。K3 将限流后端抽象为 in-memory / Redis 两种模式，并在 production readiness 中把 Redis-backed 限流纳入门禁。

## 目标

1. 支持 `APP_RATE_LIMIT_BACKEND=memory|redis`。
2. local-demo 默认继续使用 memory，避免增加本地开发复杂度。
3. `APP_ENV=production` 且启用限流时，必须使用 Redis backend 才能 readiness ready。
4. Redis limiter 不在响应、日志、readiness 中输出 `REDIS_URL` 原文或密码。
5. H5“试运行验收”页展示 K3 Redis 限流已纳入生产门禁。

## 安全边界

- 不读取 `.env` 内容。
- 不输出 Redis URL、密码、token、secret。
- 不要求本地/Docker demo 必须启动真实 Redis；测试用 fake Redis client 验证算法。
- Redis 不可用时生产 readiness degraded，不假装 ready。

## TDD 契约

新增/扩展测试：

1. `test_redis_rate_limiter_allows_until_limit_then_blocks`
   - 使用 fake Redis client。
   - 第 1、2 次 allow，第 3 次 block。
   - 验证 key 带前缀但不包含敏感 URL。

2. `test_create_rate_limiter_uses_redis_backend_when_configured`
   - `APP_RATE_LIMIT_BACKEND=redis`。
   - `create_rate_limiter(settings)` 返回 RedisRateLimiter。

3. `test_readiness_endpoint_degrades_production_when_rate_limit_uses_memory_backend`
   - `APP_ENV=production` + PostgreSQL + 安全配置 + `APP_RATE_LIMIT_BACKEND=memory`。
   - 期望 `checks.rate_limit_backend.status == degraded`。

4. `test_readiness_endpoint_reports_ready_for_production_redis_rate_limit_backend`
   - 同上但 `APP_RATE_LIMIT_BACKEND=redis`。
   - 期望 `checks.rate_limit_backend.status == ready`。

## 涉及文件

- `backend/app/core/config.py`
  - Settings 增加 `rate_limit_backend`。

- `backend/app/core/production_middleware.py`
  - 新增 `RedisRateLimiter`、`create_rate_limiter(settings)`。
  - 现有 middleware 依赖通用 limiter 协议。

- `backend/app/main.py`
  - 使用 `create_rate_limiter(settings)`。

- `backend/app/services/system_readiness.py`
  - 新增 `rate_limit_backend` readiness check。

- `backend/tests/test_production_readiness_config.py`
  - Redis limiter 与 factory 测试。

- `backend/tests/test_system_readiness_api.py`
  - production readiness rate limit backend 测试。

- `apps/h5/src/App.tsx`
  - 商用验收页增加 K3 Redis 限流状态。

## 验收命令

```bash
cd /root/business-clone
python3 -m compileall -q backend/app
PYTHONPATH=backend pytest backend/tests/test_production_readiness_config.py -q
PYTHONPATH=backend pytest backend/tests/test_system_readiness_api.py -q
PYTHONPATH=backend pytest backend/tests/test_v2_identity_context.py -q
PYTHONPATH=backend pytest backend/tests/test_v2_pc_dashboard_overview_http_flow.py -q backend/tests/test_v2_commercial_modules_http_flow.py -q backend/tests/test_v2_chat_http_confirmation_flow.py -q
cd apps/h5 && npm run build
cd /root/business-clone && git diff --check
```

## Docker / 浏览器验收

- 复制后端变更文件与 H5 dist 到 `business-backend`。
- 重启容器。
- `/api/v2/health` 返回 200。
- 浏览器登录 8001，进入“试运行验收”，确认页面出现 `Redis限流` / `K3` 信息，console error 为 0，无横向溢出。
