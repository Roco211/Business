# AI 原生 SaaS V2 显式消息意图实现计划
> **给智能执行代理（agentic workers）：** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 按任务逐项实现本计划。步骤使用 checkbox（`- [ ]`）语法跟踪。

**Goal:** 让 `POST /api/v2/sessions/{session_id}/messages` 支持显式 `intent_type`，从 task run 创建时就受控地进入 `inventory.stock_in`、`inventory.stock_out` 或默认 `conversation.capture`。

**Architecture:** 本阶段不接入完整 AI interpret 流水线，只补一个受控的 typed entrypoint。消息创建请求新增可选 `intent_type`，服务层对其做白名单校验；未传时仍落到 `conversation.capture`，已传时写入 `task_run.intent_type`，并把该值回传给 API 调用方。这样 V2 runtime 可以逐步摆脱泛型 capture，同时后端继续掌握工具边界验证权。

**Tech Stack:** Python、FastAPI、Pydantic、SQLAlchemy、pytest、OpenAPI snapshot

---

## 文件结构

- 修改 `backend/tests/test_v2_conversation_runtime.py`：增加显式意图创建成功与未知意图失败测试，并更新默认 message API 断言。
- 修改 `backend/app/contracts/v2/conversation.py`：为创建 message 请求和响应补充 `intent_type`。
- 修改 `backend/app/services/v2_conversation.py`：新增允许的 V2 message intent 白名单与校验错误。
- 修改 `backend/app/api/v2/routes/conversation.py`：把非法 `intent_type` 映射到 422 `validation_error`。
- 修改 `project_docs/generated/openapi-v1.json`：刷新 OpenAPI snapshot。

### Task 1: 固定 message API 的显式意图行为

**Files:**
- Modify: `backend/tests/test_v2_conversation_runtime.py`
- Modify: `backend/app/contracts/v2/conversation.py`

- [ ] **Step 1: 先写失败测试，确认显式 `inventory.stock_out` 会写入 task run 并在创建响应中返回**

```python
def test_v2_post_message_accepts_explicit_inventory_intent(client, db_session) -> None:
    token, context_token = seed_v2_login_and_context(client, db_session)
    session_response = client.post(
        "/api/v2/sessions",
        headers={"Authorization": f"Bearer {token}", "X-Context-Token": context_token},
        json={"session_type": "workgroup", "title": "工作群"},
    )
    session_id = session_response.json()["data"]["session_id"]

    response = client.post(
        f"/api/v2/sessions/{session_id}/messages",
        headers={"Authorization": f"Bearer {token}", "X-Context-Token": context_token},
        json={
            "message_kind": "text",
            "payload_json": {"text": "sell two cola"},
            "client_request_id": "v2_msg_stock_out_intent",
            "intent_type": "inventory.stock_out",
        },
    )
    task_run_id = response.json()["data"]["task_run_id"]

    task_response = client.get(
        f"/api/v2/task-runs/{task_run_id}",
        headers={"Authorization": f"Bearer {token}", "X-Context-Token": context_token},
    )

    assert response.status_code == 201
    assert response.json()["data"]["intent_type"] == "inventory.stock_out"
    assert task_response.status_code == 200
    assert task_response.json()["data"]["intent_type"] == "inventory.stock_out"
```

- [ ] **Step 2: 再写失败测试，确认未知 `intent_type` 返回 422**

```python
def test_v2_post_message_rejects_unknown_intent_type(client, db_session) -> None:
    token, context_token = seed_v2_login_and_context(client, db_session)
    session_response = client.post(
        "/api/v2/sessions",
        headers={"Authorization": f"Bearer {token}", "X-Context-Token": context_token},
        json={"session_type": "workgroup", "title": "工作群"},
    )
    session_id = session_response.json()["data"]["session_id"]

    response = client.post(
        f"/api/v2/sessions/{session_id}/messages",
        headers={"Authorization": f"Bearer {token}", "X-Context-Token": context_token},
        json={
            "message_kind": "text",
            "payload_json": {"text": "do something"},
            "client_request_id": "v2_msg_unknown_intent",
            "intent_type": "inventory.delete_all",
        },
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
```

- [ ] **Step 3: 更新现有默认行为测试，明确未传 `intent_type` 时仍然返回 `conversation.capture`**

```python
assert payload["status"] == "captured"
assert payload["intent_type"] == "conversation.capture"
```

