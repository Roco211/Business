# Phase B7: Chat HTTP Stock-out Confirmation Approval

日期：2026-04-25

## 背景

Phase B2/B4 已经在服务层覆盖 Chat stock_in / stock_out 的 confirmation-first 与 approve 落账闭环；Phase B5/B6 已经覆盖 Voice/Photo 的服务层与 HTTP/SSE 端到端闭环。

本阶段补齐 Chat HTTP 级 stock_out 验收，确保真实 `/api/v2/chat` 请求进入待确认单，审批后才写入 V2 库存事件账本并更新库存快照。

## 目标

1. Chat HTTP stock_out 创建 pending confirmation，approve 前不修改库存。
2. approve 空 payload 时使用 confirmation.draft_payload 落账。
3. approve 后写入 `V2InventoryLedgerEvent(event_type="stock_out")`，并将 snapshot 数量减少。
4. 库存不足时返回错误提示，不创建 confirmation，不写 ledger，不改 snapshot。

## 新增测试

文件：`backend/tests/test_v2_chat_http_confirmation_flow.py`

覆盖用例：

- `test_http_chat_stock_out_confirmation_can_be_approved_and_commits_inventory`
  - 通过 `/api/v2/auth/login` 登录。
  - 通过 `/api/v2/context/select` 选择 tenant/shop。
  - monkeypatch Chat LLM intent 为 `stock_out`。
  - 请求 `/api/v2/chat`。
  - 验证返回待确认文案。
  - 验证 pending `V2Confirmation(type="inventory.stock_out")` 已创建。
  - 验证 approve 前 snapshot 仍为原数量，且无 ledger event。
  - 调用 `/api/v2/confirmations/{confirmation_id}/approve`，空 `resolution_payload`。
  - 验证 approve 后 ledger event 为 `stock_out`，`quantity_delta == -2.000`，snapshot 从 10 变为 8。

- `test_http_chat_stock_out_insufficient_inventory_does_not_create_confirmation`
  - 初始库存为 1。
  - 请求卖出 2。
  - 验证返回库存不足提示。
  - 验证未创建 confirmation、未写 ledger、snapshot 保持 1。

## 验证结果

### Focused HTTP Chat 测试

命令：

```bash
PYTHONPATH=backend pytest -q backend/tests/test_v2_chat_http_confirmation_flow.py
```

结果：

```text
2 passed in 6.16s
```

### 关键 confirmation 回归

命令：

```bash
PYTHONPATH=backend python3 -m py_compile backend/tests/test_v2_chat_http_confirmation_flow.py \
  && PYTHONPATH=backend pytest -q \
    backend/tests/test_v2_chat_http_confirmation_flow.py \
    backend/tests/test_v2_chat_confirmation_first.py \
    backend/tests/test_v2_voice_photo_http_confirmation_flow.py \
    backend/tests/test_v2_voice_photo_confirmation_first.py
```

结果：

```text
10 passed in 17.18s
```

### Phase 9 场景脚本

服务：`127.0.0.1:8001`

结果：

```text
Total: 5/5 passed
```

### Phase 8 验收脚本

服务：`127.0.0.1:8001`

结果：

```text
Total: 8/8 passed
```

## 行为结论

Chat HTTP stock_out 现在具备端到端验收保护：

- AI/Chat 识别出的出库写操作不会直接落账。
- 库存充足时先创建 pending confirmation。
- 用户 approve 后才写不可变 ledger event，并更新 snapshot。
- 库存不足时不会创建无法执行的确认单。

## 注意事项

- 本阶段没有修改生产代码，只新增 HTTP 级回归测试和阶段文档。
- 仓库仍存在本轮之外的既有脏状态，提交时只应 stage 本阶段新增测试和本文档。
- 不应提交 `.env`、本地 SQLite 数据库或不相关历史改动。
