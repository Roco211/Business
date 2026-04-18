# AI 原生 SaaS V2 系统结果消息实现计划
> **给智能执行代理（agentic workers）：** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 按任务逐项实现本计划。步骤使用 checkbox（`- [ ]`）语法跟踪。

**Goal:** 让 V2 confirmation 在 `committed` / `rejected` 结果落定后，把系统结果消息追加到对应会话消息流，补齐 spec 中 `session.message.append_system_result` 的最小实现。

**Architecture:** 现有 V2 已能把 confirmation 推进到 `committed` / `rejected`，但结果只停留在 `task_run` 与库存账本里，没有回写会话消息历史。本切片复用现有 `V2Message` 模型，不新增 `task_run_id` 外键字段，而是通过 `actor_type="system"`、`actor_id="runtime_system"`、`message_kind="system_result"` 与结构化 `payload_json` 表达系统结果，保持 tenant / shop / session 边界不变，并把消息写入与确认决议放进同一事务中。

**Tech Stack:** Python、FastAPI、SQLAlchemy、pytest

---

## 文件结构

- 修改 `backend/tests/test_v2_clarification_confirmation.py`：为 stock-in commit、stock-out commit、reject 增加会话系统结果消息验收。
- 修改 `backend/app/services/v2_conversation.py`：新增 V2 system result message 追加助手，并在 approve / reject 流程里接入。

### Task 1: 固定 stock-in commit 的系统结果消息

**Files:**
- Modify: `backend/tests/test_v2_clarification_confirmation.py`
- Modify: `backend/app/services/v2_conversation.py`

- [ ] **Step 1: 先写失败测试，确认 stock-in approve 后会话里多出一条 system result 消息**

```python
def test_v2_approve_confirmation_commits_inventory_and_appends_system_result_message(client, db_session) -> None:
    ...
    messages_response = client.get(
        f"/api/v2/sessions/{session_id}/messages",
        headers={"Authorization": f"Bearer {token}", "X-Context-Token": context_token},
    )

    assert messages_response.status_code == 200
    messages = messages_response.json()["data"]["messages"]
    assert len(messages) == 2
    assert messages[-1]["actor_type"] == "system"
    assert messages[-1]["actor_id"] == "runtime_system"
    assert messages[-1]["message_kind"] == "system_result"
    assert messages[-1]["payload_json"]["task_run_id"] == task_run_id
    assert messages[-1]["payload_json"]["task_run_status"] == "committed"
```

- [ ] **Step 2: 运行单测，确认当前实现尚未写入 system result message 而失败**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_clarification_confirmation.py::test_v2_approve_confirmation_commits_inventory_and_appends_system_result_message -q
```

- [ ] **Step 3: 在会话服务里追加 V2 system result message 助手，并在 stock-in approve 成功后调用**

`backend/app/services/v2_conversation.py`

```python
def append_v2_system_result_message(
    db_session: Session,
    *,
    task_run: V2TaskRun,
    confirmation: V2Confirmation,
    text: str,
) -> V2Message:
    message = V2Message(
        ...,
        actor_type="system",
        actor_id="runtime_system",
        message_kind="system_result",
        payload_json={
            "text": text,
            "task_run_id": task_run.task_run_id,
            "task_run_status": task_run.status,
            "confirmation_id": confirmation.confirmation_id,
            "confirmation_type": confirmation.confirmation_type,
        },
    )
```

- [ ] **Step 4: 重跑 stock-in 单测**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_clarification_confirmation.py::test_v2_approve_confirmation_commits_inventory_and_appends_system_result_message -q
```

Expected:

- `1 passed`

### Task 2: 覆盖 stock-out commit 与 reject 的系统结果消息

**Files:**
- Modify: `backend/tests/test_v2_clarification_confirmation.py`
- Modify: `backend/app/services/v2_conversation.py`

- [ ] **Step 1: 写失败测试，确认 stock-out approve 后也会追加 committed system result message**

```python
def test_v2_approve_stock_out_confirmation_commits_inventory_and_appends_system_result_message(
    client, db_session
) -> None:
    ...
    assert messages[-1]["payload_json"]["confirmation_type"] == "inventory.stock_out"
    assert messages[-1]["payload_json"]["task_run_status"] == "committed"
```

- [ ] **Step 2: 写失败测试，确认 reject 后会追加 rejected system result message**

```python
def test_v2_reject_confirmation_marks_task_rejected_and_appends_system_result_message(
    client, db_session
) -> None:
    ...
    assert messages[-1]["payload_json"]["task_run_status"] == "rejected"
    assert "reject" in messages[-1]["payload_json"]["text"].lower()
```

- [ ] **Step 3: 在 reject 流程里接入同一个 system result message 助手**

```python
append_v2_system_result_message(
    db_session,
    task_run=task_run,
    confirmation=confirmation,
    text="Confirmation rejected; no business change committed.",
)
```

- [ ] **Step 4: 分别重跑 stock-out / reject 单测**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_clarification_confirmation.py::test_v2_approve_stock_out_confirmation_commits_inventory_and_appends_system_result_message -q
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_clarification_confirmation.py::test_v2_reject_confirmation_marks_task_rejected_and_appends_system_result_message -q
```

Expected:

- 两个用例都 `1 passed`

### Task 3: 阶段验收

**Files:**
- Verify: `backend/tests/test_v2_clarification_confirmation.py`
- Verify: `backend/tests/test_v2_conversation_runtime.py`

- [ ] **Step 1: 运行 clarification / confirmation 全测试**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_clarification_confirmation.py -q
```

- [ ] **Step 2: 运行关键 V2 回归**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_identity_context.py backend/tests/test_v2_conversation_runtime.py backend/tests/test_v2_clarification_confirmation.py backend/tests/test_v2_inventory_ledger.py backend/tests/test_v2_inventory_read_api.py backend/tests/test_v2_inventory_corrections_api.py backend/tests/test_v2_inventory_stock_out_api.py -q
```

- [ ] **Step 3: 运行后端全量测试**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests -q
```

- [ ] **Step 4: 检查 git 状态并提交**

Run:

```powershell
git status --short
git add backend/app/services/v2_conversation.py backend/tests/test_v2_clarification_confirmation.py docs/superpowers/plans/2026-04-18-ai-native-saas-v2-system-result-messages.md
git commit -m "feat: add v2 system result messages"
```

## 自检

- Spec coverage：本计划只补 `session.message.append_system_result` 的最小可用实现，不引入新的消息表字段或 outbox 事件。
- Placeholder scan：没有保留 `TBD`、`TODO`、`implement later` 一类占位。
- Type consistency：统一使用 `message_kind="system_result"`、`actor_type="system"`、`actor_id="runtime_system"`、`task_run_status`。
- Architecture check：系统结果消息只是会话投影，不替代账本、审计或库存真相，符合“AI 不能直接修改业务真相”的边界。
