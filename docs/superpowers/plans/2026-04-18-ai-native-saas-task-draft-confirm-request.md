# AI 原生 SaaS V2 任务草稿与确认请求实施计划

> **给智能执行代理（agentic workers）：** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 按任务逐项实现本计划。步骤使用 checkbox（`- [ ]`）语法跟踪。

**Goal:** 为 `drafted` 状态补齐可持久化的 `task_draft` 实体，并让任务在显式上下文下从 `drafted` 进入 `awaiting_confirmation`，同时保留“草稿不是业务真相”的边界。

**Architecture:** 本阶段继续沿用 conversation runtime 的显式上下文与状态机设计。`task_draft` 直接带 `tenant_id / shop_id / task_run_id`，用于承载结构化业务建议；回答 clarification 时只更新 draft，不写业务真相；确认请求从 task_draft 复制 `draft_payload` 到 `confirmation`，再把任务推进到 `awaiting_confirmation`。

**Tech Stack:** Python, FastAPI, Pydantic, SQLAlchemy, Alembic, pytest, SQLite 测试库, MySQL 生产目标

---

## 范围拆分

本计划覆盖 `draft -> confirm` 的最小运行时推进：

- `v2_task_drafts` 表与 ORM。
- clarification answer 自动物化 `task_draft`。
- `GET /api/v2/task-runs/{task_run_id}` 返回当前 draft。
- `POST /api/v2/task-runs/{task_run_id}/confirmations` 从 draft 创建 confirmation。
- `task_run.status` 从 `drafted` 进入 `awaiting_confirmation`。

本计划暂不覆盖：

- inventory ledger commit
- execute / commit worker
- 多种 draft 类型拆分
- draft 版本历史

## 文件结构

- 修改 `backend/app/models/v2_conversation.py`：新增 `V2TaskDraft` 模型。
- 修改 `backend/app/models/__init__.py`：导出 draft 模型。
- 新增 `backend/alembic/versions/20260418_04_create_v2_task_drafts.py`：创建 draft 表。
- 修改 `backend/app/contracts/v2/conversation.py`：扩展 `V2TaskRunData`，新增 confirmation request 合同。
- 修改 `backend/app/services/v2_conversation.py`：新增 draft 读写、clarification answer merge、request confirmation 服务。
- 修改 `backend/app/api/v2/routes/conversation.py`：新增 task-run confirmation request 路由。
- 修改 `backend/tests/test_v2_clarification_confirmation.py`：新增 draft 与 confirmation request 验收测试。
- 修改 `project_docs/generated/openapi-v1.json`：刷新 OpenAPI 快照。

### Task 1: schema 与失败测试

**Files:**
- Modify: `backend/tests/test_v2_clarification_confirmation.py`
- Modify: `backend/app/models/v2_conversation.py`
- Modify: `backend/app/models/__init__.py`
- Create: `backend/alembic/versions/20260418_04_create_v2_task_drafts.py`

- [ ] **Step 1: 写失败测试，固定 task_draft 直接持有 tenant/shop/task_run 边界**

```python
def test_v2_task_draft_schema_persists_context_boundaries(db_session) -> None:
    from sqlalchemy import select

    from app.models import V2TaskDraft

    now = _utc_now_naive()
    _seed_v2_task_run(db_session, task_run_id="vtask_draft_schema")
    draft = V2TaskDraft(
        task_draft_id="vdraft_001",
        tenant_id="tenant_a",
        shop_id="shop_a1",
        task_run_id="vtask_draft_schema",
        draft_type="inventory.stock_in",
        payload_json={"item_name": "Cola", "quantity": 2, "unit": "box"},
        created_by_account_id="acct_001",
        created_at=now,
        updated_at=now,
    )
    db_session.add(draft)
    db_session.commit()

    persisted = db_session.scalar(select(V2TaskDraft).where(V2TaskDraft.task_draft_id == "vdraft_001"))
    assert persisted is not None
    assert persisted.tenant_id == "tenant_a"
    assert persisted.shop_id == "shop_a1"
```

