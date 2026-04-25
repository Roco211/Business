# Phase B6: HTTP 级 Voice/Photo Confirmation Approve 闭环验收

日期：2026-04-25

## 背景

Phase B2/B4 已完成 Chat confirmation-first 与 approve 落账闭环；Phase B5 已让 Voice / Photo stock-in SSE 服务层创建真实 pending confirmation。

本阶段目标是把 Voice / Photo 从“服务层可用”提升到“真实 HTTP API 端到端可验收”：

1. 通过 `/api/v2/voice/stock-in` 或 `/api/v2/photo/stock-in` 上传文件。
2. 从 SSE 返回中解析真实 `confirmation_id` / `task_run_id`。
3. 确认 approve 前不写库存账本、不创建库存快照。
4. 调用 `/api/v2/confirmations/{confirmation_id}/approve`，即使 `resolution_payload={}`，也能使用原始 draft payload 落账。
5. 验证 `V2InventoryLedgerEvent` 和 `V2InventoryStockSnapshot` 正确更新。

## TDD 红灯

新增测试文件：

- `backend/tests/test_v2_voice_photo_http_confirmation_flow.py`

覆盖两个 HTTP 级端到端场景：

1. `test_http_voice_stock_in_sse_confirmation_can_be_approved_and_commits_inventory`
2. `test_http_photo_stock_in_sse_confirmation_can_be_approved_and_commits_inventory`

首次运行：

```bash
PYTHONPATH=backend pytest -q backend/tests/test_v2_voice_photo_http_confirmation_flow.py
```

结果：

```text
.F
FAILED test_http_photo_stock_in_sse_confirmation_can_be_approved_and_commits_inventory
TypeError: 'coroutine' object is not iterable
RuntimeWarning: coroutine '_build_sse_stream' was never awaited
```

红灯原因：

`backend/app/api/v2/routes/photo.py` 中 `_build_sse_stream(events)` 定义为 `async def`，调用方没有 `await`，导致传给 `StreamingResponse` 的是 coroutine，而不是 async iterator。

Voice 路由中的同名 helper 是普通 `def`，行为正确。

## 实现变更

### 1. 修复 Photo SSE Stream Builder

文件：

- `backend/app/api/v2/routes/photo.py`

改动：

- 将 `_build_sse_stream(events)` 从 `async def` 改为普通 `def`。
- 保持内部 `async def generate()` 不变。
- 返回 `generate()`，让 `StreamingResponse` 获得真正的 async iterator。

### 2. 新增 HTTP 级端到端测试

文件：

- `backend/tests/test_v2_voice_photo_http_confirmation_flow.py`

测试流程：

1. 使用测试数据库 seed V2 Account / Tenant / Membership / Shop / ShopAccess。
2. 调用 `/api/v2/auth/login` 获取 access token。
3. 调用 `/api/v2/context/select` 获取 `X-Context-Token`。
4. 通过 multipart form 调用：
   - `/api/v2/voice/stock-in`
   - `/api/v2/photo/stock-in`
5. 解析 SSE 文本：
   - `draft_created`
   - `awaiting_confirmation`
   - `complete`
6. 从 `awaiting_confirmation.data` 获取真实 `confirmation_id` / `task_run_id`。
7. 查询 DB，确认 pending confirmation 存在。
8. 确认 approve 前：
   - `V2InventoryLedgerEvent` 不存在。
   - `V2InventoryStockSnapshot` 不存在。
9. 调用：
   - `POST /api/v2/confirmations/{confirmation_id}/approve`
   - body: `{"resolution_payload": {}}`
10. 验证 approve 后：
    - confirmation `status == approved`
    - `resolution_payload.fields` 写入最终落账字段
    - ledger event `event_type == stock_in`
    - snapshot `current_quantity` 更新

## 验证结果

### Focused HTTP 测试

```bash
PYTHONPATH=backend python3 -m py_compile \
  backend/app/api/v2/routes/photo.py \
  backend/tests/test_v2_voice_photo_http_confirmation_flow.py && \
PYTHONPATH=backend pytest -q backend/tests/test_v2_voice_photo_http_confirmation_flow.py
```

结果：

```text
..                                                                       [100%]
2 passed in 6.29s
```

### 关键回归

```bash
PYTHONPATH=backend pytest -q \
  backend/tests/test_v2_voice_photo_http_confirmation_flow.py \
  backend/tests/test_v2_voice_photo_confirmation_first.py \
  backend/tests/test_v2_chat_confirmation_first.py \
  backend/tests/test_mvp_acceptance_flows.py::test_acceptance_upload_backed_photo_stock_in_remains_confirmation_first \
  backend/tests/test_mvp_acceptance_flows.py::test_acceptance_chat_stock_in_confirmation_flow
```

结果：

```text
..........                                                               [100%]
10 passed in 17.78s
```

### Phase 9 场景回归

服务启动后运行：

```bash
python3 backend/scripts/test_phase9_scenarios.py
```

结果：

```text
Total: 5/5 passed
```

### Phase 8 验收回归

服务启动后运行：

```bash
python3 backend/scripts/test_phase8_acceptance.py
```

结果：

```text
Total: 8/8 passed
```

## 当前结论

Voice / Photo stock-in 的真实 HTTP API 已形成完整闭环：

```text
multipart upload -> SSE pending confirmation -> approve(empty payload) -> ledger event -> stock snapshot
```

并且确认边界仍成立：

- AI / OCR / ASR 识别阶段不改库存。
- SSE 返回真实持久化 confirmation。
- 只有 confirmation approval path 才能提交库存账本。
- approve 空 payload 会复用原始 draft payload，并把最终 fields 写回 `resolution_payload` 用于审计。

## 后续建议

下一阶段建议进入 Phase B7：

1. 检查并补齐 HTTP 级 Chat stock-out confirmation approve 流。
2. 加一个统一 V2 HTTP 测试 helper，复用 login / context / SSE parse / approve。
3. 开始整理 git 既有脏状态，区分：
   - 应提交的历史有效功能
   - 测试产生的 DB 文件
   - 永不提交的 `.env`
