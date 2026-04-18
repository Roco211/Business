# AI 原生 SaaS V2 追问与确认骨架实施计划

> **给智能执行代理（agentic workers）：** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 按任务逐项实现本计划。步骤使用 checkbox（`- [ ]`）语法跟踪。

**Goal:** 在现有 v2 identity/context 与 conversation runtime 基础上，落地 `clarification / confirmation` 的最小可运行骨架，使任务可以显式进入 `needs_clarification` 与 `awaiting_confirmation`，并通过 v2 上下文约束完成确认列表、批准与拒绝。

**Architecture:** 本阶段继续采用“v2 新增、v1 仅作业务经验参考”的策略。`clarification` 与 `confirmation` 都直接持有 `tenant_id / shop_id / task_run_id`，服务层必须接收显式上下文参数并先按租户与门店限定；批准确认只把任务推进到 deterministic execution 待执行状态，不写入库存真相，拒绝确认则显式终止任务。真正的 interpret / draft / ledger commit / outbox worker 留给后续切片。

**Tech Stack:** Python, FastAPI, Pydantic, SQLAlchemy, Alembic, pytest, SQLite 测试库, MySQL 生产目标

---

## 范围拆分

本计划覆盖最新 design 的 phase 3 中紧接 conversation runtime 的一段：

- `v2_clarifications` 表与 ORM。
- `v2_confirmations` 表与 ORM。
- `V2TaskRun.status` 进入 `needs_clarification` 与 `awaiting_confirmation`。
- `GET /api/v2/confirmations`。
- `POST /api/v2/confirmations/{confirmation_id}/approve`。
- `POST /api/v2/confirmations/{confirmation_id}/reject`。

本计划暂不覆盖：

- LLM interpret / assess / draft worker。
- clarification 回答接口与多轮追问闭环。
- 库存账本、库存投影、审计日志、outbox event。
- approval 后的确定性工具执行。

## 文件结构

- 修改 `backend/app/models/v2_conversation.py`：新增 `V2Clarification` 与 `V2Confirmation`，继续保持 conversation_runtime 领域聚合。
- 修改 `backend/app/models/__init__.py`：导出新增 ORM。
- 新增 `backend/alembic/versions/20260418_03_create_v2_clarifications_confirmations.py`：创建追问与确认表。
- 修改 `backend/app/services/v2_conversation.py`：新增追问、确认创建与确认审批状态转移服务。
- 修改 `backend/app/contracts/v2/conversation.py`：新增 v2 confirmation 请求与响应合同。
- 修改 `backend/app/api/v2/routes/conversation.py`：新增 confirmation API，复用 `Authorization + X-Context-Token` 约束。
- 新增 `backend/tests/test_v2_clarification_confirmation.py`：阶段验收测试。
- 修改 `project_docs/generated/openapi-v1.json`：刷新 v1/v2 共存的 OpenAPI 快照。

### Task 1: v2 clarification / confirmation schema

**Files:**
- Create: `backend/tests/test_v2_clarification_confirmation.py`
- Modify: `backend/app/models/v2_conversation.py`
- Modify: `backend/app/models/__init__.py`
- Create: `backend/alembic/versions/20260418_03_create_v2_clarifications_confirmations.py`

- [x] **Step 1: 写失败测试，固定追问与确认都直接持有 tenant/shop 边界**

