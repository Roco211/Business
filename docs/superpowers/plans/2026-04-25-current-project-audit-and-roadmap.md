# 当前项目全面排查与推进计划

日期：2026-04-25
分支：`hermes/ai-native-saas-rewrite`
范围：Business 项目后端优先推进，不推进前端；以 CLI/API 验证为主。

## 1. 总体结论

当前项目已经具备 V2 后端主体框架：多租户身份、显式执行上下文、库存账本、Chat/SSE、Dashboard、Ledger、Alerts、Voice/Photo mock、LLM Provider 抽象、进货建议和盘点路由雏形都已出现。

但当前状态还不能算“后端完成”，主要原因是：

1. 测试脚本与 API 契约已经漂移：旧测试仍读取 `access_token`，而接口返回 `accessToken`。
2. 数据库迁移链不完整：新增 `V2StockCheckRecord` 模型后，容器内 SQLite 缺少 `v2_stock_check_records` 表。
3. 入库/出库能力仍不完整：存在 correction 和 stock-out，但缺少标准 `POST /inventory/stock-in`；Chat 的 stock_in/stock_out 仍有绕过确认/任务状态机的风险。
4. LLM真实接入已有基础，但 `.env` 当前仍以 OpenRouter/free 或 mock 为主，ASR/OCR/Vision 仍是 mock。
5. Docker 容器内数据库与宿主机数据库不同步，导致“本地创建表成功、服务仍报缺表”。
6. 业务测试仍存在“测试本身错误”与“业务实现缺口”混在一起的问题，必须先统一验收脚本，再继续功能开发。

因此下一步不建议立即推进前端，也不建议继续堆新功能。建议先进入“后端收口 Sprint”，目标是把 V2 后端稳定到 CLI 验收全绿。

## 2. 当前工作区状态

`git status --short` 显示当前有未提交改动：

- 已修改：
  - `backend/.env`
  - `backend/Dockerfile`
  - `backend/aism-dev.db`
  - `backend/app/api/v2/router.py`
  - `backend/app/api/v2/routes/identity.py`
  - `backend/app/api/v2/routes/voice.py`
  - `backend/app/contracts/v2/identity.py`
  - `backend/app/core/config.py`
  - `backend/app/main.py`
  - `backend/app/models/v2_inventory.py`
  - `backend/app/services/llm_real_provider.py`
  - `backend/app/services/v2_llm.py`
  - `backend/requirements.txt`
  - `backend/test_phase8_llm.py`
- 新增未跟踪：
  - `backend/app/api/v2/routes/purchase.py`
  - `backend/app/api/v2/routes/stock_checks.py`
  - `backend/app/services/v2_purchase.py`
  - `backend/app/services/v2_stock_check.py`
  - `backend/test_e2e_phase10.py`
  - `backend/test_provider_config.py`

风险：当前改动没有形成一个清晰提交边界，且包含 `.env`、SQLite 数据库、测试脚本和业务代码混合修改。后续应先整理为几个明确提交或至少明确变更清单。

## 3. 已验证情况

### 3.1 代码导入与语法

命令：

```bash
cd /root/business-clone/backend
python3 -m compileall -q app scripts test_e2e_phase10.py test_provider_config.py test_phase8_llm.py
```

结果：通过。

### 3.2 FastAPI 路由加载

`app.main` 可导入，当前应用加载约 95 条路由，其中 V2 核心路由包括：

- `POST /api/v2/auth/login`
- `GET /api/v2/me/tenants`
- `POST /api/v2/context/select`
- `GET /api/v2/inventory/items`
- `GET /api/v2/inventory/stock`
- `POST /api/v2/inventory/corrections`
- `POST /api/v2/inventory/stock-out`
- `POST /api/v2/chat`
- `POST /api/v2/chat/stream`
- `GET /api/v2/dashboard/summary`
- `GET /api/v2/purchase/suggestions`
- `POST /api/v2/stock-checks`

### 3.3 当前容器服务状态

Docker 容器 `business-backend` 正在运行，端口映射：`8001 -> 8001`。

`/api/v2/health` 返回正常：

```json
{"data":{"status":"ok","api_version":"v2"}}
```

### 3.4 现有测试结果