- [ ] **Step 4: 运行新增测试，确认当前实现因未支持显式意图或未做校验而失败**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_conversation_runtime.py::test_v2_post_message_accepts_explicit_inventory_intent backend/tests/test_v2_conversation_runtime.py::test_v2_post_message_rejects_unknown_intent_type backend/tests/test_v2_conversation_runtime.py::test_v2_get_task_run_returns_runtime_state_shape -q
```

### Task 2: 实现显式 message intent

**Files:**
- Modify: `backend/app/contracts/v2/conversation.py`
- Modify: `backend/app/services/v2_conversation.py`
- Modify: `backend/app/api/v2/routes/conversation.py`

- [ ] **Step 1: 在请求 / 响应契约中加入 `intent_type`**

```python
class V2CreateMessageRequest(BaseModel):
    message_kind: str
    payload_json: dict[str, object]
    client_request_id: str | None = None
    intent_type: str | None = None


class V2CreateMessageData(BaseModel):
    message_id: str
    task_run_id: str
    intent_type: str
    status: str
```

- [ ] **Step 2: 在服务层新增允许的 message intent 白名单与校验错误**

```python
ALLOWED_V2_MESSAGE_INTENTS = {
    "conversation.capture",
    "inventory.stock_in",
    "inventory.stock_out",
}


class V2UnsupportedIntentTypeError(ValueError):
    pass


def _normalize_v2_message_intent(intent_type: str | None) -> str:
    normalized = (intent_type or "conversation.capture").strip()
    if normalized not in ALLOWED_V2_MESSAGE_INTENTS:
        raise V2UnsupportedIntentTypeError(f"Unsupported intent_type '{normalized}'.")
    return normalized
```

- [ ] **Step 3: 在 `create_v2_message_and_task_run()` 中使用规范化后的 `intent_type`**

```python
normalized_intent_type = _normalize_v2_message_intent(intent_type)

task_run = V2TaskRun(
    ...,
    intent_type=normalized_intent_type,
    status="captured",
    ...
)
```

- [ ] **Step 4: 在 route 中传递 `payload.intent_type`，并把错误映射成 422**

```python
created = create_v2_message_and_task_run(
    ...,
    client_request_id=payload.client_request_id,
    intent_type=payload.intent_type,
)
```

```python
except V2UnsupportedIntentTypeError as exc:
    return JSONResponse(
        status_code=422,
        content=V2ErrorEnvelope(
            error=V2ErrorBody(code="validation_error", message=str(exc))
        ).model_dump(),
    )
```

- [ ] **Step 5: 在创建响应中返回 `intent_type`**

```python
return V2DataEnvelope(
    data=V2CreateMessageData(
        message_id=message.message_id,
        task_run_id=task_run.task_run_id,
        intent_type=task_run.intent_type,
        status=task_run.status,
    )
)
```

- [ ] **Step 6: 重跑新增测试**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_conversation_runtime.py::test_v2_post_message_accepts_explicit_inventory_intent backend/tests/test_v2_conversation_runtime.py::test_v2_post_message_rejects_unknown_intent_type backend/tests/test_v2_conversation_runtime.py::test_v2_get_task_run_returns_runtime_state_shape -q
```

Expected:

- `3 passed`

### Task 3: 阶段验收

**Files:**
- Verify: `backend/tests/test_v2_conversation_runtime.py`
- Modify: `project_docs/generated/openapi-v1.json`

- [ ] **Step 1: 运行 conversation runtime 全测试**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_conversation_runtime.py -q
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
git add backend/app/contracts/v2/conversation.py backend/app/services/v2_conversation.py backend/app/api/v2/routes/conversation.py backend/tests/test_v2_conversation_runtime.py docs/superpowers/plans/2026-04-18-ai-native-saas-v2-explicit-message-intents.md project_docs/generated/openapi-v1.json
git commit -m "feat: add explicit v2 message intents"
```

## 自检

- Spec coverage：本计划只补显式 message intent entrypoint，不扩展到完整 interpret worker、模型调用、clarification 自动生成或 outbox。
- Placeholder scan：没有保留 `TBD`、`TODO`、`implement later` 一类占位。
- Type consistency：统一使用 `intent_type`、`conversation.capture`、`inventory.stock_in`、`inventory.stock_out`、`validation_error` 这组命名。
- Architecture check：task run 在创建时进入显式业务意图仍然经过后端白名单校验，符合“AI 可以建议，后端必须验证并执行”的边界。
