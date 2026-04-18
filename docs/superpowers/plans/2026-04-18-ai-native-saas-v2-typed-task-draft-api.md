# AI 原生 SaaS V2 显式任务草稿 API 实现计划
> **给智能执行代理（agentic workers）：** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 按任务逐项实现本计划。步骤使用 checkbox（`- [ ]`）语法跟踪。

**Goal:** 让已经带有显式业务意图的 V2 task run 可以通过受控 API 物化 typed task draft，从而继续走现有 draft -> confirmation -> commit 链路。

**Architecture:** 本切片不引入 AI interpret worker，也不让 AI 直接写业务真相。`POST /api/v2/task-runs/{task_run_id}/draft` 只创建或更新建议态 `task_draft`，并把 task run 推进到 `drafted`；后续业务写入仍必须经过 confirmation approve 的确定性工具。该接口当前只接受已经带有 typed intent 的 task run，`draft_type` 必须与 `task_run.intent_type` 严格一致；泛型 `conversation.capture` 仍继续通过 clarification / confirmation 路径收敛。

**Tech Stack:** Python、FastAPI、Pydantic、SQLAlchemy、pytest、OpenAPI snapshot

---

## 文件结构

- 修改 `backend/tests/test_v2_clarification_confirmation.py`：新增 task draft API 成功、typed mismatch、状态拒绝测试。
- 修改 `backend/app/contracts/v2/conversation.py`：新增创建 task draft 请求合同。
- 修改 `backend/app/services/v2_conversation.py`：新增 typed draft 白名单、错误类型与 `upsert_v2_task_draft()` 服务。
- 修改 `backend/app/api/v2/routes/conversation.py`：新增 draft API 路由与错误映射。
- 修改 `project_docs/generated/openapi-v1.json`：刷新 OpenAPI snapshot。

### Task 1: 固定 typed task draft API 行为

**Files:**
- Modify: `backend/tests/test_v2_clarification_confirmation.py`

- [ ] **Step 1: 写失败测试，确认显式 `inventory.stock_in` task 可以创建 typed draft 并进入 `drafted`**

```python
def test_v2_create_typed_task_draft_materializes_draft_and_marks_task_drafted(client, db_session) -> None:
    token, context_token = _create_api_identity_context(client, db_session)
    session_response = client.post(
        "/api/v2/sessions",
        headers={"Authorization": f"Bearer {token}", "X-Context-Token": context_token},
        json={"session_type": "workgroup", "title": "Workgroup"},
    )
    session_id = session_response.json()["data"]["session_id"]
    message_response = client.post(
        f"/api/v2/sessions/{session_id}/messages",
        headers={"Authorization": f"Bearer {token}", "X-Context-Token": context_token},
        json={
            "message_kind": "text",
            "payload_json": {"text": "restock cola"},
            "client_request_id": "typed_draft_msg_stock_in",
            "intent_type": "inventory.stock_in",
        },
    )
    task_run_id = message_response.json()["data"]["task_run_id"]

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
    assert response.json()["data"]["status"] == "drafted"
    assert response.json()["data"]["intent_type"] == "inventory.stock_in"
    assert response.json()["data"]["draft_payload"] == {
        "item_name": "Cola",
        "quantity": 2,
        "unit": "box",
        "price": 18.5,
    }
    assert confirm_response.status_code == 201
    assert confirm_response.json()["data"]["draft_payload"] == response.json()["data"]["draft_payload"]
```

- [ ] **Step 2: 写失败测试，确认 typed task 不能创建不匹配的 draft**

```python
def test_v2_create_typed_task_draft_rejects_type_mismatch(client, db_session) -> None:
    token, context_token = _create_api_identity_context(client, db_session)
    task_run_id = "vtask_typed_draft_mismatch"
    _seed_v2_inventory_task_run_in_existing_context(
        db_session,
        task_run_id=task_run_id,
        intent_type="inventory.stock_out",
    )

    response = client.post(
        f"/api/v2/task-runs/{task_run_id}/draft",
        headers={"Authorization": f"Bearer {token}", "X-Context-Token": context_token},
        json={
            "draft_type": "inventory.stock_in",
            "draft_payload": {"item_name": "Cola", "quantity": 2, "unit": "box", "price": 18.5},
        },
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "draft_type_mismatch"
```

- [ ] **Step 3: 写失败测试，确认已进入 confirmation 的 task 不能继续改 draft**

```python
def test_v2_create_typed_task_draft_rejects_non_draftable_task_status(client, db_session) -> None:
    from app.services.v2_conversation import create_v2_confirmation

    token, context_token = _create_api_identity_context(client, db_session)
    task_run_id = "vtask_typed_draft_not_draftable"
    _seed_v2_inventory_task_run_in_existing_context(
        db_session,
        task_run_id=task_run_id,
        intent_type="inventory.stock_in",
    )
    create_v2_confirmation(
        db_session,
        tenant_id="tenant_a",
        shop_id="shop_a1",
        task_run_id=task_run_id,
        confirmation_type="inventory.stock_in",
        draft_payload={"item_name": "Cola", "quantity": 2, "unit": "box", "price": 18.5},
    )

    response = client.post(
        f"/api/v2/task-runs/{task_run_id}/draft",
        headers={"Authorization": f"Bearer {token}", "X-Context-Token": context_token},
        json={
            "draft_type": "inventory.stock_in",
            "draft_payload": {"item_name": "Cola", "quantity": 3, "unit": "box", "price": 18.5},
        },
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "task_run_not_draftable"
```

