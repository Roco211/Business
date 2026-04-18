# AI 原生 SaaS V2 会话运行时骨架实施计划

> **给智能执行代理（agentic workers）：** 必须使用 `superpowers:subagent-driven-development`（推荐）或 `superpowers:executing-plans` 按任务逐项实现本计划。步骤使用 checkbox（`- [ ]`）语法跟踪。

**Goal:** 在现有 v2 identity/context 基础上，落地显式上下文约束下的 `conversation_session / message / task_run` 最小骨架，让前端或调用方可以在选定 `tenant / shop` 后创建会话、追加消息、自动生成 `captured` 状态的任务运行记录，并查询这些对象。

**Architecture:** 这一阶段继续坚持“v2 新增、v1 不扩展”的策略。会话、消息和任务记录全部带 `tenant_id` 与 `shop_id`，所有业务路由都要求 `Authorization + X-Context-Token` 双重约束；消息提交只做“capture”层落库与 `task_run` 创建，不提前引入解释、确认、出入库工具等后续能力。clarification / confirmation skeleton 作为紧邻下一切片处理，避免把 phase 3 做成不可验证的大任务。

**Tech Stack:** Python, FastAPI, Pydantic, SQLAlchemy, Alembic, pytest, SQLite 测试库, MySQL 生产目标

---

## 范围拆分

本计划覆盖最新 design 的 phase 3 中最先必须可运行的一段：

- `conversation_session`
- `message`
- `task_run`
- `/api/v2/sessions`
- `/api/v2/sessions/{session_id}/messages`
- `/api/v2/task-runs/{task_run_id}`

本计划暂不覆盖：

- clarification 记录模型
- confirmation 记录模型与审批路由
- runtime interpret / assess / confirm / execute worker
- websocket / outbox / projection

这些能力应在本计划完成后，作为下一份计划继续推进。

## 文件结构

- 新增 `backend/app/models/v2_conversation.py`：v2 会话、消息、任务运行 ORM 模型。
- 新增 `backend/alembic/versions/20260418_02_create_v2_conversation_runtime.py`：runtime skeleton schema。
- 新增 `backend/app/contracts/v2/conversation.py`：会话、消息、任务运行响应合同。
- 新增 `backend/app/services/v2_conversation.py`：create/list session、create/list message、get task run。
- 修改 `backend/app/api/v2/routes/identity.py`：如果需要复用上下文读取合同，保持只做 identity/context。
- 新增 `backend/app/api/v2/routes/conversation.py`：conversation runtime 路由。
- 修改 `backend/app/api/v2/router.py`：挂载 conversation router。
- 修改 `backend/app/models/__init__.py`：导入 v2 conversation ORM。
- 新增 `backend/tests/test_v2_conversation_runtime.py`：阶段验收测试。

### Task 1: v2 conversation runtime schema

**Files:**
- Create: `backend/app/models/v2_conversation.py`
- Modify: `backend/app/models/__init__.py`
- Create: `backend/alembic/versions/20260418_02_create_v2_conversation_runtime.py`
- Test: `backend/tests/test_v2_conversation_runtime.py`

- [ ] **Step 1: 写失败测试，证明 conversation session、message、task_run 都直接带 tenant/shop 边界**

```python
from sqlalchemy import select

from app.models import (
    V2ConversationSession,
    V2Message,
    V2TaskRun,
)


def test_v2_runtime_schema_persists_tenant_and_shop_boundaries(db_session) -> None:
    session = V2ConversationSession(
        session_id="vsess_001",
        tenant_id="tenant_a",
        shop_id="shop_a1",
        session_type="workgroup",
        title="A 一号店工作群",
        status="active",
        initiated_by_account_id="acct_001",
    )
    message = V2Message(
        message_id="vmsg_001",
        tenant_id="tenant_a",
        shop_id="shop_a1",
        session_id="vsess_001",
        actor_type="account",
        actor_id="acct_001",
        message_kind="text",
        payload_json={"text": "今天到货两箱可乐"},
        client_request_id="req_001",
    )
    task_run = V2TaskRun(
        task_run_id="vtask_001",
        tenant_id="tenant_a",
        shop_id="shop_a1",
        session_id="vsess_001",
        source_message_id="vmsg_001",
        intent_type="inventory.stock_in",
        status="captured",
        risk_level="medium",
        trace_id="trace_001",
        result_summary=None,
        error_code=None,
    )
    db_session.add_all([session, message, task_run])
    db_session.commit()

    persisted_task_run = db_session.scalar(
        select(V2TaskRun).where(V2TaskRun.task_run_id == "vtask_001")
    )

    assert persisted_task_run is not None
    assert persisted_task_run.tenant_id == "tenant_a"
    assert persisted_task_run.shop_id == "shop_a1"
```

