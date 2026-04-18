# AI 原生 SaaS V2 草稿与确认类型对齐实现计划
> **给智能执行代理（agentic workers）：** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 按任务逐项实现本计划。步骤使用 checkbox（`- [ ]`）语法跟踪。

**Goal:** 收紧 `request_v2_confirmation_from_task_draft()` 的工具边界，要求 `confirmation_type` 与 `task_draft.draft_type` 对齐，并补上 `inventory.stock_out` 的 draft -> confirmation API 覆盖。

**Architecture:** 本阶段不引入新的 runtime 解释器或 task type 推断，只在现有 `draft -> confirmation` 边界增加后端验证。`request_v2_confirmation_from_task_draft()` 先读取当前 task draft，验证请求的 `confirmation_type` 与 `draft_type` 一致后才允许创建 pending confirmation；API 层为这类边界错误返回 409，避免 AI 或 worker 带着错误工具类型跨越结构化工具边界。

**Tech Stack:** Python、FastAPI、SQLAlchemy、pytest

---

## 文件结构

- 修改 `backend/tests/test_v2_clarification_confirmation.py`：新增 stock-out draft -> confirmation 成功测试与 confirmation type mismatch 失败测试。
- 修改 `backend/app/services/v2_conversation.py`：新增 draft / confirmation 类型对齐校验错误，并在请求确认时执行校验。
- 修改 `backend/app/api/v2/routes/conversation.py`：把类型不匹配映射为 409 业务错误响应。

### Task 1: 固定 stock-out draft -> confirmation 行为与类型校验

**Files:**
- Modify: `backend/tests/test_v2_clarification_confirmation.py`

- [ ] **Step 1: 先写失败测试，确认 `inventory.stock_out` 的 drafted task 可以请求同类型 confirmation**

```python
def test_v2_request_stock_out_confirmation_from_draft_creates_pending_confirmation(client, db_session) -> None:
    from app.services.v2_conversation import create_v2_clarification

    token, context_token = _create_api_identity_context(client, db_session)
    task_run_id = "vtask_stock_out_draft_confirm"
    _seed_v2_inventory_task_run_in_existing_context(
        db_session,
        task_run_id=task_run_id,
        intent_type="inventory.stock_out",
    )
    clarification = create_v2_clarification(
        db_session,
        tenant_id="tenant_a",
        shop_id="shop_a1",
        task_run_id=task_run_id,
        reason_code="missing_stock_out_quantity",
        question_text="How many boxes should be stocked out?",
        requested_fields=["stock_out_quantity", "reason"],
        draft_payload={"inventory_item_id": "vitem_seed", "expected_quantity": 5},
    )

    answer_response = client.post(
        f"/api/v2/clarifications/{clarification.clarification_id}/answer",
        headers={"Authorization": f"Bearer {token}", "X-Context-Token": context_token},
        json={"answer_payload": {"stock_out_quantity": 2, "reason": "counter sale"}},
    )
    response = client.post(
        f"/api/v2/task-runs/{task_run_id}/confirmations",
        headers={"Authorization": f"Bearer {token}", "X-Context-Token": context_token},
        json={"confirmation_type": "inventory.stock_out"},
    )

    assert answer_response.status_code == 200
    assert response.status_code == 201
    assert response.json()["data"]["confirmation_type"] == "inventory.stock_out"
    assert response.json()["data"]["draft_payload"] == {
        "inventory_item_id": "vitem_seed",
        "expected_quantity": 5,
        "stock_out_quantity": 2,
        "reason": "counter sale",
    }
```

- [ ] **Step 2: 再写失败测试，确认 draft_type 与 confirmation_type 不一致时返回 409**

