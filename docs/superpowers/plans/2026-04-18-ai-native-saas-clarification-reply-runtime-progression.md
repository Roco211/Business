# AI 原生 SaaS V2 追问回答与运行时推进实施计划

> **给智能执行代理（agentic workers）：** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 按任务逐项实现本计划。步骤使用 checkbox（`- [ ]`）语法跟踪。

**Goal:** 在现有 v2 clarification / confirmation skeleton 基础上，补齐 `clarification` 的列出与回答闭环，并让 `task_run` 在显式上下文下从 `needs_clarification` 推进到 `drafted`。

**Architecture:** 本阶段继续坚持“AI 提出草稿、系统推进状态、业务真相后置提交”的边界。`clarification` 的查询、回答和状态变更都必须显式携带 `tenant_id / shop_id`；回答追问只会把任务推进到 `drafted`，不会自动创建 `confirmation`，也不会直接调用 inventory ledger 工具，从而为下一刀的 draft -> confirm -> execute 保留清晰接口。

**Tech Stack:** Python, FastAPI, Pydantic, SQLAlchemy, Alembic, pytest, SQLite 测试库, MySQL 生产目标

---

## 范围拆分

本计划覆盖 phase 3 中 `clarify -> draft` 的最小可运行闭环：

- `GET /api/v2/clarifications`
- `POST /api/v2/clarifications/{clarification_id}/answer`
- `clarification.status = answered`
- `task_run.status = drafted`
- 追问答案记录 `answer_payload / answered_by_account_id / answered_at`

本计划暂不覆盖：

- LLM interpret / assess worker
- 自动生成 confirmation
- execute / commit / ledger / outbox
- clarification 多轮回复

## 文件结构

- 修改 `backend/app/contracts/v2/conversation.py`：新增 clarification 列表与回答合同。
- 修改 `backend/app/services/v2_conversation.py`：新增 clarification list / answer 服务与 `drafted` 状态推进。
- 修改 `backend/app/api/v2/routes/conversation.py`：新增 clarification API。
- 修改 `backend/tests/test_v2_clarification_confirmation.py`：覆盖 clarification API 与 task_run 推进。
- 修改 `project_docs/generated/openapi-v1.json`：刷新 OpenAPI 快照。

### Task 1: clarification API 合同与失败测试

**Files:**
- Modify: `backend/tests/test_v2_clarification_confirmation.py`
- Modify: `backend/app/contracts/v2/conversation.py`

- [ ] **Step 1: 写失败测试，确认只能列出当前 context 下的 pending clarification**

```python
def test_v2_list_clarifications_returns_current_context_pending_items(client, db_session) -> None:
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

    response = client.get(
        "/api/v2/clarifications?status=pending&limit=20",
        headers={"Authorization": f"Bearer {token}", "X-Context-Token": context_token},
    )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["count"] == 1
    assert payload["clarifications"][0]["clarification_id"] == clarification.clarification_id
    assert payload["clarifications"][0]["status"] == "pending"
```

- [ ] **Step 2: 写失败测试，确认回答 clarification 会记录答案并把任务推进到 drafted**

```python
def test_v2_answer_clarification_records_answer_and_moves_task_to_drafted(client, db_session) -> None:
    from app.models import V2TaskRun
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

    response = client.post(
        f"/api/v2/clarifications/{clarification.clarification_id}/answer",
        headers={"Authorization": f"Bearer {token}", "X-Context-Token": context_token},
        json={"answer_payload": {"quantity": 2, "unit": "box"}},
    )

    db_session.expire_all()
    task_run = db_session.get(V2TaskRun, task_run_id)
    assert response.status_code == 200
    assert response.json()["data"]["status"] == "answered"
    assert response.json()["data"]["answered_by_account_id"] == "acct_001"
    assert response.json()["data"]["answer_payload"] == {"quantity": 2, "unit": "box"}
    assert task_run is not None
    assert task_run.status == "drafted"
    assert task_run.completed_at is None
```

