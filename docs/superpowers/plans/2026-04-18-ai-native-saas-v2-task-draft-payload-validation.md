# AI 原生 SaaS V2 任务草稿 Payload 前置校验实现计划
> **给智能执行代理（agentic workers）：** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 按任务逐项实现本计划。步骤使用 checkbox（`- [ ]`）语法跟踪。

**Goal:** 让 `POST /api/v2/task-runs/{task_run_id}/draft` 在建议态就校验 `inventory.stock_in` / `inventory.stock_out` 的业务 payload，非法草稿直接返回 `422 validation_error`。

**Architecture:** 当前 V2 draft API 只校验 `draft_type` 与 task intent 是否一致，直到 confirmation approve 才会触发库存业务字段校验，反馈过晚。本切片把校验前移到 draft 建议态：`v2_conversation` 在写入 `task_draft` 前调用 `v2_inventory` 的确定性 payload 解析逻辑；校验失败时拒绝落草稿、不推进 `task_run.status`，仍保持 AI 不能直接修改业务真相的边界。

**Tech Stack:** Python、FastAPI、SQLAlchemy、pytest

---

## 文件结构

- 修改 `backend/tests/test_v2_clarification_confirmation.py`：增加 stock-in / stock-out draft payload 非法时返回 422 的 API 测试。
- 修改 `backend/app/services/v2_inventory.py`：提取可复用的 stock-out payload 解析函数，并暴露 stock-in / stock-out draft 校验入口。
- 修改 `backend/app/services/v2_conversation.py`：在 `upsert_v2_task_draft()` 中按 `draft_type` 调用前置校验。
- 修改 `backend/app/api/v2/routes/conversation.py`：把库存 payload 校验错误映射为 `422 validation_error`。

### Task 1: 固定 stock-in draft payload 前置校验

**Files:**
- Modify: `backend/tests/test_v2_clarification_confirmation.py`

- [ ] **Step 1: 先写失败测试，确认缺少 `unit` 的 `inventory.stock_in` draft 会被拒绝**

```python
def test_v2_create_stock_in_task_draft_rejects_invalid_payload(client, db_session) -> None:
    token, context_token, task_run_id = _create_api_task_run(
        client,
        db_session,
        intent_type="inventory.stock_in",
    )

    response = client.post(
        f"/api/v2/task-runs/{task_run_id}/draft",
        headers={"Authorization": f"Bearer {token}", "X-Context-Token": context_token},
        json={
            "draft_type": "inventory.stock_in",
            "draft_payload": {"item_name": "Cola", "quantity": 2, "price": 18.5},
        },
    )
    task_response = client.get(
        f"/api/v2/task-runs/{task_run_id}",
        headers={"Authorization": f"Bearer {token}", "X-Context-Token": context_token},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
    assert task_response.status_code == 200
    assert task_response.json()["data"]["status"] == "captured"
    assert task_response.json()["data"]["draft_payload"] is None
```

- [ ] **Step 2: 运行测试，确认当前实现错误地接受非法 draft 而失败**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_clarification_confirmation.py::test_v2_create_stock_in_task_draft_rejects_invalid_payload -q
```

- [ ] **Step 3: 在库存服务中暴露 stock-in draft 校验入口，并在 draft 写入前调用**

`backend/app/services/v2_inventory.py`

```python
def validate_v2_stock_in_draft_payload(payload: dict[str, object]) -> None:
    _parse_v2_stock_in_payload(payload)
```

`backend/app/services/v2_conversation.py`

```python
if normalized_draft_type == "inventory.stock_in":
    validate_v2_stock_in_draft_payload(draft_payload)
```

- [ ] **Step 4: 重跑 stock-in 测试**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_clarification_confirmation.py::test_v2_create_stock_in_task_draft_rejects_invalid_payload -q
```

Expected:

- `1 passed`

### Task 2: 固定 stock-out draft payload 前置校验