#### Phase 8 验收脚本

命令：

```bash
cd /root/business-clone/backend
python3 scripts/test_phase8_acceptance.py
```

结果：5/8 通过。

失败项：

- Tenant Context：测试脚本读取 `access_token` 失败。
- Inventory：同上。
- Alerts：同上。

判断：这主要是测试脚本未适配 camelCase 响应字段，不一定是业务 API 坏了。

#### Phase 9 场景脚本

命令：

```bash
cd /root/business-clone/backend
python3 scripts/test_phase9_scenarios.py
```

结果：0/5 通过。

失败原因：同样集中在测试脚本读取 `access_token`，而实际响应为 `accessToken`。

判断：优先修测试适配，不要先误判为业务回归。

#### 新增 Phase 10 E2E 脚本

命令：

```bash
cd /root/business-clone/backend
python3 test_e2e_phase10.py
```

结果：4/6 通过。

通过：

- 认证 + Context
- Chat 场景部分
- Purchase Suggestions
- Dashboard + Alerts

失败：

- Inventory CRUD：correction 发生库存并发冲突。
- Stock Check：容器内缺少 `v2_stock_check_records` 表。

判断：Phase 10 脚本比旧脚本更接近真实 V2 认证流程，但仍需修正数据读取字段和测试设计。

## 4. 关键问题清单

### P0-1：测试契约漂移

现象：

- 登录接口返回：`accessToken`、`refreshToken`、`accountId`。
- 旧验收脚本读取：`access_token`。

影响：

- Phase 8 / Phase 9 历史验收脚本大面积失败。
- 无法区分真实回归与测试脚本过期。

建议：

- 抽出统一测试客户端，例如 `backend/scripts/v2_test_client.py`。
- 同时兼容 snake_case 和 camelCase。
- 标准化认证流程：login → me/tenants → tenant shops → context/select → 设置 `Authorization` + `X-Context-Token`。

### P0-2：数据库迁移缺口

现象：

- 宿主机 `backend/aism-dev.db` 已有 `v2_stock_check_records`。
- Docker 容器 `/app/aism-dev.db` 缺少 `v2_stock_check_records`。
- API 调用 `POST /api/v2/stock-checks` 报 `no such table: v2_stock_check_records`。

原因：

- 新增 ORM 模型后没有对应 Alembic 迁移。
- 宿主机和容器数据库不是同一个文件或未同步。

建议：

- 新增 Alembic migration：创建 `v2_stock_check_records` 表。
- 容器启动/测试前执行迁移或重建 demo DB。
- 明确 SQLite demo DB 不应作为长期事实源提交；应由迁移 + bootstrap 脚本重建。

### P0-3：库存操作 API 不完整

现状：

- 有 `POST /api/v2/inventory/corrections`。
- 有 `POST /api/v2/inventory/stock-out`。
- 没有标准 `POST /api/v2/inventory/stock-in`。
- `commit_v2_inventory_stock_in()` 依赖 `task_run_id`，更偏向确认流后落账。

影响：

- CLI/E2E 中只能用 correction 模拟入库，不符合业务语义。
- Chat stock_in/stock_out 容易绕过“AI 不直接修改业务真相”的架构原则。

建议：

- 先设计入库 API 的安全边界：直接 demo 落账还是必须创建 confirmation。
- MVP demo 可允许“低风险明确输入直接落账”，但必须写入 ledger 并保留审计；商业版应走 task_run + confirmation。
- 增加 `POST /api/v2/inventory/stock-in` 或 `POST /api/v2/inventory/stock-adjustments`，不要滥用 correction。

### P0-4：规则意图解析不完整

现象：

本地 mock 模式测试：

- `进50个测试扳手` → `unknown`
- `出了10个测试扳手` → `unknown`
- `今天营业额多少` → `revenue_query`
- `热销商品排行` → `sales_query`
- `库存预警` → `alert_query`

原因：

- 规则引擎对“进 + 数量 + 商品”“出 + 数量 + 商品”的口语化表达覆盖不足。

影响：

- 不配置真实 LLM 时，S1/S2 Chat 场景不稳定。
- Demo 模式下店主最常用的“进货/卖货”表达无法被识别。

建议：