- [ ] **Step 3: 运行测试，确认因为路由或合同不存在而失败**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_clarification_confirmation.py::test_v2_list_clarifications_returns_current_context_pending_items backend/tests/test_v2_clarification_confirmation.py::test_v2_answer_clarification_records_answer_and_moves_task_to_drafted -q
```

Expected:

- `404`、`ImportError` 或响应结构不匹配。

- [ ] **Step 4: 新增 clarification 合同**

`backend/app/contracts/v2/conversation.py`

```python
class V2AnswerClarificationRequest(BaseModel):
    answer_payload: dict[str, object] = Field(default_factory=dict)


class V2ClarificationData(BaseModel):
    clarification_id: str
    tenant_id: str
    shop_id: str
    task_run_id: str
    status: str
    reason_code: str
    question_text: str
    requested_fields: list[str]
    draft_payload: dict[str, object] | None
    answer_payload: dict[str, object] | None
    answered_by_account_id: str | None
    created_at: datetime
    answered_at: datetime | None


class V2ClarificationListData(BaseModel):
    clarifications: list[V2ClarificationData]
    count: int
```

- [ ] **Step 5: 重新运行 clarification 测试，确认仍然因为服务或路由不存在而红灯**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_clarification_confirmation.py::test_v2_list_clarifications_returns_current_context_pending_items backend/tests/test_v2_clarification_confirmation.py::test_v2_answer_clarification_records_answer_and_moves_task_to_drafted -q
```

Expected:

- 红灯原因收敛为缺少服务/路由实现，而不是合同错误。

### Task 2: clarification 服务与状态推进

**Files:**
- Modify: `backend/app/services/v2_conversation.py`
- Modify: `backend/tests/test_v2_clarification_confirmation.py`

- [ ] **Step 1: 写失败测试，确认回答已回答的 clarification 会冲突**

```python
def test_v2_answer_clarification_rejects_non_pending_record(db_session) -> None:
    import pytest

    from app.services.v2_conversation import (
        V2ConfirmationConflictError,
        answer_v2_clarification,
        create_v2_clarification,
    )

    _seed_v2_task_run(db_session, task_run_id="vtask_answer_once")
    clarification = create_v2_clarification(
        db_session,
        tenant_id="tenant_a",
        shop_id="shop_a1",
        task_run_id="vtask_answer_once",
        reason_code="missing_quantity",
        question_text="How many boxes should be stocked in?",
        requested_fields=["quantity"],
        draft_payload={"item_name": "Cola"},
    )
    answer_v2_clarification(
        db_session,
        tenant_id="tenant_a",
        shop_id="shop_a1",
        clarification_id=clarification.clarification_id,
        answer_payload={"quantity": 2},
        answered_by_account_id="acct_001",
    )

    with pytest.raises(V2ConfirmationConflictError):
        answer_v2_clarification(
            db_session,
            tenant_id="tenant_a",
            shop_id="shop_a1",
            clarification_id=clarification.clarification_id,
            answer_payload={"quantity": 3},
            answered_by_account_id="acct_001",
        )
```

- [ ] **Step 2: 运行服务测试，确认因为函数不存在而失败**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_clarification_confirmation.py::test_v2_answer_clarification_rejects_non_pending_record -q
```

Expected:

- `ImportError`

- [ ] **Step 3: 新增 clarification list / answer 服务**

`backend/app/services/v2_conversation.py`

```python
ANSWERED_STATUS = "answered"


def list_v2_clarifications(db_session: Session, *, tenant_id: str, shop_id: str, status: str | None, limit: int) -> list[V2Clarification]:
    # 按 tenant_id、shop_id、status 查询 clarification。


def answer_v2_clarification(
    db_session: Session,
    *,
    tenant_id: str,
    shop_id: str,
    clarification_id: str,
    answer_payload: dict[str, object],
    answered_by_account_id: str,
) -> V2Clarification:
    # 只允许 pending clarification。
    # answer_payload、answered_by_account_id、answered_at 落库。
    # clarification.status -> answered。
    # task_run.status -> drafted。
