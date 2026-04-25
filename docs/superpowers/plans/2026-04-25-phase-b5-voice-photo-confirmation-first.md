# Phase B5: Voice/Photo AI 写入口确认优先闭环

日期：2026-04-25

## 背景

Phase B2/B4 已完成 Chat 库存写操作的 confirmation-first 与 approve 落账闭环。本阶段继续系统检查 Voice / Photo / SSE 等 AI 写入口，目标是避免任何 AI 识别结果绕过人机确认边界。

## 发现的问题

`backend/app/services/v2_voice.py` 与 `backend/app/services/v2_photo.py` 的 stock-in 流程虽然没有直接写库存账本，但仍只返回内存中的 `draft_id` 字符串：

- Voice: `voice-draft-*`
- Photo: `draft-*`

这些 ID 不是真实 `V2Confirmation.confirmation_id`，也没有对应 `V2Message` / `V2TaskRun` / `V2Confirmation` 持久化记录。结果是前端看到“awaiting_confirmation”后，无法通过统一的确认审批 API 完成落账闭环。

## 实现

新增公共 helper：

- `backend/app/services/v2_ai_confirmation.py`
  - `create_v2_ai_stock_in_confirmation(...)`
  - 为 AI 派生的 stock-in 写操作创建真实会话、消息、任务运行与 pending confirmation。
  - 保证 Voice/Photo 只生成待确认单，不直接修改库存。

改造 Voice stock-in：

- 文件：`backend/app/services/v2_voice.py`
- 原来的临时 `voice-draft-*` 改为真实 `V2Confirmation.confirmation_id`。
- SSE 事件 `draft_created` / `awaiting_confirmation` / `complete` 均返回真实 `confirmation_id` 与 `task_run_id`。
- 创建的 `V2TaskRun.intent_type == "inventory.stock_in"`，状态为 `awaiting_confirmation`。

改造 Photo stock-in：

- 文件：`backend/app/services/v2_photo.py`
- 原来的临时 `draft-*` 改为真实 `V2Confirmation.confirmation_id`。
- SSE 事件返回真实 `confirmation_id` 与 `task_run_id`。
- 票据识别不到商品时返回 `no_items_found`，不创建无效确认单。

新增测试：

- `backend/tests/test_v2_voice_photo_confirmation_first.py`
  - Voice stock-in 创建真实 pending confirmation，且不写 ledger / snapshot。
  - Photo stock-in 创建真实 pending confirmation，且不写 ledger / snapshot。

## 当前行为

Voice/Photo stock-in 流程现在统一为：

1. AI/规则提取入库草稿字段。
2. 创建 `V2ConversationSession`。
3. 创建 `V2Message` + `V2TaskRun(intent_type="inventory.stock_in")`。
4. 创建 `V2Confirmation(type="inventory.stock_in", status="pending")`。
5. SSE 返回真实 `confirmation_id` / `task_run_id`。
6. 库存账本与库存快照保持不变。
7. 只有用户 approve confirmation 后，才通过 Phase B4 的 approval path 写入库存事件账本并更新库存快照。

## 验证结果

单测：

```bash
PYTHONPATH=backend python3 -m py_compile backend/app/services/v2_ai_confirmation.py backend/app/services/v2_voice.py backend/app/services/v2_photo.py backend/tests/test_v2_voice_photo_confirmation_first.py
PYTHONPATH=backend pytest -q backend/tests/test_v2_voice_photo_confirmation_first.py
```

结果：

```text
2 passed in 2.17s
```

关键回归：

```bash
PYTHONPATH=backend pytest -q \
  backend/tests/test_v2_voice_photo_confirmation_first.py \
  backend/tests/test_v2_chat_confirmation_first.py \
  backend/tests/test_mvp_acceptance_flows.py::test_acceptance_chat_stock_in_confirmation_flow \
  backend/tests/test_mvp_acceptance_flows.py::test_acceptance_upload_backed_photo_stock_in_remains_confirmation_first
```

结果：

```text
8 passed in 11.68s
```

接口级回归：

- `backend/scripts/test_phase9_scenarios.py`: `Total: 5/5 passed`
- `backend/scripts/test_phase8_acceptance.py`: `Total: 8/8 passed`

## 结论

Phase B5 完成后，Chat / Voice / Photo 这三类核心 AI 写入口都已经进入统一的 confirmation-first 安全边界：AI 只生成待确认单，业务真相只在确认审批路径中改变。
