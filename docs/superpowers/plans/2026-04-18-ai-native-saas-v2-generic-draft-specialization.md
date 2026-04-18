# AI 原生 SaaS V2 泛型草稿专门化实现计划
> **给智能执行代理（agentic workers）：** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 按任务逐项实现本计划。步骤使用 checkbox（`- [ ]`）语法跟踪。

**Goal:** 当 `conversation.capture` 泛型 task draft 被请求为具体 confirmation 时，将 `task_run.intent_type` 与 `task_draft.draft_type` 专门化为该 `confirmation_type`。

**Architecture:** 上一个切片允许泛型 `conversation.capture` draft 在请求确认时专门化为具体业务 confirmation，本切片把该专门化结果持久化。`request_v2_confirmation_from_task_draft()` 在通过类型校验后，如果 draft 仍是泛型类型，就把 draft 与 task run 同步更新为请求的 `confirmation_type`，随后再创建 confirmation；已类型化 draft 仍继续要求严格匹配。

**Tech Stack:** Python、FastAPI、SQLAlchemy、pytest

---

## 文件结构

- 修改 `backend/tests/test_v2_clarification_confirmation.py`：新增泛型 capture draft 请求具体 confirmation 后专门化 task/draft 类型的测试。
- 修改 `backend/app/services/v2_conversation.py`：在 `request_v2_confirmation_from_task_draft()` 中持久化泛型 draft 的业务类型。

### Task 1: 固定泛型 draft 专门化行为

**Files:**
- Modify: `backend/tests/test_v2_clarification_confirmation.py`

- [ ] **Step 1: 先写失败测试，确认泛型 capture draft 请求 `inventory.stock_in` confirmation 后会专门化 task 与 draft**

```python
def test_v2_request_confirmation_from_generic_draft_specializes_task_and_draft_type(client, db_session) -> None:
    from app.models import V2TaskDraft
    from app.services.v2_conversation import create_v2_clarification

    token, context_token, task_run_id = _create_api_task_run(client, db_session)
    clarification = create_v2_clarification(
        db_session,
        tenant_id="tenant_a",
        shop_id="shop_a1",
        task_run_id=task_run_id,
        reason_code="missing_quantity",
        question_text="How many boxes should be stocked in?",
        requested_fields=["quantity"],
        draft_payload={"item_name": "Cola"},
    )
    answer_response = client.post(
        f"/api/v2/clarifications/{clarification.clarification_id}/answer",
        headers={"Authorization": f"Bearer {token}", "X-Context-Token": context_token},
        json={"answer_payload": {"quantity": 2, "unit": "box"}},
    )
    confirmation_response = client.post(
        f"/api/v2/task-runs/{task_run_id}/confirmations",
        headers={"Authorization": f"Bearer {token}", "X-Context-Token": context_token},
        json={"confirmation_type": "inventory.stock_in"},
    )
    task_response = client.get(
        f"/api/v2/task-runs/{task_run_id}",
        headers={"Authorization": f"Bearer {token}", "X-Context-Token": context_token},
    )

    db_session.expire_all()
    draft = db_session.query(V2TaskDraft).filter_by(task_run_id=task_run_id).one()

    assert answer_response.status_code == 200
    assert confirmation_response.status_code == 201
    assert task_response.json()["data"]["intent_type"] == "inventory.stock_in"
    assert draft.draft_type == "inventory.stock_in"
```

- [ ] **Step 2: 运行新增测试，确认当前实现仍保留 `conversation.capture` 而失败**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_clarification_confirmation.py::test_v2_request_confirmation_from_generic_draft_specializes_task_and_draft_type -q
```

### Task 2: 实现泛型 draft 专门化

**Files:**
- Modify: `backend/app/services/v2_conversation.py`

- [ ] **Step 1: 在 `request_v2_confirmation_from_task_draft()` 中识别泛型 draft**

```python
should_specialize_generic_draft = draft.draft_type in GENERIC_DRAFT_TYPES
```

- [ ] **Step 2: 在 task 状态校验通过后更新 task 与 draft 类型**

```python
if should_specialize_generic_draft:
    task_run.intent_type = confirmation_type
    draft.draft_type = confirmation_type
    draft.updated_at = utc_now_naive()
```

- [ ] **Step 3: 重跑新增测试**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_clarification_confirmation.py::test_v2_request_confirmation_from_generic_draft_specializes_task_and_draft_type -q
```

Expected:

- `1 passed`

### Task 3: 阶段验收

**Files:**
- Verify: `backend/tests/test_v2_clarification_confirmation.py`

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
git add backend/app/services/v2_conversation.py backend/tests/test_v2_clarification_confirmation.py docs/superpowers/plans/2026-04-18-ai-native-saas-v2-generic-draft-specialization.md
git commit -m "feat: specialize v2 generic task drafts"
```

## 自检

- Spec coverage：本计划只收紧 `conversation.capture` 泛型 draft 的专门化持久化，不扩展到 AI interpret worker、自动字段抽取或 outbox。
- Placeholder scan：没有保留 `TBD`、`TODO`、`implement later` 一类占位。
- Type consistency：统一使用 `conversation.capture`、`confirmation_type`、`task_run.intent_type`、`task_draft.draft_type`。
- Architecture check：系统在确认边界前把泛型任务收敛为显式业务类型，减少后续工具执行中的隐式语义。
