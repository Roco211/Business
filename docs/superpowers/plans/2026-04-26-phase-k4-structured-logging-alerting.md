# Phase K4 结构化日志与告警基础

## 背景

K1 已完成 RBAC，K2 已完成生产数据库/安全配置 readiness，K3 已完成 Redis-backed 限流 readiness。下一步要让 Business 在真实试运行和正式商用前具备基础可观测性：出错时能通过 request_id 追踪，日志不泄露敏感信息，并预留告警通道。

## 目标

1. 后端请求链路具备结构化日志字段。
2. 每个请求生成或透传 `X-Request-ID`，响应与错误日志一致。
3. 未处理异常响应脱敏，日志也不输出 token/password/secret/API key/连接串。
4. readiness 新增 observability / alerting 配置检查。
5. H5 商用试运行验收页展示 K4 能力。
6. 生产运行手册补充日志与告警配置。

## 非目标

- 本阶段不接入真实飞书/企业微信 webhook。
- 本阶段不搭建 ELK、Loki、Prometheus 等外部日志平台。
- 本阶段不新增复杂告警事件表。
- 本阶段不输出任何真实 webhook URL、token、API key、密码或连接串。

## 设计

### 结构化日志

新增 observability 工具模块，提供：

- `sanitize_for_log(...)`
- `build_request_log_payload(...)`
- `emit_structured_log(...)`
- `MockAlertSender` / `create_alert_sender(...)`

日志 payload 至少包含：

- event
- request_id
- method
- path
- status_code
- latency_ms
- client_ip
- user_agent
- account_id / tenant_id / shop_id（若上下文可安全获取）
- error_code / exception_type（错误场景）

### 脱敏规则

任何 key 或文本包含以下关键词时必须脱敏：

- token
- password
- secret
- api_key
- authorization
- cookie
- database_url
- redis_url
- webhook_url

脱敏值统一为 `[REDACTED]`。

### readiness

新增检查：

- `observability`
- `alerting`

production 下：

- 结构化日志应该启用。
- 告警 webhook 可先不强制 ready，但 readiness 需要明确显示 enabled/configured 状态。
- webhook URL 只显示是否配置，不输出原文。

### H5

“商用试运行验收清单”新增：

- 结构化日志
- Request ID 追踪
- 异常脱敏
- 告警预留

## TDD 验收

1. 请求成功时响应包含 `X-Request-ID`，日志 payload 包含 request_id/path/status_code/latency_ms。
2. 请求失败时 500 响应包含 request_id，不包含 traceback 或敏感值。
3. 日志脱敏函数覆盖 token/password/secret/url 等字段。
4. readiness 包含 observability/alerting，且不输出 webhook URL。
5. H5 build 通过。
6. Docker 热更新后浏览器访问 8001，试运行验收页可见 K4 项，console error 为 0。