**Files:**
- Modify: `backend/tests/test_v2_clarification_confirmation.py`
- Modify: `backend/app/services/v2_inventory.py`
- Modify: `backend/app/services/v2_conversation.py`
- Modify: `backend/app/api/v2/routes/conversation.py`

- [ ] **Step 1: 写失败测试，确认 `stock_out_quantity <= 0` 的 `inventory.stock_out` draft 会被拒绝**

```python
def test_v2_create_stock_out_task_draft_rejects_invalid_payload(client, db_session) -> None:
    token, context_token = _create_api_identity_context(client, db_session)
    task_run_id = "vtask_stock_out_invalid_draft"
    _seed_v2_inventory_task_run_in_existing_context(
        db_session,
        task_run_id=task_run_id,
        intent_type="inventory.stock_out",
    )

    response = client.post(
        f"/api/v2/task-runs/{task_run_id}/draft",
        headers={"Authorization": f"Bearer {token}", "X-Context-Token": context_token},
        json={
            "draft_type": "inventory.stock_out",
            "draft_payload": {
                "inventory_item_id": "vitem_seed",
                "expected_quantity": 5,
                "stock_out_quantity": 0,
                "reason": "counter sale",
            },
        },
    )
    task_response = client.get(
        f"/api/v2/task-runs/{task_run_id}",
        headers={"Authorization": f"Bearer {token}", "X-Context-Token": context_token},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
    assert task_response.status_code == 200
    assert task_response.json()["data"]["status"] == "captured"
    assert task_response.json()["data"]["draft_payload"] is None
```

- [ ] **Step 2: 运行测试，确认当前实现错误地接受非法 draft 而失败**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_clarification_confirmation.py::test_v2_create_stock_out_task_draft_rejects_invalid_payload -q
```

- [ ] **Step 3: 提取 stock-out payload 解析函数并接入 route 错误映射**

`backend/app/services/v2_inventory.py`

```python
def _parse_v2_stock_out_payload(payload: dict[str, object]) -> tuple[str, Decimal, Decimal, str]:
    ...


def validate_v2_stock_out_draft_payload(payload: dict[str, object]) -> None:
    _parse_v2_stock_out_payload(payload)
```

`backend/app/services/v2_conversation.py`

```python
elif normalized_draft_type == "inventory.stock_out":
    validate_v2_stock_out_draft_payload(draft_payload)
```

`backend/app/api/v2/routes/conversation.py`

```python
except (V2InventoryPayloadValidationError, V2InventoryStockOutValidationError) as exc:
    return JSONResponse(
        status_code=422,
        content=V2ErrorEnvelope(
            error=V2ErrorBody(code="validation_error", message=str(exc))
        ).model_dump(),
    )
```

- [ ] **Step 4: 重跑 stock-out 测试**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_clarification_confirmation.py::test_v2_create_stock_out_task_draft_rejects_invalid_payload -q
```

Expected:

- `1 passed`

### Task 3: 阶段验收

**Files:**
- Verify: `backend/tests/test_v2_clarification_confirmation.py`

- [ ] **Step 1: 运行 draft / clarification / confirmation 全测试**

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
git add backend/app/services/v2_inventory.py backend/app/services/v2_conversation.py backend/app/api/v2/routes/conversation.py backend/tests/test_v2_clarification_confirmation.py docs/superpowers/plans/2026-04-18-ai-native-saas-v2-task-draft-payload-validation.md
git commit -m "feat: validate v2 task draft payloads"
```

## 自检

- Spec coverage：本计划只把 typed inventory draft 的字段约束前移到 draft API，不实现 clarification 自动分流。
- Placeholder scan：没有保留 `TBD`、`TODO`、`implement later` 一类占位。
- Type consistency：统一使用 `draft_type`、`draft_payload`、`validation_error`、`inventory.stock_in`、`inventory.stock_out`。
- Architecture check：非法 draft 不会进入 `drafted`，更符合“AI 负责建议，系统负责约束与确认”的边界。