- [ ] **Step 2: 运行测试，确认因为模型或表不存在而失败**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_clarification_confirmation.py::test_v2_task_draft_schema_persists_context_boundaries -q
```

- [ ] **Step 3: 新增 `V2TaskDraft` 模型与迁移**

`backend/app/models/v2_conversation.py`

```python
class V2TaskDraft(Base):
    __tablename__ = "v2_task_drafts"

    task_draft_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("v2_tenants.tenant_id"), nullable=False, index=True)
    shop_id: Mapped[str] = mapped_column(ForeignKey("v2_shops.shop_id"), nullable=False, index=True)
    task_run_id: Mapped[str] = mapped_column(ForeignKey("v2_task_runs.task_run_id"), nullable=False, unique=True)
    draft_type: Mapped[str] = mapped_column(String(64), nullable=False)
    payload_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    created_by_account_id: Mapped[str] = mapped_column(ForeignKey("v2_accounts.account_id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False, default=utc_now_naive)
    updated_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False, default=utc_now_naive)
```

`backend/alembic/versions/20260418_04_create_v2_task_drafts.py`

```python
revision = "20260418_04"
down_revision = "20260418_03"
```

- [ ] **Step 4: 重新运行 schema 测试**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_clarification_confirmation.py::test_v2_task_draft_schema_persists_context_boundaries -q
```

Expected:

- `1 passed`

### Task 2: clarification answer 物化 draft

**Files:**
- Modify: `backend/app/contracts/v2/conversation.py`
- Modify: `backend/app/services/v2_conversation.py`
- Modify: `backend/tests/test_v2_clarification_confirmation.py`

- [ ] **Step 1: 写失败测试，确认回答 clarification 会创建可读取的 task_draft**

```python
def test_v2_answer_clarification_materializes_task_draft(client, db_session) -> None:
    token, context_token, task_run_id = _create_api_task_run(client, db_session)
    from app.services.v2_conversation import create_v2_clarification

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
    task_response = client.get(
        f"/api/v2/task-runs/{task_run_id}",
        headers={"Authorization": f"Bearer {token}", "X-Context-Token": context_token},
    )

    assert answer_response.status_code == 200
    assert task_response.status_code == 200
    assert task_response.json()["data"]["draft_payload"] == {
        "item_name": "Cola",
        "quantity": 2,
        "unit": "box",
    }
```

- [ ] **Step 2: 运行测试，确认因为 draft 字段或服务不存在而失败**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_clarification_confirmation.py::test_v2_answer_clarification_materializes_task_draft -q
```

- [ ] **Step 3: 扩展合同与服务**

`backend/app/contracts/v2/conversation.py`

```python
class V2TaskRunData(BaseModel):
    ...
    draft_payload: dict[str, object] | None = None


class V2RequestConfirmationFromDraftRequest(BaseModel):
    confirmation_type: str
```

`backend/app/services/v2_conversation.py`

```python
def get_v2_task_draft(...):
    ...


def upsert_v2_task_draft_from_clarification(...):
    # merge clarification.draft_payload 与 answer_payload。
```

并让 `answer_v2_clarification()` 在 task 进入 `drafted` 的同时写入或更新 draft。

- [ ] **Step 4: 重新运行 draft 测试**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_clarification_confirmation.py::test_v2_answer_clarification_materializes_task_draft -q
```

Expected:

- `1 passed`

### Task 3: 从 draft 发起 confirmation

**Files:**
- Modify: `backend/app/api/v2/routes/conversation.py`
- Modify: `backend/app/services/v2_conversation.py`
- Modify: `backend/tests/test_v2_clarification_confirmation.py`

- [ ] **Step 1: 写失败测试，确认 drafted task 可以从 draft 创建 confirmation**

```python
def test_v2_request_confirmation_from_draft_creates_pending_confirmation(client, db_session) -> None:
    token, context_token, task_run_id = _create_api_task_run(client, db_session)
    from app.services.v2_conversation import create_v2_clarification

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
    client.post(
        f"/api/v2/clarifications/{clarification.clarification_id}/answer",
        headers={"Authorization": f"Bearer {token}", "X-Context-Token": context_token},
        json={"answer_payload": {"quantity": 2, "unit": "box"}},
    )

    response = client.post(
        f"/api/v2/task-runs/{task_run_id}/confirmations",
        headers={"Authorization": f"Bearer {token}", "X-Context-Token": context_token},
        json={"confirmation_type": "inventory.stock_in"},
    )
    task_response = client.get(
        f"/api/v2/task-runs/{task_run_id}",
        headers={"Authorization": f"Bearer {token}", "X-Context-Token": context_token},
    )

    assert response.status_code == 201
    assert response.json()["data"]["status"] == "pending"
    assert response.json()["data"]["draft_payload"] == {
        "item_name": "Cola",
        "quantity": 2,
        "unit": "box",
    }
    assert task_response.json()["data"]["status"] == "awaiting_confirmation"
```

- [ ] **Step 2: 写失败测试，确认没有 draft 时不能请求 confirmation**

```python
def test_v2_request_confirmation_from_draft_rejects_missing_draft(client, db_session) -> None:
    token, context_token, task_run_id = _create_api_task_run(client, db_session)

    response = client.post(
        f"/api/v2/task-runs/{task_run_id}/confirmations",
        headers={"Authorization": f"Bearer {token}", "X-Context-Token": context_token},
        json={"confirmation_type": "inventory.stock_in"},
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "draft_not_ready"
```

- [ ] **Step 3: 运行测试，确认因为路由不存在而失败**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_clarification_confirmation.py::test_v2_request_confirmation_from_draft_creates_pending_confirmation backend/tests/test_v2_clarification_confirmation.py::test_v2_request_confirmation_from_draft_rejects_missing_draft -q
```

- [ ] **Step 4: 新增 request-confirmation 服务与路由**

`backend/app/services/v2_conversation.py`

```python
def request_v2_confirmation_from_task_draft(...):
    # 读取 task_draft，校验 task_run.status == drafted，
    # 复制 payload 到 confirmation.draft_payload，
    # 推进 task_run.status -> awaiting_confirmation。
```

`backend/app/api/v2/routes/conversation.py`

```python
@router.post("/task-runs/{task_run_id}/confirmations", response_model=V2DataEnvelope[V2ConfirmationData], status_code=status.HTTP_201_CREATED)
def request_confirmation_from_draft_v2(...):
    ...
```

- [ ] **Step 5: 重新运行 confirmation request 测试**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_clarification_confirmation.py::test_v2_request_confirmation_from_draft_creates_pending_confirmation backend/tests/test_v2_clarification_confirmation.py::test_v2_request_confirmation_from_draft_rejects_missing_draft -q
```

Expected:

- `2 passed`

### Task 4: 阶段验收

**Files:**
- Verify: `backend/tests/test_v2_clarification_confirmation.py`
- Modify: `project_docs/generated/openapi-v1.json`

- [ ] **Step 1: 运行 clarification / draft / confirmation 全测试**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_clarification_confirmation.py -q
```

- [ ] **Step 2: 运行 v2 关键回归**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_identity_context.py backend/tests/test_v2_conversation_runtime.py backend/tests/test_v2_clarification_confirmation.py -q
```

- [ ] **Step 3: 刷新 OpenAPI 快照并校验**

Run:

```powershell
$env:PYTHONPATH="backend"; python backend/scripts/generate_openapi_snapshot.py
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_openapi_contract_snapshot.py -q
```

- [ ] **Step 4: 运行全量后端测试**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests -q
```

- [ ] **Step 5: 检查 git 状态并提交**

Run:

```powershell
git status --short
git add backend/app/models/v2_conversation.py backend/app/models/__init__.py backend/alembic/versions/20260418_04_create_v2_task_drafts.py backend/app/contracts/v2/conversation.py backend/app/services/v2_conversation.py backend/app/api/v2/routes/conversation.py backend/tests/test_v2_clarification_confirmation.py docs/superpowers/plans/2026-04-18-ai-native-saas-task-draft-confirm-request.md project_docs/generated/openapi-v1.json
git commit -m "feat: add v2 task draft confirmation request"
```

## 自检

- Spec coverage：补齐了 `drafted` 状态的实体承载，并把任务推进到 `awaiting_confirmation`。
- Placeholder scan：没有 `TBD`、`TODO`、`implement later` 或“类似上一任务”的占位。
- Type consistency：统一使用 `V2TaskDraft`、`draft_payload`、`drafted`、`confirmation_type`。
- 架构约束：draft 是建议态，不是业务真相；只有 confirmation 创建后任务才进入确认边界，ledger commit 仍留到后续切片。
