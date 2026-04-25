# Phase C9/C10 — Provider Trial Preflight 与后端 Readiness 收尾

日期：2026-04-25
分支：hermes/ai-native-saas-rewrite

## 背景

C1-C8 已完成：

- Inventory stock-in / stock-out 正式 API 回归
- Inventory 查询侧 tenant/shop/active 隔离
- Dashboard / Analytics 聚合隔离
- 商品 CRUD + soft delete
- 单商品 audit trail API
- Docker acceptance 一键脚本
- Backend preflight + GitHub Actions 门禁

C9/C10 的目标是完成后端收尾：

1. 增加真实 LLM Provider trial preflight。
2. 保持默认 CI/mock 模式安全，不依赖真实凭证。
3. 增加最终后端 readiness summary，确认后端核心门禁文件齐备。

## C9：Provider Trial Preflight

新增脚本：

```bash
python3 backend/scripts/run_provider_trial_preflight.py
```

默认行为：

- 只读取当前进程环境变量。
- 不导入 `app.core.config`。
- 不隐式加载 `backend/.env`。
- 不输出 API key、Authorization header、请求体或响应体。
- 不执行真实网络调用。

支持的 LLM 配置变量：

- `LLM_PROVIDER`
- `LLM_PROVIDER_API_URL` 或 `LLM_API_URL` 或 `VOLCANO_API_URL`
- `LLM_PROVIDER_API_KEY` 或 `LLM_API_KEY` 或 `VOLCANO_API_KEY`
- `LLM_PROVIDER_MODEL` 或 `LLM_MODEL` 或 `VOLCANO_MODEL`
- `LLM_TIMEOUT_SECONDS`
- `LLM_MAX_TOKENS`
- `LLM_TEMPERATURE`

启用真实网络探测必须显式设置：

```bash
RUN_REAL_PROVIDER_TRIAL=1 python3 backend/scripts/run_provider_trial_preflight.py
```

C8 preflight 集成方式：

```bash
RUN_PROVIDER_TRIAL_PREFLIGHT=1 RUN_REAL_PROVIDER_TRIAL=0 bash backend/scripts/run_backend_preflight.sh
```

如果需要真实 Provider 网络探测：

```bash
RUN_PROVIDER_TRIAL_PREFLIGHT=1 RUN_REAL_PROVIDER_TRIAL=1 bash backend/scripts/run_backend_preflight.sh
```

注意：真实探测需要调用外部 Provider，只有在用户明确提供并导出凭证后才运行。

## C10：Backend Readiness Summary

新增脚本：

```bash
python3 backend/scripts/run_backend_readiness_summary.py
```

检查核心后端门禁文件：

- `backend/scripts/run_backend_preflight.sh`
- `backend/scripts/run_docker_backend_acceptance.sh`
- `backend/scripts/run_provider_trial_preflight.py`
- `.github/workflows/backend-preflight.yml`
- `backend/tests/test_v2_inventory_item_audit_http_flow.py`
- `backend/tests/test_v2_inventory_item_crud_http_flow.py`
- `backend/tests/test_provider_trial_preflight.py`

全部存在时输出 `overall_status=ready`。

## 安全边界

- 本阶段未读取 `backend/.env`。
- 本阶段未提交 `backend/.env`。
- 本阶段未提交 `backend/aism-dev.db`。
- Provider preflight 输出只显示 `api_key_present=yes/no`，不显示真实 key。
- CI 默认 `RUN_PROVIDER_TRIAL_PREFLIGHT=0`，不触碰真实 Provider。
- 即使启用 Provider preflight，默认 `RUN_REAL_PROVIDER_TRIAL=0`，只做配置结构检查。

## 验证记录

Provider preflight 红绿测试：

```bash
PYTHONPATH=backend pytest -q backend/tests/test_provider_trial_preflight.py
```

结果：

- `2 passed in 0.06s`

Backend readiness summary 红绿测试：

```bash
PYTHONPATH=backend pytest -q backend/tests/test_backend_readiness_summary.py
```

结果：

- `2 passed in 0.04s`

默认 preflight：

```bash
RUN_DOCKER_ACCEPTANCE=0 RUN_PROVIDER_TRIAL_PREFLIGHT=0 bash backend/scripts/run_backend_preflight.sh
```

结果：

- `26 passed in 48.56s`
- readiness summary: `overall_status=ready`, `ready_count=7`, `missing_count=0`
- Provider trial preflight skipped
- Docker acceptance skipped
- preflight passed

Provider trial dry-run preflight：

```bash
LLM_PROVIDER=volcano \
LLM_PROVIDER_API_URL=https://ark.cn-beijing.volces.com/api/v3/chat/completions \
LLM_PROVIDER_API_KEY=[REDACTED] \
LLM_PROVIDER_MODEL=ep-20260416043519-v4vzq \
RUN_PROVIDER_TRIAL_PREFLIGHT=1 \
RUN_REAL_PROVIDER_TRIAL=0 \
RUN_DOCKER_ACCEPTANCE=0 \
bash backend/scripts/run_backend_preflight.sh
```

结果：

- `26 passed in 48.68s`
- readiness summary: `overall_status=ready`, `ready_count=7`, `missing_count=0`
- Provider preflight 输出 `api_key_present=yes`
- `network_trial=skipped`
- `overall_status=ready`
- preflight passed

完整 Docker preflight：

```bash
RUN_DOCKER_ACCEPTANCE=1 RUN_PROVIDER_TRIAL_PREFLIGHT=0 bash backend/scripts/run_backend_preflight.sh
```

结果：

- 核心 pytest：`26 passed in 45.87s`
- readiness summary: `overall_status=ready`, `ready_count=7`, `missing_count=0`
- Docker health OK
- Alembic version: `20260419_05`
- Table count: `40`
- Phase 8: `8/8 passed`
- Phase 9: `5/5 passed`
- Phase 10: `6/6 tests passed`
- Docker backend acceptance passed
- preflight passed

## 当前后端结论

Business V2 后端当前已具备：

- 核心库存写操作安全边界
- 查询侧多租户/门店隔离
- 商品主数据 CRUD + soft delete
- 单商品 audit trail
- Dashboard 聚合隔离
- Chat/Voice/Photo confirmation-first
- Docker acceptance
- GitHub Actions 后端门禁
- 真实 Provider trial preflight 的安全 opt-in 入口

下一阶段如果继续推进，应进入 Phase D：前端真实 API 接入，而不是继续补后端基础设施。