```python
from datetime import UTC, datetime

from sqlalchemy import select


def _utc_now_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _seed_v2_task_run(db_session, *, task_run_id: str = "vtask_001") -> None:
    from app.models import (
        V2Account,
        V2ConversationSession,
        V2Message,
        V2Shop,
        V2TaskRun,
        V2Tenant,
    )

    now = _utc_now_naive()
    db_session.add(V2Account(account_id="acct_001", email="owner@example.com", display_name="Owner", password_hash="hash", password_salt="salt", status="active", created_at=now, updated_at=now))
    db_session.add(V2Tenant(tenant_id="tenant_a", name="Tenant A", slug="tenant-a", status="active", plan_code="trial", owner_account_id="acct_001", created_at=now, updated_at=now))
    db_session.add(V2Shop(shop_id="shop_a1", tenant_id="tenant_a", code="a-1", name="Shop A1", locale="zh-CN", timezone="Asia/Shanghai", status="active", created_at=now, updated_at=now))
    db_session.add(V2ConversationSession(session_id="vsess_001", tenant_id="tenant_a", shop_id="shop_a1", session_type="workgroup", title="Workgroup", status="active", initiated_by_account_id="acct_001", created_at=now, updated_at=now))
    db_session.add(V2Message(message_id="vmsg_001", tenant_id="tenant_a", shop_id="shop_a1", session_id="vsess_001", actor_type="account", actor_id="acct_001", message_kind="text", payload_json={"text": "restock cola"}, client_request_id="req_001", created_at=now))
    db_session.add(V2TaskRun(task_run_id=task_run_id, tenant_id="tenant_a", shop_id="shop_a1", session_id="vsess_001", source_message_id="vmsg_001", intent_type="inventory.stock_in", status="captured", risk_level="medium", trace_id="trace_001", result_summary=None, error_code=None, created_at=now, updated_at=now, completed_at=None))
    db_session.commit()


def test_v2_clarification_and_confirmation_schema_persist_context_boundaries(db_session) -> None:
    from app.models import V2Clarification, V2Confirmation

    now = _utc_now_naive()
    _seed_v2_task_run(db_session)
    clarification = V2Clarification(
        clarification_id="vclar_001",
        tenant_id="tenant_a",
        shop_id="shop_a1",
        task_run_id="vtask_001",
        status="pending",
        reason_code="missing_quantity",
        question_text="How many boxes should be stocked in?",
        requested_fields=["quantity"],
        draft_payload={"item_name": "Cola"},
        answer_payload=None,
        answered_by_account_id=None,
        created_at=now,
        answered_at=None,
    )
    confirmation = V2Confirmation(
        confirmation_id="vconf_001",
        tenant_id="tenant_a",
        shop_id="shop_a1",
        task_run_id="vtask_001",
        confirmation_type="inventory.stock_in",
        status="pending",
        draft_payload={"item_name": "Cola", "quantity": 2},
        approved_by_account_id=None,
        resolution_payload=None,
        created_at=now,
        resolved_at=None,
    )
    db_session.add_all([clarification, confirmation])
    db_session.commit()

    persisted = db_session.scalar(select(V2Confirmation).where(V2Confirmation.confirmation_id == "vconf_001"))

    assert persisted is not None
    assert persisted.tenant_id == "tenant_a"
    assert persisted.shop_id == "shop_a1"
```

- [x] **Step 2: 运行测试，确认因为模型或表不存在而失败**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_clarification_confirmation.py::test_v2_clarification_and_confirmation_schema_persist_context_boundaries -q
```

Expected:

- `ImportError`、`AttributeError` 或 `OperationalError: no such table`。

- [x] **Step 3: 新增 ORM 模型**

在 `backend/app/models/v2_conversation.py` 中追加：

```python
class V2Clarification(Base):
    __tablename__ = "v2_clarifications"

    clarification_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("v2_tenants.tenant_id"), nullable=False, index=True)
    shop_id: Mapped[str] = mapped_column(ForeignKey("v2_shops.shop_id"), nullable=False, index=True)
    task_run_id: Mapped[str] = mapped_column(ForeignKey("v2_task_runs.task_run_id"), nullable=False, unique=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    reason_code: Mapped[str] = mapped_column(String(64), nullable=False)
    question_text: Mapped[str] = mapped_column(String(500), nullable=False)
    requested_fields: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    draft_payload: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    answer_payload: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    answered_by_account_id: Mapped[str | None] = mapped_column(ForeignKey("v2_accounts.account_id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False, default=utc_now_naive)
    answered_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)


class V2Confirmation(Base):
    __tablename__ = "v2_confirmations"

    confirmation_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("v2_tenants.tenant_id"), nullable=False, index=True)
    shop_id: Mapped[str] = mapped_column(ForeignKey("v2_shops.shop_id"), nullable=False, index=True)
    task_run_id: Mapped[str] = mapped_column(ForeignKey("v2_task_runs.task_run_id"), nullable=False, unique=True)
    confirmation_type: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    draft_payload: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    approved_by_account_id: Mapped[str | None] = mapped_column(ForeignKey("v2_accounts.account_id"), nullable=True)
    resolution_payload: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False, default=utc_now_naive)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