- 补强 `v2_llm.py` 规则优先路径。
- 增加中文数量抽取测试：`进50个黄色手枪钻`、`来了20把锤子`、`卖了5个电钻`、`出了10个扳手`。

### P1-1：LLM Provider 配置已可用但还未产品化

现状：

- `llm_real_provider.py` 已支持 OpenAI-compatible Provider。
- 已增强 Volcano/OpenRouter 默认配置。
- 真实 OpenRouter 调用此前可通过，但延迟波动较大。
- 火山引擎仍需要真实 API Key 与 Endpoint ID。

建议：

- 继续保留 mock fallback。
- 增加 `/internal/worker-health` 或 readiness 中对 LLM provider 状态的显式展示。
- 火山引擎接入后做 latency benchmark。

### P1-2：ASR/OCR/Vision 仍是 mock

现状：

- Voice/Photo/Receipt 路由存在。
- Provider gateway/mocks 存在。
- 真实 provider 是否完整可用需要单独校验。

建议：

- 不阻塞后端业务闭环。
- 在库存/账本/确认流稳定后，再逐个切换真实 provider。

### P1-3：Chat Session 仍偏临时

文档显示 Phase 9 使用内存 ChatSession。架构原则要求关键事实可审计、可回放。

建议：

- 短期接受内存 session 用于演示。
- 中期迁移到 `V2ConversationSession` + `V2Message` 持久化。

## 5. 推荐推进路线

### Sprint A：验收脚本与运行环境收口（最高优先级）

目标：把“测试坏”和“业务坏”分离，让后续每一步都有可信验收。

任务：

1. 创建统一测试客户端：`backend/scripts/v2_test_client.py`
   - 登录支持 `accessToken` / `access_token`。
   - 自动选择 tenant/shop。
   - 自动设置 `Authorization` 和 `X-Context-Token`。
2. 修复以下脚本使用统一客户端：
   - `backend/scripts/test_phase8_acceptance.py`
   - `backend/scripts/test_phase9_scenarios.py`
   - `backend/test_e2e_phase10.py`
3. 将 Phase 10 测试放入 `backend/scripts/`，避免根目录散落测试文件。
4. 明确 API 返回字段规范：建议外部 API 统一 camelCase，测试客户端内部做兼容。
5. 验收：
   - Phase 8 脚本不再因 token 字段失败。
   - Phase 9 脚本不再因 token 字段失败。
   - Phase 10 输出能明确区分功能失败。

预计工作量：0.5 天。

### Sprint B：数据库迁移与 Demo 数据重建

目标：消除容器/宿主机数据库不一致和缺表问题。

任务：

1. 新增 Alembic migration：`v2_stock_check_records`。
2. 检查 `alembic/env.py` 是否导入所有 V2 模型，确保 metadata 完整。
3. 明确 demo DB 重建流程：
   - migration upgrade
   - bootstrap_v2_trial_data
   - optional seed ledger/alerts
4. 不再依赖手工 `create_all` 或手工改 SQLite。
5. 更新 Docker 启动/测试说明：容器内 DB 需要迁移。

验收：

- 容器内 `/app/aism-dev.db` 包含 `v2_stock_check_records`。
- `POST /api/v2/stock-checks` 成功。
- Phase 10 Stock Check 通过。

预计工作量：0.5 天。

### Sprint C：库存入库/出库业务闭环

目标：完成后端最核心的“进销存”业务动作，不靠 correction 冒充入库。

任务：

1. 设计并实现 `POST /api/v2/inventory/stock-in`：
   - 输入：`inventory_item_id` 或 `item_name`、quantity、unit、price、reason。
   - 输出：event_id、inventory_item_id、new_quantity。
   - 行为：创建或更新 snapshot，写 ledger event。
2. 修正 `POST /api/v2/inventory/stock-out` 测试字段：
   - 使用 `inventory_item_id`、`expected_quantity`、`stock_out_quantity`、`reason`。
3. 明确 correction 只用于盘点纠偏，不用于普通入库。
4. 补齐并发冲突测试：expected_quantity 不匹配返回 409。
5. 保证所有 mutation 都按 `tenant_id + shop_id` 限定。

验收：

