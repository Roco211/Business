# Business 商用试运行生产化运行手册（E1-E3）

生成时间：2026-04-25
适用范围：Business PC/H5 + FastAPI 单体容器商用试运行。

## 1. PostgreSQL 部署

推荐使用：

```bash
cd /root/business-clone
POSTGRES_PASSWORD='<强密码>' \
APP_CORS_ORIGINS='https://你的域名' \
HOST_PORT=8001 \
docker compose -f infra/docker/docker-compose.production.yml up -d --build
```

说明：
- API/H5 端口显式绑定 `0.0.0.0:${HOST_PORT:-8001}:8001`，支持外网访问。
- `DATABASE_URL` 在 compose 内部自动使用 `postgresql+psycopg://...@postgres:5432/...`。
- 本地 demo/CI 仍可继续使用 SQLite，不影响现有测试。
- 生产化默认使用 `APP_ENV=production`、`APP_RUNTIME_MODE=trial`。

## 2. CORS 与安全头

关键环境变量：

```bash
APP_CORS_ORIGINS='https://app.example.com,https://admin.example.com'
APP_SECURITY_HEADERS_ENABLED=1
APP_RATE_LIMIT_PER_MINUTE=120
APP_RATE_LIMIT_BACKEND=redis
REDIS_URL='redis://redis:6379/0'
```

已实现：
- CORS 白名单，不配置则不开放跨域；
- `X-Content-Type-Options: nosniff`；
- `X-Frame-Options: DENY`；
- `Referrer-Policy: strict-origin-when-cross-origin`；
- `Permissions-Policy: camera=(), microphone=(), geolocation=()`；
- Redis-backed rate limiting，正式生产多实例通过 Redis 共享限流窗口；本地 demo 可继续使用 `APP_RATE_LIMIT_BACKEND=memory`。

注意：`REDIS_URL` 不会出现在 readiness details 或错误响应中，生产环境启用限流时 readiness 要求 `APP_RATE_LIMIT_BACKEND=redis`。

## 3. 备份与恢复

容器内备份：

```bash
docker compose -f infra/docker/docker-compose.production.yml exec api \
  bash /app/scripts/backup_postgres.sh
```

脚本输出：
- `backup_path=/app/backups/business-postgres-YYYYmmddTHHMMSSZ.dump`
- `checksum_path=/app/backups/business-postgres-YYYYmmddTHHMMSSZ.dump.sha256`

恢复：

```bash
docker compose -f infra/docker/docker-compose.production.yml exec api \
  bash /app/scripts/restore_postgres.sh /app/backups/business-postgres-YYYYmmddTHHMMSSZ.dump
```

恢复脚本会：
- 校验 `DATABASE_URL` 必须是 PostgreSQL；
- 若存在 `.sha256` 文件则先校验；
- 使用 `pg_restore --clean --if-exists` 恢复。

## 4. Provider trial 小流量验证

默认不访问真实 Provider，必须显式 opt-in：

```bash
RUN_PROVIDER_TRIAL_PREFLIGHT=1 \
RUN_REAL_PROVIDER_TRIAL=1 \
TRIAL_PROVIDER_PROFILE='pilot-v1' \
ASR_PROVIDER='real-provider' \
ASR_PROVIDER_API_URL='https://asr.example.com/v1/transcriptions' \
ASR_PROVIDER_API_KEY='[通过进程环境变量注入]' \
OCR_PROVIDER='real-provider' \
OCR_PROVIDER_API_URL='https://ocr.example.com/v1/receipts' \
OCR_PROVIDER_API_KEY='[通过进程环境变量注入]' \
VISION_PROVIDER='real-provider' \
VISION_PROVIDER_API_URL='https://vision.example.com/v1/recognize' \
VISION_PROVIDER_API_KEY='[通过进程环境变量注入]' \
bash backend/scripts/run_backend_preflight.sh
```

安全边界：
- 不读取 `.env`；
- 不在日志/报告输出任何 key/token/secret/password；
- 真实网络调用必须同时开启 `RUN_PROVIDER_TRIAL_PREFLIGHT=1` 和 `RUN_REAL_PROVIDER_TRIAL=1`；
- 建议先只给一个门店设置 `LIVE_PILOT_ALLOWED_SHOP_IDS`。

## 5. 上线前检查清单

- 域名 HTTPS 已配置；
- 云安全组/防火墙只开放必要端口；
- `POSTGRES_PASSWORD` 使用强密码；
- `APP_CORS_ORIGINS` 为真实域名，不使用 `*`；
- `APP_RATE_LIMIT_PER_MINUTE` 已按试运行流量设置；
- `APP_RATE_LIMIT_BACKEND=redis`，且 `REDIS_URL` 指向生产 Redis；
- 备份脚本跑通并下载到异地；
- Provider trial 使用小样本验证，并检查 fallback/低置信率；
- 确认 `.env`、数据库文件、任何凭证没有提交到 Git。