```

实现时必须满足：

- clarification 查询必须同时限定 `tenant_id` 和 `shop_id`。
- 回答追问时，对应 `task_run` 必须是 `needs_clarification`。
- 回答成功后 `task_run.result_summary` 更新为可用于后续 confirm 的文案。
- 不自动创建 confirmation。

- [ ] **Step 4: 重新运行服务测试**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_clarification_confirmation.py::test_v2_answer_clarification_rejects_non_pending_record -q
```

Expected:

- `1 passed`

### Task 3: clarification API

**Files:**
- Modify: `backend/app/api/v2/routes/conversation.py`
- Modify: `backend/tests/test_v2_clarification_confirmation.py`

- [ ] **Step 1: 新增 clarification route helper**

`backend/app/api/v2/routes/conversation.py`

```python
def _to_clarification_data(clarification) -> V2ClarificationData:
    ...
```

- [ ] **Step 2: 新增 `GET /api/v2/clarifications`**

```python
@router.get("/clarifications", response_model=V2DataEnvelope[V2ClarificationListData])
def list_clarifications_v2(...):
    # 复用 Authorization + X-Context-Token
```

- [ ] **Step 3: 新增 `POST /api/v2/clarifications/{clarification_id}/answer`**

```python
@router.post("/clarifications/{clarification_id}/answer", response_model=V2DataEnvelope[V2ClarificationData])
def answer_clarification_v2(...):
    # LookupError -> clarification_not_found
    # V2ConfirmationConflictError / V2TaskRunTransitionError -> clarification_not_pending
```

- [ ] **Step 4: 重新运行 clarification API 测试**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_clarification_confirmation.py::test_v2_list_clarifications_returns_current_context_pending_items backend/tests/test_v2_clarification_confirmation.py::test_v2_answer_clarification_records_answer_and_moves_task_to_drafted -q
```

Expected:

- `2 passed`

### Task 4: 阶段验收

**Files:**
- Verify: `backend/tests/test_v2_clarification_confirmation.py`
- Modify: `project_docs/generated/openapi-v1.json`

- [ ] **Step 1: 运行 clarification / confirmation 全测试**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_clarification_confirmation.py -q
```

Expected:

- 本文件全部通过。

- [ ] **Step 2: 运行 v2 关键回归**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_identity_context.py backend/tests/test_v2_conversation_runtime.py backend/tests/test_v2_clarification_confirmation.py -q
```

Expected:

- v2 identity/context、conversation runtime、clarification/confirmation 全部通过。

- [ ] **Step 3: 刷新 OpenAPI 快照**

Run:

```powershell
$env:PYTHONPATH="backend"; python backend/scripts/generate_openapi_snapshot.py
```

- [ ] **Step 4: 运行 OpenAPI 合同测试**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_openapi_contract_snapshot.py -q
```

- [ ] **Step 5: 运行全量后端测试**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests -q
```

- [ ] **Step 6: 检查 git 状态并提交**

Run:

```powershell
git status --short
git add backend/app/contracts/v2/conversation.py backend/app/services/v2_conversation.py backend/app/api/v2/routes/conversation.py backend/tests/test_v2_clarification_confirmation.py docs/superpowers/plans/2026-04-18-ai-native-saas-clarification-reply-runtime-progression.md project_docs/generated/openapi-v1.json
git commit -m "feat: add v2 clarification reply progression"
```

## 自检

- Spec coverage：本计划补上了 `clarify -> draft` 的最小运行时推进。
- Placeholder scan：没有留 `TODO`、`TBD` 或“后面再补”的空洞步骤。
- Type consistency：统一使用 `V2Clarification*`、`answer_payload`、`answered_by_account_id`、`drafted`。
- 架构约束：追问回答只推进状态，不直接修改业务真相，也不绕开 `tenant_id / shop_id` 显式上下文。