- [ ] **Step 4: 运行新增测试，确认当前实现因为路由不存在而失败**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_clarification_confirmation.py::test_v2_create_typed_task_draft_materializes_draft_and_marks_task_drafted backend/tests/test_v2_clarification_confirmation.py::test_v2_create_typed_task_draft_rejects_type_mismatch backend/tests/test_v2_clarification_confirmation.py::test_v2_create_typed_task_draft_rejects_non_draftable_task_status -q
```

Expected:

- 新增测试失败，至少首个测试返回 404。

### Task 2: 实现 typed task draft 服务与 API

**Files:**
- Modify: `backend/app/contracts/v2/conversation.py`
- Modify: `backend/app/services/v2_conversation.py`
- Modify: `backend/app/api/v2/routes/conversation.py`

- [ ] **Step 1: 新增请求合同**

```python
class V2CreateTaskDraftRequest(BaseModel):
    draft_type: str
    draft_payload: dict[str, object] = Field(default_factory=dict)
```

- [ ] **Step 2: 在服务层新增 draft type 白名单与错误**

```python
ALLOWED_V2_TASK_DRAFT_TYPES = {
    "inventory.stock_in",
    "inventory.stock_out",
}


class V2UnsupportedDraftTypeError(ValueError):
    pass


class V2TaskDraftTypeMismatchError(ValueError):
    pass
```

- [ ] **Step 3: 新增 `upsert_v2_task_draft()`**

```python
def upsert_v2_task_draft(
    db_session: Session,
    *,
    tenant_id: str,
    shop_id: str,
    task_run_id: str,
    draft_type: str,
    draft_payload: dict[str, object],
    created_by_account_id: str,
) -> V2TaskRun:
    normalized_draft_type = _normalize_v2_task_draft_type(draft_type)
    task_run = _require_v2_task_run_for_context(...)
    if task_run.status not in {CAPTURED_STATUS, DRAFTED_STATUS}:
        raise V2TaskRunTransitionError(...)
    if task_run.intent_type != normalized_draft_type:
        raise V2TaskDraftTypeMismatchError(...)
    _upsert_v2_task_draft(...)
    task_run.status = DRAFTED_STATUS
    task_run.result_summary = "Task draft is ready for confirmation."
    task_run.error_code = None
    task_run.completed_at = None
    db_session.commit()
    return task_run
```

- [ ] **Step 4: 新增路由并复用 task run 响应形状**

```python
@router.post("/task-runs/{task_run_id}/draft", response_model=V2DataEnvelope[V2TaskRunData])
def create_task_draft_v2(...):
    ...
```

- [ ] **Step 5: 重跑新增测试**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_clarification_confirmation.py::test_v2_create_typed_task_draft_materializes_draft_and_marks_task_drafted backend/tests/test_v2_clarification_confirmation.py::test_v2_create_typed_task_draft_rejects_type_mismatch backend/tests/test_v2_clarification_confirmation.py::test_v2_create_typed_task_draft_rejects_non_draftable_task_status -q
```

Expected:

- `3 passed`

### Task 3: 阶段验收

**Files:**
- Verify: `backend/tests/test_v2_clarification_confirmation.py`
- Modify: `project_docs/generated/openapi-v1.json`

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

- [ ] **Step 3: 刷新 OpenAPI snapshot 并校验**

Run:

```powershell
$env:PYTHONPATH="backend"; python backend/scripts/generate_openapi_snapshot.py
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_openapi_contract_snapshot.py -q
```

- [ ] **Step 4: 运行后端全量测试**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests -q
```

- [ ] **Step 5: 检查 git 状态并提交**

Run:

```powershell
git status --short
git add backend/app/contracts/v2/conversation.py backend/app/services/v2_conversation.py backend/app/api/v2/routes/conversation.py backend/tests/test_v2_clarification_confirmation.py docs/superpowers/plans/2026-04-18-ai-native-saas-v2-typed-task-draft-api.md project_docs/generated/openapi-v1.json
git commit -m "feat: add v2 typed task draft api"
```

## 自检

- Spec coverage：本计划补齐 capture / typed intent 到 draft 的显式后端入口，仍不实现 AI interpret worker、模型调用或自动字段抽取。
- Placeholder scan：没有保留 `TBD`、`TODO`、`implement later` 一类占位。
- Type consistency：统一使用 `draft_type`、`draft_payload`、`inventory.stock_in`、`inventory.stock_out`、`drafted`。
- Architecture check：draft 是建议态，不写 inventory ledger；confirmation approve 仍是唯一业务真相写入入口。
