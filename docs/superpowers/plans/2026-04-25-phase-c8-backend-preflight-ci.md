# Phase C8 — Backend Preflight / CI 门禁固化

日期：2026-04-25
分支：hermes/ai-native-saas-rewrite

## 目标

C1-C7 已经补齐 Business V2 后端的核心边界：

- 正式 stock-in / stock-out API 回归
- Inventory 查询侧 tenant/shop/active 过滤
- Dashboard / Analytics 聚合隔离
- 商品主数据 CRUD + soft delete
- 单商品审计轨迹 API
- Chat / Voice / Photo 的 confirmation-first 人机确认边界
- Docker 后端验收脚本

C8 的目标是把这些后端回归固化成标准门禁，避免后续接真实 Provider 或前端时破坏既有后端能力。

## 新增脚本

新增：

- `backend/scripts/run_backend_preflight.sh`

默认执行：

1. `python3 -m compileall -q backend/app backend/tests backend/scripts`
2. 核心 pytest 回归：
   - `backend/tests/test_v2_inventory_item_audit_http_flow.py`
   - `backend/tests/test_v2_inventory_item_crud_http_flow.py`
   - `backend/tests/test_v2_inventory_query_isolation_http_flow.py`
   - `backend/tests/test_v2_inventory_stock_in_http_flow.py`
   - `backend/tests/test_v2_inventory_stock_out_http_flow.py`
   - `backend/tests/test_v2_dashboard_analytics_isolation_http_flow.py`
   - `backend/tests/test_v2_chat_http_confirmation_flow.py`
   - `backend/tests/test_v2_voice_photo_http_confirmation_flow.py`
   - `backend/tests/test_v2_chat_confirmation_first.py`

默认不跑 Docker acceptance，便于本地快速验证和 CI 执行。

启用 Docker acceptance：

```bash
RUN_DOCKER_ACCEPTANCE=1 bash backend/scripts/run_backend_preflight.sh
```

## 环境默认值

脚本默认使用 mock provider：

- `APP_RUNTIME_MODE=local-demo`
- `LLM_PROVIDER=mock`
- `ASR_PROVIDER=mock`
- `OCR_PROVIDER=mock`
- `VISION_PROVIDER=mock`
- `LLM_ALLOW_MOCK_FALLBACK=1`

不依赖真实 LLM/ASR/OCR/Vision 凭证，不读取 `.env`。

## GitHub Actions

新增：

- `.github/workflows/backend-preflight.yml`

触发条件：

- push 到：
  - `main`
  - `ai-native-saas-rewrite`
  - `hermes/ai-native-saas-rewrite`
  - `codex/ai-native-saas-rewrite`
- pull_request 到上述分支

CI 行为：

1. Checkout
2. Setup Python 3.10
3. 安装 `backend/requirements.txt`
4. 执行：

```bash
bash backend/scripts/run_backend_preflight.sh
```

CI 默认 `RUN_DOCKER_ACCEPTANCE=0`，避免 GitHub Actions 里跑 Docker acceptance 时间过长或受宿主环境影响。

## 本地验证

红灯：

```bash
test -f backend/scripts/run_backend_preflight.sh && test -f .github/workflows/backend-preflight.yml
```

结果：

- exit 1，原因：两个目标文件尚不存在

脚本结构验证：

```bash
chmod +x backend/scripts/run_backend_preflight.sh
bash -n backend/scripts/run_backend_preflight.sh
python3 - <<'PY'
from pathlib import Path
p = Path('.github/workflows/backend-preflight.yml')
text = p.read_text()
required = [
    'Backend Preflight',
    'actions/checkout@v4',
    'actions/setup-python@v5',
    'backend/scripts/run_backend_preflight.sh',
    'LLM_PROVIDER: mock',
]
missing = [s for s in required if s not in text]
if missing:
    raise SystemExit(f'missing workflow markers: {missing}')
print('workflow markers ok')
PY
```

结果：

- `workflow markers ok`

非 Docker preflight：

```bash
RUN_DOCKER_ACCEPTANCE=0 bash backend/scripts/run_backend_preflight.sh
```

结果：

- `22 passed in 46.48s`
- `preflight passed`

完整 preflight + Docker acceptance：

```bash
RUN_DOCKER_ACCEPTANCE=1 bash backend/scripts/run_backend_preflight.sh
```

结果：

- 核心 pytest：`22 passed in 46.28s`
- Docker Health OK
- Alembic version：`20260419_05`
- Table count：`40`
- Phase 8：`8/8 passed`
- Phase 9：`5/5 passed`
- Phase 10：`6/6 tests passed`
- `All tests PASSED`
- `preflight passed`

## 安全边界

- 不提交 `backend/.env`
- 不提交 `backend/aism-dev.db`
- CI 使用 mock provider，不需要任何 secret
- Docker acceptance 仍保留为显式 opt-in，本地/发布前可手动开启

## 后续建议

下一阶段建议 Phase C9：真实 Provider trial preflight。

C8 已经把后端业务边界变成一键门禁，C9 可以在不破坏 mock/CI 的前提下，新增一个只做 readiness 的 trial preflight，验证真实 Provider 配置是否齐备，但仍不提交任何凭证。