```

- [x] **Step 4: 导出新增模型**

`backend/app/models/__init__.py`

```python
from app.models.v2_conversation import (
    V2Clarification,
    V2Confirmation,
    V2ConversationSession,
    V2Message,
    V2TaskRun,
)
```

并把 `"V2Clarification"` 与 `"V2Confirmation"` 加入 `__all__`。

- [x] **Step 5: 新增 Alembic 迁移**

`backend/alembic/versions/20260418_03_create_v2_clarifications_confirmations.py`

```python
from alembic import op
import sqlalchemy as sa


revision = "20260418_03"
down_revision = "20260418_02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "v2_clarifications",
        sa.Column("clarification_id", sa.String(length=40), nullable=False),
        sa.Column("tenant_id", sa.String(length=40), nullable=False),
        sa.Column("shop_id", sa.String(length=40), nullable=False),
        sa.Column("task_run_id", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("reason_code", sa.String(length=64), nullable=False),
        sa.Column("question_text", sa.String(length=500), nullable=False),
        sa.Column("requested_fields", sa.JSON(), nullable=False),
        sa.Column("draft_payload", sa.JSON(), nullable=True),
        sa.Column("answer_payload", sa.JSON(), nullable=True),
        sa.Column("answered_by_account_id", sa.String(length=40), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("answered_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["answered_by_account_id"], ["v2_accounts.account_id"]),
        sa.ForeignKeyConstraint(["shop_id"], ["v2_shops.shop_id"]),
        sa.ForeignKeyConstraint(["task_run_id"], ["v2_task_runs.task_run_id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["v2_tenants.tenant_id"]),
        sa.PrimaryKeyConstraint("clarification_id"),
        sa.UniqueConstraint("task_run_id"),
    )
    op.create_index("ix_v2_clarifications_tenant_id", "v2_clarifications", ["tenant_id"], unique=False)
    op.create_index("ix_v2_clarifications_shop_id", "v2_clarifications", ["shop_id"], unique=False)

    op.create_table(
        "v2_confirmations",
        sa.Column("confirmation_id", sa.String(length=40), nullable=False),
        sa.Column("tenant_id", sa.String(length=40), nullable=False),
        sa.Column("shop_id", sa.String(length=40), nullable=False),
        sa.Column("task_run_id", sa.String(length=40), nullable=False),
        sa.Column("confirmation_type", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("draft_payload", sa.JSON(), nullable=False),
        sa.Column("approved_by_account_id", sa.String(length=40), nullable=True),
        sa.Column("resolution_payload", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["approved_by_account_id"], ["v2_accounts.account_id"]),
        sa.ForeignKeyConstraint(["shop_id"], ["v2_shops.shop_id"]),
        sa.ForeignKeyConstraint(["task_run_id"], ["v2_task_runs.task_run_id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["v2_tenants.tenant_id"]),
        sa.PrimaryKeyConstraint("confirmation_id"),
        sa.UniqueConstraint("task_run_id"),
    )
    op.create_index("ix_v2_confirmations_tenant_id", "v2_confirmations", ["tenant_id"], unique=False)
    op.create_index("ix_v2_confirmations_shop_id", "v2_confirmations", ["shop_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_v2_confirmations_shop_id", table_name="v2_confirmations")
    op.drop_index("ix_v2_confirmations_tenant_id", table_name="v2_confirmations")
    op.drop_table("v2_confirmations")
    op.drop_index("ix_v2_clarifications_shop_id", table_name="v2_clarifications")
    op.drop_index("ix_v2_clarifications_tenant_id", table_name="v2_clarifications")
    op.drop_table("v2_clarifications")
```

- [x] **Step 6: 重新运行 schema 测试**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_clarification_confirmation.py::test_v2_clarification_and_confirmation_schema_persist_context_boundaries -q
```

Expected:

- `1 passed`。

### Task 2: 服务层状态转移

**Files:**
- Modify: `backend/tests/test_v2_clarification_confirmation.py`
- Modify: `backend/app/services/v2_conversation.py`

- [x] **Step 1: 写失败测试，确认 task 能进入 `needs_clarification`**

```python
def test_v2_create_clarification_moves_task_to_needs_clarification(db_session) -> None:
    from app.models import V2TaskRun
    from app.services.v2_conversation import create_v2_clarification

    _seed_v2_task_run(db_session, task_run_id="vtask_clarify")

    clarification = create_v2_clarification(
        db_session,
        tenant_id="tenant_a",
        shop_id="shop_a1",
        task_run_id="vtask_clarify",
        reason_code="missing_quantity",
        question_text="How many boxes should be stocked in?",
        requested_fields=["quantity"],
        draft_payload={"item_name": "Cola"},
    )

    task_run = db_session.get(V2TaskRun, "vtask_clarify")
    assert clarification.status == "pending"
    assert task_run is not None
    assert task_run.status == "needs_clarification"
    assert task_run.completed_at is None
```

- [x] **Step 2: 写失败测试，确认 task 能进入 `awaiting_confirmation`**

```python
def test_v2_create_confirmation_moves_task_to_awaiting_confirmation(db_session) -> None:
    from app.models import V2TaskRun
    from app.services.v2_conversation import create_v2_confirmation

    _seed_v2_task_run(db_session, task_run_id="vtask_confirm")

    confirmation = create_v2_confirmation(
        db_session,
        tenant_id="tenant_a",
        shop_id="shop_a1",
        task_run_id="vtask_confirm",
        confirmation_type="inventory.stock_in",
        draft_payload={"item_name": "Cola", "quantity": 2, "unit": "box"},
    )

    task_run = db_session.get(V2TaskRun, "vtask_confirm")
    assert confirmation.status == "pending"
    assert task_run is not None
    assert task_run.status == "awaiting_confirmation"
    assert task_run.completed_at is None
```

- [x] **Step 3: 运行服务测试，确认因为服务函数不存在而失败**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_clarification_confirmation.py::test_v2_create_clarification_moves_task_to_needs_clarification backend/tests/test_v2_clarification_confirmation.py::test_v2_create_confirmation_moves_task_to_awaiting_confirmation -q
```

Expected:

- `ImportError`。

- [x] **Step 4: 实现最小服务层函数与状态常量**

`backend/app/services/v2_conversation.py`

```python
CAPTURED_STATUS = "captured"
DRAFTED_STATUS = "drafted"
NEEDS_CLARIFICATION_STATUS = "needs_clarification"
AWAITING_CONFIRMATION_STATUS = "awaiting_confirmation"
EXECUTING_STATUS = "executing"
REJECTED_STATUS = "rejected"
PENDING_STATUS = "pending"
APPROVED_STATUS = "approved"


class V2TaskRunTransitionError(ValueError):
    pass


class V2ConfirmationConflictError(ValueError):
    pass


def create_v2_clarification(...):
    # 按 tenant/shop/task_run 限定加载 task，创建 pending clarification，并把 task_run.status 改为 needs_clarification。


def create_v2_confirmation(...):
    # 按 tenant/shop/task_run 限定加载 task，创建 pending confirmation，并把 task_run.status 改为 awaiting_confirmation。
```

实际实现必须：

- `task_run` 查询同时包含 `tenant_id` 与 `shop_id`。
- 追问只允许从 `captured / interpreting` 进入 `needs_clarification`。
- 确认只允许从 `captured / drafted` 进入 `awaiting_confirmation`。
- 如果同一个 `task_run` 已有 pending 记录，返回已有记录，保持幂等。
- 如果同一个 `task_run` 已有非 pending 记录，抛出冲突异常。

- [x] **Step 5: 重新运行服务测试**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_clarification_confirmation.py::test_v2_create_clarification_moves_task_to_needs_clarification backend/tests/test_v2_clarification_confirmation.py::test_v2_create_confirmation_moves_task_to_awaiting_confirmation -q
```

Expected:

- `2 passed`。

### Task 3: v2 confirmation API

**Files:**
- Modify: `backend/tests/test_v2_clarification_confirmation.py`
- Modify: `backend/app/contracts/v2/conversation.py`
- Modify: `backend/app/services/v2_conversation.py`
- Modify: `backend/app/api/v2/routes/conversation.py`

- [x] **Step 1: 写测试 helper，使用真实 v2 auth/context/session/message API 创建 task**

```python
def _seed_v2_identity_for_api(db_session) -> None:
    from app.models import V2Account, V2Shop, V2ShopAccess, V2Tenant, V2TenantMembership
    from app.services.v2_identity import hash_v2_password

    now = _utc_now_naive()
    password_salt = "11" * 16
    db_session.add(V2Account(account_id="acct_001", email="owner@example.com", display_name="Owner", password_hash=hash_v2_password("dev-password", password_salt), password_salt=password_salt, status="active", created_at=now, updated_at=now))
    db_session.add(V2Tenant(tenant_id="tenant_a", name="Tenant A", slug="tenant-a", status="active", plan_code="trial", owner_account_id="acct_001", created_at=now, updated_at=now))
    db_session.add(V2TenantMembership(membership_id="mship_tenant_a", tenant_id="tenant_a", account_id="acct_001", role_key="owner", status="active", joined_at=now, updated_at=now))
    db_session.add(V2Shop(shop_id="shop_a1", tenant_id="tenant_a", code="a-1", name="Shop A1", locale="zh-CN", timezone="Asia/Shanghai", status="active", created_at=now, updated_at=now))
    db_session.add(V2ShopAccess(shop_access_id="access_shop_a1", tenant_id="tenant_a", shop_id="shop_a1", membership_id="mship_tenant_a", access_level="write", status="active", created_at=now))
    db_session.commit()


def _create_api_task_run(client, db_session) -> tuple[str, str, str]:
    _seed_v2_identity_for_api(db_session)
    login_response = client.post("/api/v2/auth/login", json={"email": "owner@example.com", "password": "dev-password"})
    token = login_response.json()["data"]["access_token"]
    context_response = client.post("/api/v2/context/select", headers={"Authorization": f"Bearer {token}"}, json={"tenant_id": "tenant_a", "shop_id": "shop_a1"})
    context_token = context_response.json()["data"]["context_token"]
    session_response = client.post("/api/v2/sessions", headers={"Authorization": f"Bearer {token}", "X-Context-Token": context_token}, json={"session_type": "workgroup", "title": "Workgroup"})
    message_response = client.post(f"/api/v2/sessions/{session_response.json()['data']['session_id']}/messages", headers={"Authorization": f"Bearer {token}", "X-Context-Token": context_token}, json={"message_kind": "text", "payload_json": {"text": "restock cola"}, "client_request_id": "confirm_api_msg"})
    return token, context_token, message_response.json()["data"]["task_run_id"]
```

- [x] **Step 2: 写失败测试，确认列表只返回当前 context 下的 pending confirmation**

```python
def test_v2_list_confirmations_returns_current_context_pending_items(client, db_session) -> None:
    from app.services.v2_conversation import create_v2_confirmation

    token, context_token, task_run_id = _create_api_task_run(client, db_session)
    confirmation = create_v2_confirmation(
        db_session,
        tenant_id="tenant_a",
        shop_id="shop_a1",
        task_run_id=task_run_id,
        confirmation_type="inventory.stock_in",
        draft_payload={"item_name": "Cola", "quantity": 2, "unit": "box"},
    )

    response = client.get(
        "/api/v2/confirmations?status=pending&limit=20",
        headers={"Authorization": f"Bearer {token}", "X-Context-Token": context_token},
    )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["count"] == 1
    assert payload["confirmations"][0]["confirmation_id"] == confirmation.confirmation_id
    assert payload["confirmations"][0]["tenant_id"] == "tenant_a"
    assert payload["confirmations"][0]["shop_id"] == "shop_a1"
```

- [x] **Step 3: 写失败测试，确认批准不会直接提交业务真相，而是推进到待确定性执行**

```python
def test_v2_approve_confirmation_records_resolution_and_moves_task_to_executing(client, db_session) -> None:
    from app.models import V2TaskRun
    from app.services.v2_conversation import create_v2_confirmation

    token, context_token, task_run_id = _create_api_task_run(client, db_session)
    confirmation = create_v2_confirmation(
        db_session,
        tenant_id="tenant_a",
        shop_id="shop_a1",
        task_run_id=task_run_id,
        confirmation_type="inventory.stock_in",
        draft_payload={"item_name": "Cola", "quantity": 2, "unit": "box"},
    )

    response = client.post(
        f"/api/v2/confirmations/{confirmation.confirmation_id}/approve",
        headers={"Authorization": f"Bearer {token}", "X-Context-Token": context_token},
        json={"resolution_payload": {"fields": {"item_name": "Cola", "quantity": 2, "unit": "box"}}},
    )

    task_run = db_session.get(V2TaskRun, task_run_id)
    assert response.status_code == 200
    assert response.json()["data"]["status"] == "approved"
    assert response.json()["data"]["approved_by_account_id"] == "acct_001"
    assert task_run is not None
    assert task_run.status == "executing"
    assert task_run.completed_at is None
```

- [x] **Step 4: 写失败测试，确认拒绝会显式拒绝任务**

```python
def test_v2_reject_confirmation_marks_task_rejected(client, db_session) -> None:
    from app.models import V2TaskRun
    from app.services.v2_conversation import create_v2_confirmation

    token, context_token, task_run_id = _create_api_task_run(client, db_session)
    confirmation = create_v2_confirmation(
        db_session,
        tenant_id="tenant_a",
        shop_id="shop_a1",
        task_run_id=task_run_id,
        confirmation_type="inventory.stock_in",
        draft_payload={"item_name": "Cola", "quantity": 2, "unit": "box"},
    )

    response = client.post(
        f"/api/v2/confirmations/{confirmation.confirmation_id}/reject",
        headers={"Authorization": f"Bearer {token}", "X-Context-Token": context_token},
    )

    task_run = db_session.get(V2TaskRun, task_run_id)
    assert response.status_code == 200
    assert response.json()["data"]["status"] == "rejected"
    assert task_run is not None
    assert task_run.status == "rejected"
    assert task_run.completed_at is not None
```

- [x] **Step 5: 运行 API 测试，确认因为路由不存在而失败**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_clarification_confirmation.py::test_v2_list_confirmations_returns_current_context_pending_items backend/tests/test_v2_clarification_confirmation.py::test_v2_approve_confirmation_records_resolution_and_moves_task_to_executing backend/tests/test_v2_clarification_confirmation.py::test_v2_reject_confirmation_marks_task_rejected -q
```

Expected:

- `404` 或 `ImportError`。

- [x] **Step 6: 新增 confirmation 合同**

`backend/app/contracts/v2/conversation.py`

```python
class V2ApproveConfirmationRequest(BaseModel):
    resolution_payload: dict[str, object] = Field(default_factory=dict)


class V2ConfirmationData(BaseModel):
    confirmation_id: str
    tenant_id: str
    shop_id: str
    task_run_id: str
    confirmation_type: str
    status: str
    draft_payload: dict[str, object]
    approved_by_account_id: str | None
    resolution_payload: dict[str, object] | None
    created_at: datetime
    resolved_at: datetime | None


class V2ConfirmationListData(BaseModel):
    confirmations: list[V2ConfirmationData]
    count: int
```

- [x] **Step 7: 新增 list / approve / reject 服务函数**

`backend/app/services/v2_conversation.py`

```python
def list_v2_confirmations(db_session: Session, *, tenant_id: str, shop_id: str, status: str | None, limit: int) -> list[V2Confirmation]:
    # 先限定 tenant_id，再限定 shop_id，再按 status 过滤，按 created_at desc 返回。


def approve_v2_confirmation(db_session: Session, *, tenant_id: str, shop_id: str, confirmation_id: str, resolution_payload: dict[str, object], approved_by_account_id: str) -> V2Confirmation:
    # 只允许 pending confirmation + awaiting_confirmation task。
    # confirmation.status -> approved。
    # task_run.status -> executing。
    # 不写库存、不创建 ledger event。


def reject_v2_confirmation(db_session: Session, *, tenant_id: str, shop_id: str, confirmation_id: str) -> V2Confirmation:
    # 只允许 pending confirmation + awaiting_confirmation task。
    # confirmation.status -> rejected。
    # task_run.status -> rejected，并设置 completed_at。
```

- [x] **Step 8: 新增 v2 confirmation 路由**

`backend/app/api/v2/routes/conversation.py`

```python
@router.get("/confirmations", response_model=V2DataEnvelope[V2ConfirmationListData])
def list_confirmations_v2(...):
    # 复用 require_v2_authenticated_account 与 require_v2_execution_context。


@router.post("/confirmations/{confirmation_id}/approve", response_model=V2DataEnvelope[V2ConfirmationData])
def approve_confirmation_v2(...):
    # context/account mismatch 返回 context_account_mismatch。
    # LookupError 返回 confirmation_not_found。
    # V2ConfirmationConflictError / V2TaskRunTransitionError 返回 confirmation_not_pending。


@router.post("/confirmations/{confirmation_id}/reject", response_model=V2DataEnvelope[V2ConfirmationData])
def reject_confirmation_v2(...):
    # 同 approve，但 resolution_payload 为空，task_run 进入 rejected。
```

- [x] **Step 9: 重新运行 API 测试**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_clarification_confirmation.py::test_v2_list_confirmations_returns_current_context_pending_items backend/tests/test_v2_clarification_confirmation.py::test_v2_approve_confirmation_records_resolution_and_moves_task_to_executing backend/tests/test_v2_clarification_confirmation.py::test_v2_reject_confirmation_marks_task_rejected -q
```

Expected:

- `3 passed`。

### Task 4: 阶段验收与合同刷新

**Files:**
- Verify: `backend/tests/test_v2_clarification_confirmation.py`
- Verify: `backend/tests/test_v2_conversation_runtime.py`
- Verify: `backend/tests/test_v2_identity_context.py`
- Modify: `project_docs/generated/openapi-v1.json`

- [x] **Step 1: 运行新增测试文件**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_clarification_confirmation.py -q
```

Expected:

- 新增测试全部通过。

- [x] **Step 2: 运行 v2 关键回归**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_identity_context.py backend/tests/test_v2_conversation_runtime.py backend/tests/test_v2_clarification_confirmation.py -q
```

Expected:

- v2 identity/context、conversation runtime、clarification/confirmation 全部通过。

- [x] **Step 3: 刷新 OpenAPI snapshot**

Run:

```powershell
$env:PYTHONPATH="backend"; python backend/scripts/generate_openapi_snapshot.py
```

Expected:

- `project_docs/generated/openapi-v1.json` 包含 `/api/v2/confirmations`、`/api/v2/confirmations/{confirmation_id}/approve`、`/api/v2/confirmations/{confirmation_id}/reject`。

- [x] **Step 4: 运行 OpenAPI 合同测试**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_openapi_contract_snapshot.py -q
```

Expected:

- `1 passed`。

- [x] **Step 5: 运行全量后端测试**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests -q
```

Expected:

- 全量后端测试通过。

- [x] **Step 6: 检查 git 状态并提交**

Run:

```powershell
git status --short
git add backend/app/models/v2_conversation.py backend/app/models/__init__.py backend/alembic/versions/20260418_03_create_v2_clarifications_confirmations.py backend/app/services/v2_conversation.py backend/app/contracts/v2/conversation.py backend/app/api/v2/routes/conversation.py backend/tests/test_v2_clarification_confirmation.py project_docs/generated/openapi-v1.json docs/superpowers/plans/2026-04-18-ai-native-saas-clarification-confirmation-skeleton.md
git commit -m "feat: add v2 clarification and confirmation skeleton"
```

Expected:

- 只提交本计划相关文件。

## 自检

- Spec coverage：本计划覆盖 phase 3 中 `clarification`、`confirmation` 与 runtime 状态机骨架的最小可运行部分。
- Placeholder scan：计划没有 `TBD`、`TODO`、`implement later`，也没有“类似上一任务”的占位步骤。
- Type consistency：统一使用 `V2Clarification / V2Confirmation`、`needs_clarification / awaiting_confirmation / executing / rejected`、`draft_payload / resolution_payload`。
- 架构约束：所有新增数据和查询都直接持有并限定 `tenant_id / shop_id`；确认批准不直接写库存真相，拒绝确认会显式终止任务。