- [ ] **Step 2: 运行测试，确认因为模型或表不存在而失败**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_conversation_runtime.py::test_v2_runtime_schema_persists_tenant_and_shop_boundaries -q
```

Expected:

- `ImportError`、`AttributeError` 或 `OperationalError: no such table`

- [ ] **Step 3: 写 v2 runtime ORM 模型**

`backend/app/models/v2_conversation.py`

```python
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.services.v2_time import utc_now_naive


class V2ConversationSession(Base):
    __tablename__ = "v2_conversation_sessions"

    session_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("v2_tenants.tenant_id"), nullable=False, index=True)
    shop_id: Mapped[str] = mapped_column(ForeignKey("v2_shops.shop_id"), nullable=False, index=True)
    session_type: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    initiated_by_account_id: Mapped[str] = mapped_column(
        ForeignKey("v2_accounts.account_id"),
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False, default=utc_now_naive)
    updated_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False, default=utc_now_naive)


class V2Message(Base):
    __tablename__ = "v2_messages"
    __table_args__ = (
        UniqueConstraint("session_id", "client_request_id", name="uq_v2_messages_session_client_request"),
    )

    message_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("v2_tenants.tenant_id"), nullable=False, index=True)
    shop_id: Mapped[str] = mapped_column(ForeignKey("v2_shops.shop_id"), nullable=False, index=True)
    session_id: Mapped[str] = mapped_column(
        ForeignKey("v2_conversation_sessions.session_id"),
        nullable=False,
        index=True,
    )
    actor_type: Mapped[str] = mapped_column(String(20), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(40), nullable=False)
    message_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    payload_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    client_request_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False, default=utc_now_naive)


class V2TaskRun(Base):
    __tablename__ = "v2_task_runs"

    task_run_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("v2_tenants.tenant_id"), nullable=False, index=True)
    shop_id: Mapped[str] = mapped_column(ForeignKey("v2_shops.shop_id"), nullable=False, index=True)
    session_id: Mapped[str] = mapped_column(
        ForeignKey("v2_conversation_sessions.session_id"),
        nullable=False,
        index=True,
    )
    source_message_id: Mapped[str] = mapped_column(
        ForeignKey("v2_messages.message_id"),
        nullable=False,
        unique=True,
    )
    intent_type: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    risk_level: Mapped[str] = mapped_column(String(20), nullable=False)
    trace_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    result_summary: Mapped[str | None] = mapped_column(String(255), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False, default=utc_now_naive)
    updated_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False, default=utc_now_naive)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
```

- [ ] **Step 4: 写 Alembic 迁移**

`backend/alembic/versions/20260418_02_create_v2_conversation_runtime.py`

```python
from alembic import op
import sqlalchemy as sa