```python
def test_v2_request_confirmation_from_draft_rejects_type_mismatch(client, db_session) -> None:
    from app.services.v2_conversation import create_v2_clarification

    token, context_token = _create_api_identity_context(client, db_session)
    task_run_id = "vtask_stock_out_type_mismatch"
    _seed_v2_inventory_task_run_in_existing_context(
        db_session,
        task_run_id=task_run_id,
        intent_type="inventory.stock_out",
    )
    clarification = create_v2_clarification(
        db_session,
        tenant_id="tenant_a",
        shop_id="shop_a1",
        task_run_id=task_run_id,
        reason_code="missing_stock_out_quantity",
        question_text="How many boxes should be stocked out?",
        requested_fields=["stock_out_quantity", "reason"],
        draft_payload={"inventory_item_id": "vitem_seed", "expected_quantity": 5},
    )

    answer_response = client.post(
        f"/api/v2/clarifications/{clarification.clarification_id}/answer",
        headers={"Authorization": f"Bearer {token}", "X-Context-Token": context_token},
        json={"answer_payload": {"stock_out_quantity": 2, "reason": "counter sale"}},
    )
    response = client.post(
        f"/api/v2/task-runs/{task_run_id}/confirmations",
        headers={"Authorization": f"Bearer {token}", "X-Context-Token": context_token},
        json={"confirmation_type": "inventory.stock_in"},
    )

    assert answer_response.status_code == 200
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "confirmation_type_mismatch"
```

- [ ] **Step 3: 运行新增测试，确认当前实现还没有类型对齐校验而失败**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_clarification_confirmation.py::test_v2_request_stock_out_confirmation_from_draft_creates_pending_confirmation backend/tests/test_v2_clarification_confirmation.py::test_v2_request_confirmation_from_draft_rejects_type_mismatch -q
```

### Task 2: 实现 draft / confirmation 类型对齐校验

**Files:**
- Modify: `backend/app/services/v2_conversation.py`
- Modify: `backend/app/api/v2/routes/conversation.py`

- [ ] **Step 1: 在 `v2_conversation.py` 新增类型不匹配错误**

```python
class V2ConfirmationTypeMismatchError(ValueError):
    pass
```

- [ ] **Step 2: 在 `request_v2_confirmation_from_task_draft()` 中验证 `draft_type == confirmation_type`**

```python
if draft.draft_type != confirmation_type:
    raise V2ConfirmationTypeMismatchError(
        f"Task run {task_run_id} draft type '{draft.draft_type}' does not match confirmation type '{confirmation_type}'."
    )
```

- [ ] **Step 3: 在 route 中把类型不匹配映射成 409 `confirmation_type_mismatch`**

```python
except V2ConfirmationTypeMismatchError:
    return JSONResponse(
        status_code=409,
        content=V2ErrorEnvelope(
            error=V2ErrorBody(
                code="confirmation_type_mismatch",
                message="Confirmation type does not match task draft type",
            )
        ).model_dump(),
    )
```

- [ ] **Step 4: 重跑新增测试**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_clarification_confirmation.py::test_v2_request_stock_out_confirmation_from_draft_creates_pending_confirmation backend/tests/test_v2_clarification_confirmation.py::test_v2_request_confirmation_from_draft_rejects_type_mismatch -q
```

Expected:

- `2 passed`

### Task 3: 阶段验收

**Files:**
- Verify: `backend/tests/test_v2_clarification_confirmation.py`
- Verify: `backend/tests/test_v2_inventory_stock_out_api.py`

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
git add backend/app/services/v2_conversation.py backend/app/api/v2/routes/conversation.py backend/tests/test_v2_clarification_confirmation.py docs/superpowers/plans/2026-04-18-ai-native-saas-v2-draft-confirmation-type-alignment.md
git commit -m "feat: validate v2 draft confirmation types"
```

## 自检

- Spec coverage：本计划聚焦结构化工具边界校验和 `inventory.stock_out` 的 draft -> confirmation 覆盖，不扩展到新的 runtime 解释器、confirmation approval 或 audit/outbox。
- Placeholder scan：没有保留 `TBD`、`TODO`、`implement later` 一类占位。
- Type consistency：统一使用 `draft_type`、`confirmation_type`、`inventory.stock_out`、`confirmation_type_mismatch` 这组命名。
- Architecture check：后端在 AI 建议跨越工具边界前执行类型校验，符合“AI 可以提出工具调用建议，但后端必须验证并执行”的原则。