- 入库后库存增加。
- 出库后库存减少。
- Ledger 能查到 stock_in / stock_out 事件。
- Phase 10 Inventory CRUD 通过。

预计工作量：1 天。

### Sprint D：Chat S1/S2/S4/S5/S6/S7 真实业务闭环

目标：让 AI 对话真正驱动业务场景，但不违反“AI 不能直接修改业务真相”的原则。

任务：

1. 补强 `v2_llm.py` mock/rule 意图解析：
   - `进50个测试扳手` → stock_in
   - `出了10个测试扳手` → stock_out
   - `卖了5个电钻` → stock_out
   - `来了20把锤子` → stock_in
2. Chat stock_in/stock_out 暂按 demo 模式直接调用库存服务，但必须：
   - 记录 ledger。
   - 返回明确的 item、quantity、event_id。
   - 低置信度或缺数量时不落账，进入追问。
3. 中期方案：引入 task_run + confirmation，把 Chat mutation 改为“生成待确认任务”。
4. S4 盘点通过 stock_checks + correction 形成闭环。
5. S5/S6/S7 保持 dashboard/analytics/purchase suggestions 查询式，不做副作用。

验收：

- Chat S1 入库成功，库存增加。
- Chat S2 出库成功，库存减少。
- Chat S3 查询正确。
- Chat S4 创建盘点记录。
- Chat S5/S6/S7 返回真实数据。

预计工作量：1 天。

### Sprint E：Provider 与观测完善

目标：为真实火山引擎接入做好生产化基础。

任务：

1. 清理 `.env`：不要把真实 key 或占位 `***` 混入可运行配置。
2. `.env.example` 明确：
   - OpenRouter 示例
   - Volcano 示例
   - mock fallback 示例
3. LLM/ASR/OCR/Vision readiness 明确显示 provider、mode、fallback 状态。
4. LLM latency benchmark 脚本纳入 scripts。
5. 火山引擎接入时验证 Endpoint ID，而不是模型名。

验收：

- mock 模式 readiness = ready。
- trial 模式无真实 key = degraded 且原因明确。
- 配置真实 key 后 LLM 调用通过。

预计工作量：0.5-1 天。

### Sprint F：后端完成定义与前端交接

目标：在恢复前端之前，后端达到稳定契约。

后端完成标准：

1. Phase 8 acceptance：全通过。
2. Phase 9 scenarios：全通过。
3. Phase 10 E2E：全通过。
4. OpenAPI 文档更新。
5. API contract 文档更新。
6. 所有新增表有 migration。
7. demo bootstrap 可从空 DB 重建完整演示数据。
8. 无需手工修 DB 即可跑通。

达到以上标准后，再进入前端对接。

## 6. 近期建议执行顺序

建议按以下顺序推进：

1. 修复测试客户端和历史验收脚本。
2. 补 Alembic migration，解决 stock_checks 缺表。
3. 新增正式 stock-in API，修复库存闭环。
4. 补强规则意图解析，修复 Chat S1/S2 unknown。
5. 让 Phase 8 / Phase 9 / Phase 10 全绿。
6. 整理 API 文档与 OpenAPI snapshot。
7. 清理未提交改动，形成合理 commit。

## 7. 风险与注意事项

1. 不要继续手工修改容器内 SQLite 作为长期方案；必须迁移化。
2. 不要把 `.env` 中的真实 API Key 提交。
3. 不要在未确认风险边界前让 AI mutation 绕过确认流进入商业版逻辑。
4. 当前 `backend/aism-dev.db` 已被修改，应决定是否作为 demo fixture 保留，还是从 git 中移除/忽略。
5. 用户已明确：前端在后端完成前不推进；因此前端对接排在后端验收全绿之后。

## 8. 下一步可直接执行的任务包

如果继续执行，建议第一个任务包为：

“后端验收脚本收口 + stock_checks migration”

包含：

- 新建 `backend/scripts/v2_test_client.py`
- 修复 Phase 8/9/10 测试认证流程
- 新增 `v2_stock_check_records` Alembic 迁移
- 更新容器/本地 DB 重建流程
- 跑通到至少：Phase 8/9 不因 token 失败，Phase 10 stock_checks 不再缺表

完成后，再进入库存 stock-in API 和 Chat mutation 闭环。