revision = "20260418_02"
down_revision = "20260418_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "v2_conversation_sessions",
        sa.Column("session_id", sa.String(length=40), nullable=False),
        sa.Column("tenant_id", sa.String(length=40), nullable=False),
        sa.Column("shop_id", sa.String(length=40), nullable=False),
        sa.Column("session_type", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("initiated_by_account_id", sa.String(length=40), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["initiated_by_account_id"], ["v2_accounts.account_id"]),
        sa.ForeignKeyConstraint(["shop_id"], ["v2_shops.shop_id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["v2_tenants.tenant_id"]),
        sa.PrimaryKeyConstraint("session_id"),
    )
    op.create_index("ix_v2_conversation_sessions_tenant_id", "v2_conversation_sessions", ["tenant_id"], unique=False)
    op.create_index("ix_v2_conversation_sessions_shop_id", "v2_conversation_sessions", ["shop_id"], unique=False)
    op.create_index(
        "ix_v2_conversation_sessions_initiated_by_account_id",
        "v2_conversation_sessions",
        ["initiated_by_account_id"],
        unique=False,
    )

    op.create_table(
        "v2_messages",
        sa.Column("message_id", sa.String(length=40), nullable=False),
        sa.Column("tenant_id", sa.String(length=40), nullable=False),
        sa.Column("shop_id", sa.String(length=40), nullable=False),
        sa.Column("session_id", sa.String(length=40), nullable=False),
        sa.Column("actor_type", sa.String(length=20), nullable=False),
        sa.Column("actor_id", sa.String(length=40), nullable=False),
        sa.Column("message_kind", sa.String(length=32), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("client_request_id", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["v2_conversation_sessions.session_id"]),
        sa.ForeignKeyConstraint(["shop_id"], ["v2_shops.shop_id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["v2_tenants.tenant_id"]),
        sa.PrimaryKeyConstraint("message_id"),
        sa.UniqueConstraint("session_id", "client_request_id", name="uq_v2_messages_session_client_request"),
    )
    op.create_index("ix_v2_messages_tenant_id", "v2_messages", ["tenant_id"], unique=False)
    op.create_index("ix_v2_messages_shop_id", "v2_messages", ["shop_id"], unique=False)
    op.create_index("ix_v2_messages_session_id", "v2_messages", ["session_id"], unique=False)

    op.create_table(
        "v2_task_runs",
        sa.Column("task_run_id", sa.String(length=40), nullable=False),
        sa.Column("tenant_id", sa.String(length=40), nullable=False),
        sa.Column("shop_id", sa.String(length=40), nullable=False),
        sa.Column("session_id", sa.String(length=40), nullable=False),
        sa.Column("source_message_id", sa.String(length=40), nullable=False),
        sa.Column("intent_type", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("risk_level", sa.String(length=20), nullable=False),
        sa.Column("trace_id", sa.String(length=64), nullable=False),
        sa.Column("result_summary", sa.String(length=255), nullable=True),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["session_id"], ["v2_conversation_sessions.session_id"]),
        sa.ForeignKeyConstraint(["shop_id"], ["v2_shops.shop_id"]),
        sa.ForeignKeyConstraint(["source_message_id"], ["v2_messages.message_id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["v2_tenants.tenant_id"]),
        sa.PrimaryKeyConstraint("task_run_id"),
        sa.UniqueConstraint("source_message_id"),
    )
    op.create_index("ix_v2_task_runs_tenant_id", "v2_task_runs", ["tenant_id"], unique=False)
    op.create_index("ix_v2_task_runs_shop_id", "v2_task_runs", ["shop_id"], unique=False)
    op.create_index("ix_v2_task_runs_session_id", "v2_task_runs", ["session_id"], unique=False)
    op.create_index("ix_v2_task_runs_trace_id", "v2_task_runs", ["trace_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_v2_task_runs_trace_id", table_name="v2_task_runs")
    op.drop_index("ix_v2_task_runs_session_id", table_name="v2_task_runs")
    op.drop_index("ix_v2_task_runs_shop_id", table_name="v2_task_runs")
    op.drop_index("ix_v2_task_runs_tenant_id", table_name="v2_task_runs")
    op.drop_table("v2_task_runs")
    op.drop_index("ix_v2_messages_session_id", table_name="v2_messages")
    op.drop_index("ix_v2_messages_shop_id", table_name="v2_messages")
    op.drop_index("ix_v2_messages_tenant_id", table_name="v2_messages")
    op.drop_table("v2_messages")
    op.drop_index("ix_v2_conversation_sessions_initiated_by_account_id", table_name="v2_conversation_sessions")
    op.drop_index("ix_v2_conversation_sessions_shop_id", table_name="v2_conversation_sessions")
    op.drop_index("ix_v2_conversation_sessions_tenant_id", table_name="v2_conversation_sessions")
    op.drop_table("v2_conversation_sessions")
```

- [ ] **Step 5: 导入模型并重新运行 schema 测试**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_conversation_runtime.py::test_v2_runtime_schema_persists_tenant_and_shop_boundaries -q
```

Expected:

- `1 passed`

- [ ] **Step 6: Commit**

```bash
git add backend/app/models/v2_conversation.py backend/app/models/__init__.py backend/alembic/versions/20260418_02_create_v2_conversation_runtime.py backend/tests/test_v2_conversation_runtime.py
git commit -m "feat: add v2 conversation runtime schema"
```

### Task 2: 创建与列出 v2 session

**Files:**
- Create: `backend/app/contracts/v2/conversation.py`
- Create: `backend/app/services/v2_conversation.py`
- Create: `backend/app/api/v2/routes/conversation.py`
- Modify: `backend/app/api/v2/router.py`
- Test: `backend/tests/test_v2_conversation_runtime.py`

- [ ] **Step 1: 先在测试文件写共享 helper，显式创建 v2 account、context，并返回 `token + context_token`**

```python
def seed_v2_login_and_context(client, db_session) -> tuple[str, str]:
    seed_v2_identity(
        db_session,
        account_id="acct_001",
        email="owner@example.com",
        password="dev-password",
        tenants=[("tenant_a", "A 商家")],
        shops={"tenant_a": [("shop_a1", "A 一号店")]},
        accessible_shops=["shop_a1"],
    )
    login_response = client.post(
        "/api/v2/auth/login",
        json={"email": "owner@example.com", "password": "dev-password"},
    )
    token = login_response.json()["data"]["access_token"]
    select_response = client.post(
        "/api/v2/context/select",
        headers={"Authorization": f"Bearer {token}"},
        json={"tenant_id": "tenant_a", "shop_id": "shop_a1"},
    )
    return token, select_response.json()["data"]["context_token"]
```

- [ ] **Step 2: 写失败测试，确认创建 session 必须使用 execution context，并从 context 继承 tenant/shop**

```python
def test_v2_create_session_uses_execution_context_boundaries(client, db_session) -> None:
    token, context_token = seed_v2_login_and_context(client, db_session)

    response = client.post(
        "/api/v2/sessions",
        headers={
            "Authorization": f"Bearer {token}",
            "X-Context-Token": context_token,
        },
        json={
            "session_type": "workgroup",
            "title": "A 一号店工作群",
        },
    )

    assert response.status_code == 201
    payload = response.json()["data"]
    assert payload["tenant_id"] == "tenant_a"
    assert payload["shop_id"] == "shop_a1"
    assert payload["session_type"] == "workgroup"
```

- [ ] **Step 3: 写失败测试，确认列出 session 只返回当前 tenant/shop 下的对象**

```python
def test_v2_list_sessions_only_returns_current_context_scope(client, db_session) -> None:
    token, context_token = seed_v2_login_and_context(client, db_session)

    first = client.post(
        "/api/v2/sessions",
        headers={"Authorization": f"Bearer {token}", "X-Context-Token": context_token},
        json={"session_type": "workgroup", "title": "会话一"},
    )
    second = client.post(
        "/api/v2/sessions",
        headers={"Authorization": f"Bearer {token}", "X-Context-Token": context_token},
        json={"session_type": "receipt", "title": "会话二"},
    )
    response = client.get(
        "/api/v2/sessions",
        headers={"Authorization": f"Bearer {token}", "X-Context-Token": context_token},
    )

    assert first.status_code == 201
    assert second.status_code == 201
    assert response.status_code == 200
    assert [item["title"] for item in response.json()["data"]["sessions"]] == ["会话二", "会话一"]
```

- [ ] **Step 4: 运行 session 测试，确认因为路由不存在而失败**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_conversation_runtime.py::test_v2_create_session_uses_execution_context_boundaries backend/tests/test_v2_conversation_runtime.py::test_v2_list_sessions_only_returns_current_context_scope -q
```

Expected:

- `404 != 201` 或 `404 != 200`

- [ ] **Step 5: 写合同、服务与路由最小实现**

`backend/app/contracts/v2/conversation.py`

```python
from pydantic import BaseModel


class V2CreateSessionRequest(BaseModel):
    session_type: str
    title: str


class V2SessionData(BaseModel):
    session_id: str
    tenant_id: str
    shop_id: str
    session_type: str
    title: str
    status: str
    initiated_by_account_id: str


class V2SessionListData(BaseModel):
    sessions: list[V2SessionData]
```

`backend/app/services/v2_conversation.py`

```python
from dataclasses import dataclass
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import V2ConversationSession
from app.services.v2_time import utc_now_naive


@dataclass(frozen=True)
class CreatedV2Session:
    session_id: str
    tenant_id: str
    shop_id: str
    session_type: str
    title: str
    status: str
    initiated_by_account_id: str


def create_v2_session(
    db_session: Session,
    *,
    tenant_id: str,
    shop_id: str,
    initiated_by_account_id: str,
    session_type: str,
    title: str,
) -> CreatedV2Session:
    now = utc_now_naive()
    session = V2ConversationSession(
        session_id=f"vsess_{uuid.uuid4().hex}"[:40],
        tenant_id=tenant_id,
        shop_id=shop_id,
        session_type=session_type,
        title=title,
        status="active",
        initiated_by_account_id=initiated_by_account_id,
        created_at=now,
        updated_at=now,
    )
    db_session.add(session)
    db_session.commit()
    return CreatedV2Session(
        session_id=session.session_id,
        tenant_id=session.tenant_id,
        shop_id=session.shop_id,
        session_type=session.session_type,
        title=session.title,
        status=session.status,
        initiated_by_account_id=session.initiated_by_account_id,
    )


def list_v2_sessions(
    db_session: Session,
    *,
    tenant_id: str,
    shop_id: str,
) -> list[V2ConversationSession]:
    return list(
        db_session.scalars(
            select(V2ConversationSession)
            .where(
                V2ConversationSession.tenant_id == tenant_id,
                V2ConversationSession.shop_id == shop_id,
            )
            .order_by(V2ConversationSession.created_at.desc(), V2ConversationSession.session_id.desc())
        )
    )
```

`backend/app/api/v2/routes/conversation.py`

```python
from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api.deps.v2_context import (
    V2AuthenticatedAccount,
    V2ExecutionContext,
    require_v2_authenticated_account,
    require_v2_execution_context,
)
from app.contracts.v2.common import V2DataEnvelope, V2ErrorBody, V2ErrorEnvelope
from app.contracts.v2.conversation import (
    V2CreateSessionRequest,
    V2SessionData,
    V2SessionListData,
)
from app.db.session import get_db_session
from app.services.v2_conversation import create_v2_session, list_v2_sessions

router = APIRouter(prefix="/api/v2", tags=["v2-conversation"])


@router.post("/sessions", response_model=V2DataEnvelope[V2SessionData], status_code=status.HTTP_201_CREATED)
def create_session_v2(
    payload: V2CreateSessionRequest,
    account: V2AuthenticatedAccount = Depends(require_v2_authenticated_account),
    context: V2ExecutionContext = Depends(require_v2_execution_context),
    db_session: Session = Depends(get_db_session),
) -> V2DataEnvelope[V2SessionData] | JSONResponse:
    if account.account_id != context.account_id:
        return JSONResponse(
            status_code=403,
            content=V2ErrorEnvelope(
                error=V2ErrorBody(code="context_account_mismatch", message="Context account mismatch")
            ).model_dump(),
        )
    created = create_v2_session(
        db_session,
        tenant_id=context.tenant_id,
        shop_id=context.shop_id,
        initiated_by_account_id=context.account_id,
        session_type=payload.session_type,
        title=payload.title,
    )
    return V2DataEnvelope(data=V2SessionData(**created.__dict__))


@router.get("/sessions", response_model=V2DataEnvelope[V2SessionListData])
def list_sessions_v2(
    account: V2AuthenticatedAccount = Depends(require_v2_authenticated_account),
    context: V2ExecutionContext = Depends(require_v2_execution_context),
    db_session: Session = Depends(get_db_session),
) -> V2DataEnvelope[V2SessionListData] | JSONResponse:
    if account.account_id != context.account_id:
        return JSONResponse(
            status_code=403,
            content=V2ErrorEnvelope(
                error=V2ErrorBody(code="context_account_mismatch", message="Context account mismatch")
            ).model_dump(),
        )
    sessions = [
        V2SessionData(
            session_id=item.session_id,
            tenant_id=item.tenant_id,
            shop_id=item.shop_id,
            session_type=item.session_type,
            title=item.title,
            status=item.status,
            initiated_by_account_id=item.initiated_by_account_id,
        )
        for item in list_v2_sessions(
            db_session,
            tenant_id=context.tenant_id,
            shop_id=context.shop_id,
        )
    ]
    return V2DataEnvelope(data=V2SessionListData(sessions=sessions))
```

- [ ] **Step 6: 挂载 router 并跑 session 测试**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_conversation_runtime.py::test_v2_create_session_uses_execution_context_boundaries backend/tests/test_v2_conversation_runtime.py::test_v2_list_sessions_only_returns_current_context_scope -q
```

Expected:

- `2 passed`

- [ ] **Step 7: Commit**

```bash
git add backend/app/contracts/v2/conversation.py backend/app/services/v2_conversation.py backend/app/api/v2/routes/conversation.py backend/app/api/v2/router.py backend/tests/test_v2_conversation_runtime.py
git commit -m "feat: add v2 conversation sessions"
```

### Task 3: 创建与列出 v2 message，并自动生成 captured task_run

**Files:**
- Modify: `backend/app/contracts/v2/conversation.py`
- Modify: `backend/app/services/v2_conversation.py`
- Modify: `backend/app/api/v2/routes/conversation.py`
- Test: `backend/tests/test_v2_conversation_runtime.py`

- [ ] **Step 1: 写失败测试，确认追加消息时会自动创建 `captured` 任务**

```python
def test_v2_post_message_creates_message_and_captured_task_run(client, db_session) -> None:
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
            "payload_json": {"text": "今天到货两箱可乐"},
            "client_request_id": "v2_msg_001",
        },
    )

    assert response.status_code == 201
    payload = response.json()["data"]
    assert payload["message_id"].startswith("vmsg_")
    assert payload["task_run_id"].startswith("vtask_")
    assert payload["status"] == "captured"
```

- [ ] **Step 2: 写失败测试，确认列出消息只返回当前 session 且按时间正序**

```python
def test_v2_list_messages_returns_session_scoped_history(client, db_session) -> None:
    token, context_token = seed_v2_login_and_context(client, db_session)
    session_response = client.post(
        "/api/v2/sessions",
        headers={"Authorization": f"Bearer {token}", "X-Context-Token": context_token},
        json={"session_type": "workgroup", "title": "工作群"},
    )
    session_id = session_response.json()["data"]["session_id"]
    client.post(
        f"/api/v2/sessions/{session_id}/messages",
        headers={"Authorization": f"Bearer {token}", "X-Context-Token": context_token},
        json={"message_kind": "text", "payload_json": {"text": "one"}, "client_request_id": "v2_msg_hist_1"},
    )
    client.post(
        f"/api/v2/sessions/{session_id}/messages",
        headers={"Authorization": f"Bearer {token}", "X-Context-Token": context_token},
        json={"message_kind": "text", "payload_json": {"text": "two"}, "client_request_id": "v2_msg_hist_2"},
    )

    response = client.get(
        f"/api/v2/sessions/{session_id}/messages",
        headers={"Authorization": f"Bearer {token}", "X-Context-Token": context_token},
    )

    assert response.status_code == 200
    assert [item["payload_json"]["text"] for item in response.json()["data"]["messages"]] == ["one", "two"]
```

- [ ] **Step 3: 运行 message 测试，确认红灯**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_conversation_runtime.py::test_v2_post_message_creates_message_and_captured_task_run backend/tests/test_v2_conversation_runtime.py::test_v2_list_messages_returns_session_scoped_history -q
```

Expected:

- `404` 或 `422`

- [ ] **Step 4: 写消息合同、服务与路由最小实现**

`backend/app/contracts/v2/conversation.py`

```python
class V2CreateMessageRequest(BaseModel):
    message_kind: str
    payload_json: dict[str, object]
    client_request_id: str | None = None


class V2CreateMessageData(BaseModel):
    message_id: str
    task_run_id: str
    status: str


class V2MessageData(BaseModel):
    message_id: str
    tenant_id: str
    shop_id: str
    session_id: str
    actor_type: str
    actor_id: str
    message_kind: str
    payload_json: dict[str, object]
    client_request_id: str | None
    created_at: datetime


class V2MessageListData(BaseModel):
    messages: list[V2MessageData]
```

`backend/app/services/v2_conversation.py`

```python
def create_v2_message_and_task_run(
    db_session: Session,
    *,
    tenant_id: str,
    shop_id: str,
    session_id: str,
    actor_id: str,
    message_kind: str,
    payload_json: dict[str, object],
    client_request_id: str | None,
) -> tuple[V2Message, V2TaskRun] | None:
    session = db_session.scalar(
        select(V2ConversationSession).where(
            V2ConversationSession.session_id == session_id,
            V2ConversationSession.tenant_id == tenant_id,
            V2ConversationSession.shop_id == shop_id,
        )
    )
    if session is None:
        return None
    now = utc_now_naive()
    message = V2Message(
        message_id=f"vmsg_{uuid.uuid4().hex}"[:40],
        tenant_id=tenant_id,
        shop_id=shop_id,
        session_id=session_id,
        actor_type="account",
        actor_id=actor_id,
        message_kind=message_kind,
        payload_json=payload_json,
        client_request_id=client_request_id,
        created_at=now,
    )
    task_run = V2TaskRun(
        task_run_id=f"vtask_{uuid.uuid4().hex}"[:40],
        tenant_id=tenant_id,
        shop_id=shop_id,
        session_id=session_id,
        source_message_id=message.message_id,
        intent_type="conversation.capture",
        status="captured",
        risk_level="unknown",
        trace_id=f"trace_{uuid.uuid4().hex}",
        result_summary=None,
        error_code=None,
        created_at=now,
        updated_at=now,
        completed_at=None,
    )
    db_session.add(message)
    db_session.add(task_run)
    db_session.commit()
    return message, task_run


def list_v2_messages(
    db_session: Session,
    *,
    tenant_id: str,
    shop_id: str,
    session_id: str,
) -> list[V2Message]:
    return list(
        db_session.scalars(
            select(V2Message)
            .where(
                V2Message.tenant_id == tenant_id,
                V2Message.shop_id == shop_id,
                V2Message.session_id == session_id,
            )
            .order_by(V2Message.created_at.asc(), V2Message.message_id.asc())
        )
    )
```

`backend/app/api/v2/routes/conversation.py`

```python
@router.post("/sessions/{session_id}/messages", response_model=V2DataEnvelope[V2CreateMessageData], status_code=status.HTTP_201_CREATED)
def post_message_v2(
    session_id: str,
    payload: V2CreateMessageRequest,
    account: V2AuthenticatedAccount = Depends(require_v2_authenticated_account),
    context: V2ExecutionContext = Depends(require_v2_execution_context),
    db_session: Session = Depends(get_db_session),
) -> V2DataEnvelope[V2CreateMessageData] | JSONResponse:
    created = create_v2_message_and_task_run(
        db_session,
        tenant_id=context.tenant_id,
        shop_id=context.shop_id,
        session_id=session_id,
        actor_id=account.account_id,
        message_kind=payload.message_kind,
        payload_json=payload.payload_json,
        client_request_id=payload.client_request_id,
    )
    if created is None:
        return JSONResponse(
            status_code=404,
            content=V2ErrorEnvelope(
                error=V2ErrorBody(code="session_not_found", message="Session not found")
            ).model_dump(),
        )
    message, task_run = created
    return V2DataEnvelope(
        data=V2CreateMessageData(
            message_id=message.message_id,
            task_run_id=task_run.task_run_id,
            status=task_run.status,
        )
    )


@router.get("/sessions/{session_id}/messages", response_model=V2DataEnvelope[V2MessageListData])
def list_messages_v2(
    session_id: str,
    account: V2AuthenticatedAccount = Depends(require_v2_authenticated_account),
    context: V2ExecutionContext = Depends(require_v2_execution_context),
    db_session: Session = Depends(get_db_session),
) -> V2DataEnvelope[V2MessageListData] | JSONResponse:
    if account.account_id != context.account_id:
        return JSONResponse(
            status_code=403,
            content=V2ErrorEnvelope(
                error=V2ErrorBody(code="context_account_mismatch", message="Context account mismatch")
            ).model_dump(),
        )
    messages = [
        V2MessageData(
            message_id=item.message_id,
            tenant_id=item.tenant_id,
            shop_id=item.shop_id,
            session_id=item.session_id,
            actor_type=item.actor_type,
            actor_id=item.actor_id,
            message_kind=item.message_kind,
            payload_json=item.payload_json,
            client_request_id=item.client_request_id,
            created_at=item.created_at,
        )
        for item in list_v2_messages(
            db_session,
            tenant_id=context.tenant_id,
            shop_id=context.shop_id,
            session_id=session_id,
        )
    ]
    return V2DataEnvelope(data=V2MessageListData(messages=messages))
```

- [ ] **Step 5: 重新运行 message 测试**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_conversation_runtime.py::test_v2_post_message_creates_message_and_captured_task_run backend/tests/test_v2_conversation_runtime.py::test_v2_list_messages_returns_session_scoped_history -q
```

Expected:

- `2 passed`

- [ ] **Step 6: Commit**

```bash
git add backend/app/contracts/v2/conversation.py backend/app/services/v2_conversation.py backend/app/api/v2/routes/conversation.py backend/tests/test_v2_conversation_runtime.py
git commit -m "feat: add v2 messages and captured task runs"
```

### Task 4: 查询 task_run 与阶段验收

**Files:**
- Modify: `backend/app/contracts/v2/conversation.py`
- Modify: `backend/app/api/v2/routes/conversation.py`
- Test: `backend/tests/test_v2_conversation_runtime.py`

- [ ] **Step 1: 写失败测试，确认 task_run 查询必须受当前上下文约束**

```python
def test_v2_get_task_run_returns_runtime_state_shape(client, db_session) -> None:
    token, context_token = seed_v2_login_and_context(client, db_session)
    session_response = client.post(
        "/api/v2/sessions",
        headers={"Authorization": f"Bearer {token}", "X-Context-Token": context_token},
        json={"session_type": "workgroup", "title": "工作群"},
    )
    session_id = session_response.json()["data"]["session_id"]
    message_response = client.post(
        f"/api/v2/sessions/{session_id}/messages",
        headers={"Authorization": f"Bearer {token}", "X-Context-Token": context_token},
        json={"message_kind": "text", "payload_json": {"text": "task"}, "client_request_id": "v2_task_query_1"},
    )
    task_run_id = message_response.json()["data"]["task_run_id"]

    response = client.get(
        f"/api/v2/task-runs/{task_run_id}",
        headers={"Authorization": f"Bearer {token}", "X-Context-Token": context_token},
    )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["task_run_id"] == task_run_id
    assert payload["status"] == "captured"
    assert payload["intent_type"] == "conversation.capture"
    assert payload["tenant_id"] == "tenant_a"
    assert payload["shop_id"] == "shop_a1"
```

- [ ] **Step 2: 运行 task_run 测试，确认红灯**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_conversation_runtime.py::test_v2_get_task_run_returns_runtime_state_shape -q
```

Expected:

- `404`

- [ ] **Step 3: 写 `GET /api/v2/task-runs/{task_run_id}` 最小实现**

`backend/app/contracts/v2/conversation.py`

```python
class V2TaskRunData(BaseModel):
    task_run_id: str
    tenant_id: str
    shop_id: str
    session_id: str
    source_message_id: str
    intent_type: str
    status: str
    risk_level: str
    trace_id: str
    result_summary: str | None
    error_code: str | None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None
```

`backend/app/api/v2/routes/conversation.py`

```python
@router.get("/task-runs/{task_run_id}", response_model=V2DataEnvelope[V2TaskRunData])
def get_task_run_v2(
    task_run_id: str,
    account: V2AuthenticatedAccount = Depends(require_v2_authenticated_account),
    context: V2ExecutionContext = Depends(require_v2_execution_context),
    db_session: Session = Depends(get_db_session),
) -> V2DataEnvelope[V2TaskRunData] | JSONResponse:
    if account.account_id != context.account_id:
        return JSONResponse(
            status_code=403,
            content=V2ErrorEnvelope(
                error=V2ErrorBody(code="context_account_mismatch", message="Context account mismatch")
            ).model_dump(),
        )
    task_run = db_session.scalar(
        select(V2TaskRun).where(
            V2TaskRun.task_run_id == task_run_id,
            V2TaskRun.tenant_id == context.tenant_id,
            V2TaskRun.shop_id == context.shop_id,
        )
    )
    if task_run is None:
        return JSONResponse(
            status_code=404,
            content=V2ErrorEnvelope(
                error=V2ErrorBody(code="task_run_not_found", message="Task run not found")
            ).model_dump(),
        )
    return V2DataEnvelope(
        data=V2TaskRunData(
            task_run_id=task_run.task_run_id,
            tenant_id=task_run.tenant_id,
            shop_id=task_run.shop_id,
            session_id=task_run.session_id,
            source_message_id=task_run.source_message_id,
            intent_type=task_run.intent_type,
            status=task_run.status,
            risk_level=task_run.risk_level,
            trace_id=task_run.trace_id,
            result_summary=task_run.result_summary,
            error_code=task_run.error_code,
            created_at=task_run.created_at,
            updated_at=task_run.updated_at,
            completed_at=task_run.completed_at,
        )
    )
```

- [ ] **Step 4: 跑 task_run 测试**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_conversation_runtime.py::test_v2_get_task_run_returns_runtime_state_shape -q
```

Expected:

- `1 passed`

- [ ] **Step 5: 运行本阶段新增测试**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_conversation_runtime.py -q
```

Expected:

- 本文件全部通过

- [ ] **Step 6: 运行关键回归**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_identity_context.py backend/tests/test_openapi_contract_snapshot.py -q
```

Expected:

- v2 identity/context 不回退
- OpenAPI 快照如失败，应先用 `python backend/scripts/generate_openapi_snapshot.py` 更新，再重新验证

- [ ] **Step 7: 运行全量后端测试**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests -q
```

Expected:

- 全量通过

- [ ] **Step 8: Commit**

```bash
git add backend/app/contracts/v2/conversation.py backend/app/api/v2/routes/conversation.py backend/tests/test_v2_conversation_runtime.py project_docs/generated/openapi-v1.json
git commit -m "feat: add v2 conversation runtime skeleton"
```

## 自检

- Spec coverage：本计划覆盖 phase 3 中 conversation/message/task_run 的最小可运行骨架。
- Placeholder scan：计划没有占位标记、延后实现表述或“类似 Task N”的占位表述。
- Type consistency：`V2ConversationSession / V2Message / V2TaskRun`、`session_type / message_kind / intent_type / status` 在后续任务中保持同一命名。
- 架构约束：所有 runtime 对象都直接带 `tenant_id` 与 `shop_id`，路由必须依赖 `Authorization + X-Context-Token`，不会回退到只靠主键回溯上下文。
