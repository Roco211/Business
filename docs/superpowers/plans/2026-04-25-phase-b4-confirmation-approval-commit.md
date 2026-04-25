# Phase B4：确认审批落账闭环

## 背景

Phase B2 已经把 Chat 识别出的库存入库、出库写操作改为 confirmation-first：AI 只生成待确认单，不直接修改库存账本。

本阶段继续补齐确认审批后的落账闭环：用户审批待确认单时，即使前端只发送“确认”动作、没有重复提交完整字段，后端也必须能使用 confirmation.draft_payload 中的原始草稿完成确定性落账。

## 本阶段目标

1. Chat stock_in / stock_out 生成 pending V2Confirmation 后，approve 能真正写入库存账本。
2. approve 请求允许 resolution_payload 为空；后端默认使用 confirmation.draft_payload。
3. 如果 approve 请求包含 resolution_payload.fields，则以 draft_payload 为基础，用 fields 覆盖用户编辑后的字段。
4. 审批后的 resolution_payload 要保存最终实际落账字段，便于审计和回放。

## 代码改动

### 1. approve 字段解析

文件：`backend/app/services/v2_conversation.py`

新增 `_resolve_v2_approved_fields(...)`：

- 从 `confirmation.draft_payload` 读取原始草稿字段
- 从 `resolution_payload.fields` 读取审批时覆盖字段
- 合并规则：`draft_payload + fields override`

### 2. stock_in approve 兼容空 payload

`confirmation_type == "inventory.stock_in"` 时：

- 旧行为：只读取 `resolution_payload.fields`，为空时会因为缺少 `item_name/unit/quantity/price` 报错
- 新行为：默认读取 `confirmation.draft_payload`，允许用户直接确认
- 实际落账字段写回 `confirmation.resolution_payload.fields`

### 3. stock_out approve 兼容空 payload

`confirmation_type == "inventory.stock_out"` 时：

- 旧行为：只读取 `resolution_payload.fields`，为空时会因为缺少 `inventory_item_id/expected_quantity/stock_out_quantity/reason` 报错
- 新行为：默认读取 `confirmation.draft_payload`，允许用户直接确认
- 实际落账字段写回 `confirmation.resolution_payload.fields`

## 测试补充

文件：`backend/tests/test_v2_chat_confirmation_first.py`

新增 2 个测试：

1. `test_chat_stock_in_confirmation_approval_commits_original_draft_payload`
   - Chat 创建 stock_in 待确认单
   - approve 使用空 `resolution_payload={}`
   - 验证库存从 10 变为 15
   - 验证 task_run 状态为 `committed`
   - 验证 ledger event 为 `stock_in`
   - 验证 resolution_payload 保存最终 fields

2. `test_chat_stock_out_confirmation_approval_commits_original_draft_payload`
   - Chat 创建 stock_out 待确认单
   - approve 使用空 `resolution_payload={}`
   - 验证库存从 10 变为 8
   - 验证 task_run 状态为 `committed`
   - 验证 ledger event 为 `stock_out`
   - 验证 resolution_payload 保存最终 fields

## TDD 红灯结果

实现前，两个新增测试均失败，原因符合预期：

- stock_in：`V2InventoryPayloadValidationError: item_name is required when item_id is absent`
- stock_out：`V2InventoryStockOutValidationError: inventory_item_id is required`

说明原 approve 逻辑确实只读取审批请求里的 fields，没有回退到 confirmation 草稿。

## 验证结果

### 1. 新增确认闭环测试

命令：

```bash
cd /root/business-clone
PYTHONPATH=backend pytest -q backend/tests/test_v2_chat_confirmation_first.py
```

结果：

```text
4 passed in 4.05s
```

### 2. py_compile + 关键回归

命令：

```bash
cd /root/business-clone
PYTHONPATH=backend python3 -m py_compile \
  backend/app/services/v2_conversation.py \
  backend/tests/test_v2_chat_confirmation_first.py \
&& PYTHONPATH=backend pytest -q \
  backend/tests/test_v2_chat_confirmation_first.py \
  backend/tests/test_mvp_acceptance_flows.py::test_acceptance_chat_stock_in_confirmation_flow \
  backend/tests/test_mvp_acceptance_flows.py::test_acceptance_upload_backed_photo_stock_in_remains_confirmation_first
```

结果：

```text
6 passed in 10.42s
```

### 3. Phase 9 场景回归

命令：

```bash
cd /root/business-clone
python3 backend/scripts/test_phase9_scenarios.py
```

结果：

```text
Total: 5/5 passed
```

### 4. Phase 8 验收回归

命令：

```bash
cd /root/business-clone
python3 backend/scripts/test_phase8_acceptance.py
```

结果：

```text
Total: 8/8 passed
```

## 当前行为

完整链路现在为：

1. Chat 识别 `stock_in` / `stock_out`
2. 后端创建 `V2Message`
3. 后端创建 `V2TaskRun(status=awaiting_confirmation)`
4. 后端创建 `V2Confirmation(status=pending)`
5. 库存快照不变
6. 用户 approve
7. 后端使用 draft_payload + 用户覆盖字段落账
8. 写入 `V2InventoryLedgerEvent`
9. 更新 `V2InventoryStockSnapshot`
10. `V2TaskRun.status=committed`
11. `V2Confirmation.status=approved`

## 结论

Phase B4 已补齐 Chat confirmation-first 后的审批落账闭环。现在 AI 解释出的库存写操作不会直接修改业务真相，但用户确认后可以稳定进入库存账本和库存快照。