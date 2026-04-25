# Phase B8: 脏状态审计与 Phase10 后端基线收口

日期：2026-04-25
项目路径：/root/business-clone
分支：hermes/ai-native-saas-rewrite

## 目标

Phase B7 之后，仓库仍存在大量未提交改动。本阶段目标不是继续堆新功能，而是：

1. 审计当前 git 脏状态。
2. 区分不可提交文件、可形成业务基线的代码、仍需后续验证的配置改动。
3. 验证 Phase10/采购/盘点相关后端能力是否可作为一个阶段基线提交。
4. 只提交明确安全的代码、脚本和文档，排除 `.env` 与本地 SQLite 数据库。

## 脏状态分类

### 明确不提交

- `backend/.env`
  - 包含本地运行配置/潜在凭证，不能提交。
- `backend/aism-dev.db`
  - 本地 SQLite demo 数据库，会被测试脚本改变，不作为代码事实源提交。

### 纳入 Phase10 后端基线的代码

库存正式入库 API：

- `backend/app/api/v2/routes/inventory.py`
- `backend/app/contracts/v2/inventory.py`
- `backend/app/services/v2_inventory.py`

盘点能力：

- `backend/app/models/v2_inventory.py`
- `backend/app/models/__init__.py`
- `backend/alembic/versions/20260419_05_create_v2_stock_check_records.py`
- `backend/app/api/v2/routes/stock_checks.py`
- `backend/app/services/v2_stock_check.py`

进货建议能力：

- `backend/app/api/v2/routes/purchase.py`
- `backend/app/services/v2_purchase.py`
- `backend/app/api/v2/router.py`

验收脚本与测试客户端：

- `backend/scripts/v2_test_client.py`
- `backend/scripts/test_phase8_acceptance.py`
- `backend/scripts/test_phase9_scenarios.py`
- `backend/test_e2e_phase10.py`

LLM/Provider 与 demo 运行配置相关代码：

- `backend/app/services/v2_llm.py`
- `backend/app/services/llm_real_provider.py`
- `backend/app/core/config.py`
- `backend/requirements.txt`
- `backend/test_phase8_llm.py`
- `backend/test_provider_config.py`

身份响应契约 camelCase 对齐：

- `backend/app/api/v2/routes/identity.py`
- `backend/app/contracts/v2/identity.py`

服务入口/Docker 运行相关：

- `backend/app/main.py`
- `backend/Dockerfile`
- `backend/app/api/v2/routes/voice.py`

### 文档

- `docs/superpowers/plans/2026-04-25-current-project-audit-and-roadmap.md`
- `docs/superpowers/plans/2026-04-25-phase10-backend-acceptance-report.md`
- `docs/superpowers/plans/2026-04-25-phase-b8-dirty-state-audit-and-phase10-baseline.md`

## 验证命令与结果

### 编译检查

命令：

```bash
PYTHONPATH=backend python3 -m compileall -q backend/app backend/scripts backend/test_e2e_phase10.py backend/test_provider_config.py backend/test_phase8_llm.py && echo COMPILE_OK
```

结果：

```text
COMPILE_OK
```

### 后端健康检查

临时启动服务：

```bash
cd /root/business-clone/backend
PYTHONPATH=. python3 -c 'import uvicorn; uvicorn.run("app.main:app", host="127.0.0.1", port=8001, log_level="warning")'
```

健康检查结果：

```text
200 {"data":{"status":"ok","api_version":"v2"}}
```

### Phase 8 验收

命令：

```bash
python3 backend/scripts/test_phase8_acceptance.py
```

结果：

```text
Total: 8/8 passed
```

通过模块：

- Health
- Auth
- Tenant Context
- Inventory
- Alerts
- LLM Intent
- Provider Gateways
- Voice/Photo Routes

### Phase 9 场景脚本

命令：

```bash
python3 backend/scripts/test_phase9_scenarios.py
```

结果：

```text
Total: 5/5 passed
```

通过模块：

- Chat Standard
- Chat SSE
- Catalog
- Ledger
- Alerts

### Phase 10 E2E

命令：

```bash
python3 backend/test_e2e_phase10.py
```

结果：

```text
Total: 6/6 tests passed
All tests PASSED!
```

通过模块：

- Inventory CRUD
- Chat Scenarios
- Stock Check
- Purchase Suggestions
- Dashboard

## 结论

当前 Phase10 后端基线可提交，原因：

1. 编译通过。
2. 服务可启动，V2 health 正常。
3. Phase 8 / Phase 9 / Phase 10 三层验收均通过。
4. 盘点、进货建议、正式 stock-in API、统一 V2 测试客户端形成闭环。
5. `.env` 与本地 SQLite 数据库已明确排除，不进入提交。

## 后续建议

1. 下一阶段继续做 Phase B9：清理或隔离剩余本地运行状态，检查是否还有非代码生成物需要加入 `.gitignore`。
2. 将 Phase10 E2E 中的脚本式测试逐步转为 pytest，减少依赖本地长期运行数据库。
3. 对 `POST /api/v2/inventory/stock-in` 补 pytest 级单测/HTTP 测试，进一步收敛正式库存 API 的回归保护。
4. 后端基线稳定后，再考虑真实 ASR/OCR/Vision Provider 产品化接入。
