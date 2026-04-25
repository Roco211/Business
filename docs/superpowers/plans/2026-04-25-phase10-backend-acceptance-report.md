# Business V2 Phase 10 后端验收收口报告

日期：2026-04-25
项目路径：/root/business-clone
后端路径：/root/business-clone/backend
服务地址：http://localhost:8001

## 本轮目标

按推进计划优先完成后端验收闭环，不推进前端：

1. 统一 V2 验收脚本认证流程。
2. 补齐库存 stock-in / stock-out API 闭环。
3. 修复容器内 stock_checks 缺表问题。
4. 增强 mock/rule-based 聊天意图识别。
5. 跑通 Phase 8 / Phase 9 / Phase 10 三套验收脚本。

## 已完成事项

### 1. 多 agent 并行排查

已使用 multi-agent 并行拆解：

- Agent A：排查 Phase 8/9/10 认证流程漂移。
- Agent B：排查 v2_stock_check_records 容器缺表和 Alembic migration 方案。
- Agent C：排查库存正式 stock-in API 最小闭环实现方案。

主会话负责整合、实现和验收。

### 2. 统一 V2 测试客户端

新增文件：

- backend/scripts/v2_test_client.py

能力：

- demo phone-code 登录。
- 自动兼容 accessToken / access_token。
- 自动读取 tenant / shop。
- 自动调用 /api/v2/context/select。
- 自动设置 Authorization 与 X-Context-Token。

已改造：

- backend/scripts/test_phase8_acceptance.py
- backend/scripts/test_phase9_scenarios.py

### 3. 正式库存入库 API

新增正式 API：

- POST /api/v2/inventory/stock-in

相关修改：

- backend/app/contracts/v2/inventory.py
- backend/app/api/v2/routes/inventory.py
- backend/app/services/v2_inventory.py

行为：

- 支持 inventory_item_id 或 item_name 定位商品。
- 校验入库数量必须大于 0。
- 写入 v2_inventory_ledger_events。
- 更新 v2_inventory_stock_snapshots。
- 返回 item / snapshot / event 信息。

Phase 10 E2E 已从 correction 伪装入库改为正式 stock-in + stock-out 闭环。

### 4. stock_checks migration

新增 migration：

- backend/alembic/versions/20260419_05_create_v2_stock_check_records.py

并在模型导出中补充：

- backend/app/models/__init__.py

容器内已执行 migration，并验证：

- /app/aism-dev.db 已存在 v2_stock_check_records。
- alembic_version 为 20260419_05。

### 5. 聊天意图规则增强

修改：

- backend/app/services/v2_llm.py

增强 mock/rule-based parser：

- “进50个测试扳手” -> stock_in / 扳手 / 50
- “出了10个测试扳手” -> stock_out / 扳手 / 10
- “今天卖了5个扳手” -> stock_out / 扳手 / 5

容器已同步并重启。

## 验收结果

### 编译检查

命令：

python3 -m compileall -q app scripts test_e2e_phase10.py && echo COMPILE_OK

结果：

COMPILE_OK

### Phase 8 验收

命令：

python3 scripts/test_phase8_acceptance.py

结果：

8/8 passed
PHASE8_EXIT:0

通过模块：

- Health
- Auth
- Tenant Context
- Inventory
- Alerts
- LLM Intent
- Provider Gateways
- Voice/Photo Routes

### Phase 9 场景测试

命令：

python3 scripts/test_phase9_scenarios.py

结果：

5/5 passed
PHASE9_EXIT:0

通过场景：

- Chat Standard
- Chat SSE
- Catalog
- Ledger
- Alerts

### Phase 10 E2E 测试

命令：

python3 test_e2e_phase10.py

结果：

6/6 tests passed
PHASE10_EXIT:0

通过模块：

- T3 Inventory CRUD
- T4 Chat Scenarios
- T5 Stock Check
- T6 Purchase Suggestions
- T7 Dashboard

关键验证点：

- 正式 stock-in 可入库。
- stock-out 可出库。
- 最终库存变更正确。
- S1 入库聊天场景识别为 stock_in 并执行成功。
- S2 出库聊天场景识别为 stock_out 并执行成功。
- 盘点记录可创建和处理。
- 进货建议可返回。

### 代码格式检查

命令：

git diff --check -- backend/app/api/v2/routes/inventory.py backend/app/contracts/v2/inventory.py backend/app/services/v2_inventory.py backend/app/services/v2_llm.py backend/app/models/__init__.py backend/scripts/test_phase8_acceptance.py backend/scripts/test_phase9_scenarios.py backend/scripts/v2_test_client.py backend/alembic/versions/20260419_05_create_v2_stock_check_records.py backend/test_e2e_phase10.py

结果：无 trailing whitespace / whitespace error。

## 当前状态结论

Business V2 后端 Phase 8 / Phase 9 / Phase 10 当前已形成可重复验收基线：

- Phase 8 acceptance：全绿。
- Phase 9 scenarios：全绿。
- Phase 10 E2E：全绿。

可以进入下一阶段后端落地工作：

1. 收敛当前大量未提交改动，做一次代码审查和分组提交。
2. 把 stock-in / stock-check migration 的容器同步方式固化到标准启动流程，避免手工 docker cp。
3. 继续推进真实 ASR/OCR/Vision Provider 产品化接入。
4. 开始补充更严格的库存幂等、并发、异常用例。
5. 后端稳定后再恢复前端对接。
