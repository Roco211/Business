# AI 原生 SaaS V2 泛型任务 Draft 专门化实现计划
> **给智能执行代理（agentic workers）：** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 按任务逐项实现本计划。步骤使用 checkbox（`- [ ]`）语法跟踪。

**Goal:** 让默认 `conversation.capture` task run 在提交 typed task draft 时即可专门化为具体业务意图，而不是等到 confirmation 阶段才完成收敛。

**Architecture:** 当前 V2 已支持显式 typed message intent，也支持 typed task draft API；但默认 `conversation.capture` task 仍会在 draft API 入口被 `draft_type_mismatch` 拒绝。本切片把 `upsert_v2_task_draft()` 与既有 confirmation specialization 对齐：如果 task run 仍是泛型意图，就允许显式 `draft_type` 把 `task_run.intent_type` 与 `task_draft.draft_type` 一起收敛为具体业务类型，然后再继续 confirmation / commit 流程。整个过程仍停留在建议态，不写 inventory ledger。

**Tech Stack:** Python、FastAPI、SQLAlchemy、pytest

---

## 文件结构

- 修改 `backend/tests/test_v2_clarification_confirmation.py`：新增 generic task 经 typed draft API 专门化成功测试。
- 修改 `backend/app/services/v2_conversation.py`：放宽 `upsert_v2_task_draft()` 对 generic intent 的限制，并在写 draft 前更新 `task_run.intent_type`。

### Task 1: 固定泛型 task 的 draft 专门化行为

**Files:**
- Modify: `backend/tests/test_v2_clarification_confirmation.py`

- [x] **Step 1: 写失败测试，确认默认 `conversation.capture` task 可以通过 typed draft API 进入 `inventory.stock_in`**

```python
def test_v2_create_typed_task_draft_specializes_generic_task_intent(client, db_session) -> None:
    token, context_token, task_run_id = _create_api_task_run(client, db_session)

    response = client.post(
        f"/api/v2/task-runs/{task_run_id}/draft",
        headers={"Authorization": f"Bearer {token}", "X-Context-Token": context_token},
        json={
            "draft_type": "inventory.stock_in",
            "draft_payload": {"item_name": "Cola", "quantity": 2, "unit": "box", "price": 18.5},
        },
    )
    confirm_response = client.post(
        f"/api/v2/task-runs/{task_run_id}/confirmations",
        headers={"Authorization": f"Bearer {token}", "X-Context-Token": context_token},
        json={"confirmation_type": "inventory.stock_in"},
    )

    assert response.status_code == 200
    assert response.json()["data"]["intent_type"] == "inventory.stock_in"
    assert response.json()["data"]["status"] == "drafted"
    assert confirm_response.status_code == 201
```

- [x] **Step 2: 运行新增测试，确认当前实现因为 generic intent 被当作 mismatch 而失败**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_clarification_confirmation.py::test_v2_create_typed_task_draft_specializes_generic_task_intent -q
```

Expected:

- `1 failed`
- 错误原因为 `draft_type_mismatch` 或 409。

### Task 2: 实现 generic task draft specialization

**Files:**
- Modify: `backend/app/services/v2_conversation.py`

- [x] **Step 1: 在 `upsert_v2_task_draft()` 中识别 generic intent**

```python
should_specialize_generic_task = task_run.intent_type in GENERIC_DRAFT_TYPES
```

- [x] **Step 2: 仅在非 generic 且不匹配时拒绝**

```python
if not should_specialize_generic_task and task_run.intent_type != normalized_draft_type:
    raise V2TaskDraftTypeMismatchError(...)
```

- [x] **Step 3: 在写 draft 前更新 task run 的 intent**

```python
if should_specialize_generic_task:
    task_run.intent_type = normalized_draft_type
```

- [x] **Step 4: 重跑新增测试**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_clarification_confirmation.py::test_v2_create_typed_task_draft_specializes_generic_task_intent -q
```

Expected:

- `1 passed`

### Task 3: 阶段验收

**Files:**
- Verify: `backend/tests/test_v2_clarification_confirmation.py`

- [x] **Step 1: 运行 clarification / confirmation 全测试**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_clarification_confirmation.py -q
```

- [x] **Step 2: 运行关键 V2 回归**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_identity_context.py backend/tests/test_v2_conversation_runtime.py backend/tests/test_v2_clarification_confirmation.py backend/tests/test_v2_inventory_ledger.py backend/tests/test_v2_inventory_read_api.py backend/tests/test_v2_inventory_corrections_api.py backend/tests/test_v2_inventory_stock_out_api.py -q
```

- [x] **Step 3: 运行后端全量测试**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests -q
```

- [x] **Step 4: 检查 git 状态并提交**

Run:

```powershell
git status --short
git add backend/app/services/v2_conversation.py backend/tests/test_v2_clarification_confirmation.py docs/superpowers/plans/2026-04-18-ai-native-saas-v2-generic-task-draft-specialization.md
git commit -m "feat: specialize v2 generic tasks at draft creation"
```

## 自检

- Spec coverage：本计划让 generic task 更早收敛为显式业务意图，但仍不实现 interpret worker 或自动抽取。
- Placeholder scan：没有保留 `TBD`、`TODO`、`implement later` 一类占位。
- Type consistency：统一使用 `conversation.capture`、`draft_type`、`task_run.intent_type`、`task_draft.draft_type`。
- Architecture check：专门化只发生在 draft 建议态，confirmation / commit 的真相写入边界没有变化。
