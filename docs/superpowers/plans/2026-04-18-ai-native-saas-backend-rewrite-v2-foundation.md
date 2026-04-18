# AI 原生 SaaS 后端重构 V2 基础实施计划（Implementation Plan）

> **给智能执行代理（agentic workers）：** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 按任务逐项实现本计划。步骤使用 checkbox（`- [ ]`）语法跟踪。

**Goal:** 在不继续扩展旧 `/api/v1` 错误边界的前提下，落地 `/api/v2` 骨架、身份（identity）、租户（tenant）、门店（shop）与显式上下文（context session）基础，让账号登录后先获得账号级登录态，再显式选择当前租户和门店。

**Architecture:** 本阶段采用“并行新增 `/api/v2` + 保持 `/api/v1` 可运行”的模块化单体过渡方式。新实现只依赖 `account -> tenant -> shop -> membership -> shop access -> context session` 边界，不复用旧的 `shop = tenant`、登录绑定 `shop_id`、默认店铺 bootstrap 等假设。数据库侧优先用新增 v2 表承载新语义，避免为兼容旧接口而污染新模型。

**Tech Stack:** Python, FastAPI, Pydantic, SQLAlchemy, Alembic, pytest, SQLite 测试库, MySQL 生产目标

---

## 范围拆分

最新 spec 覆盖 identity、tenant/shop、workspace context、conversation runtime、inventory ledger、media AI platform、audit governance、async realtime 八个核心域。为避免把多个独立子系统塞进一份不可执行的大计划，本计划只覆盖首个可验证切片：

- `/api/v2` 路由骨架与共享响应模型。
- 新身份与上下文基础表。
- v2 登录、列出租户、列出门店、选择上下文、读取当前上下文。
- 明确阻断“无上下文执行业务动作”的依赖入口。

后续应继续拆出这些独立计划：

- Conversation Runtime V2：会话、消息、任务状态机、追问与确认。
- Inventory Ledger V2：tenant 级商品档案、shop 级库存投影、事件账本与纠错。
- Media / AI Platform V2：media asset、document、model call log、provider 抽象。
- Outbox / Worker / Realtime V2：可靠异步、投影、websocket replay。

## 文件结构

- 新增 `backend/app/api/v2/`：v2 路由聚合与版本化路由边界。
- 新增 `backend/app/contracts/v2/`：v2 请求、响应与错误合同。
- 新增 `backend/app/models/v2_identity.py`：v2 身份、租户、门店访问、上下文 ORM 模型。
- 新增 `backend/app/services/v2_identity.py`：账号登录、租户/门店访问查询、上下文选择服务。
- 新增 `backend/app/api/deps/v2_context.py`：账号登录态与业务上下文依赖。
- 新增 `backend/alembic/versions/20260418_01_create_v2_identity_context.py`：首批 v2 schema。
- 新增 `backend/tests/test_v2_identity_context.py`：阶段验收测试。
- 修改 `backend/app/api/router.py`：挂载 v2 router，不移除现有 v1 router。
- 修改 `backend/app/models/__init__.py`：导入 v2 ORM，保证 Alembic 和测试能发现 metadata。

### Task 1: `/api/v2` 路由骨架与共享合同

**Files:**
- Create: `backend/app/api/v2/__init__.py`
- Create: `backend/app/api/v2/router.py`
- Create: `backend/app/api/v2/routes/__init__.py`
- Create: `backend/app/api/v2/routes/health.py`
- Create: `backend/app/contracts/v2/__init__.py`
- Create: `backend/app/contracts/v2/common.py`
- Modify: `backend/app/api/router.py`
- Test: `backend/tests/test_v2_identity_context.py`

- [ ] **Step 1: 写失败测试，固定 v2 health 入口**

```python
def test_v2_health_returns_versioned_envelope(client) -> None:
    response = client.get("/api/v2/health")

    assert response.status_code == 200
    assert response.json() == {
        "data": {
            "status": "ok",
            "api_version": "v2",
        }
    }
```

- [ ] **Step 2: 运行测试，确认因为路由不存在而失败**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_identity_context.py::test_v2_health_returns_versioned_envelope -q
```

Expected:

- 失败原因是 `404 != 200`。
- 如果是导入错误，先修正测试导入再重新确认红灯（RED）。

- [ ] **Step 3: 写最小 v2 合同和路由实现**

`backend/app/contracts/v2/common.py`

```python
from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class V2DataEnvelope(BaseModel, Generic[T]):
    data: T


class V2ErrorDetail(BaseModel):
    field: str | None = None
    message: str


class V2ErrorBody(BaseModel):
    code: str
    message: str
    details: list[V2ErrorDetail] = Field(default_factory=list)


class V2ErrorEnvelope(BaseModel):
    error: V2ErrorBody
```

`backend/app/api/v2/routes/health.py`

```python
from pydantic import BaseModel
from fastapi import APIRouter

from app.contracts.v2.common import V2DataEnvelope

router = APIRouter(prefix="/api/v2", tags=["v2-system"])


class V2HealthData(BaseModel):
    status: str
    api_version: str


@router.get("/health", response_model=V2DataEnvelope[V2HealthData])
def v2_health() -> V2DataEnvelope[V2HealthData]:
    return V2DataEnvelope(data=V2HealthData(status="ok", api_version="v2"))
```

`backend/app/api/v2/router.py`

```python
from fastapi import APIRouter

from app.api.v2.routes.health import router as health_router

v2_router = APIRouter()
v2_router.include_router(health_router)
```

`backend/app/api/router.py`

```python
from app.api.v2.router import v2_router

api_router.include_router(v2_router)
```

- [ ] **Step 4: 运行 v2 health 测试确认绿灯**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_identity_context.py::test_v2_health_returns_versioned_envelope -q
```

Expected:

- `1 passed`

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/router.py backend/app/api/v2 backend/app/contracts/v2 backend/tests/test_v2_identity_context.py
git commit -m "feat: add v2 api foundation"
```

### Task 2: v2 身份、租户、门店访问与上下文数据模型

**Files:**
- Create: `backend/app/services/v2_time.py`
- Create: `backend/app/models/v2_identity.py`
- Modify: `backend/app/models/__init__.py`
- Create: `backend/alembic/versions/20260418_01_create_v2_identity_context.py`
- Test: `backend/tests/test_v2_identity_context.py`

- [ ] **Step 1: 写失败测试，证明账号可属于两个租户且租户可包含多个门店**

```python
from sqlalchemy import select

from app.models import V2Account, V2Shop, V2Tenant, V2TenantMembership


def test_v2_schema_supports_account_multiple_tenants_and_tenant_multiple_shops(db_session) -> None:
    account = V2Account(
        account_id="acct_001",
        email="owner@example.com",
        display_name="Owner",
        password_hash="hash",
        password_salt="salt",
        status="active",
    )
    tenant_a = V2Tenant(
        tenant_id="tenant_a",
        name="A 商家",
        slug="tenant-a",
        status="active",
        plan_code="trial",
        owner_account_id="acct_001",
    )
    tenant_b = V2Tenant(
        tenant_id="tenant_b",
        name="B 商家",
        slug="tenant-b",
        status="active",
        plan_code="trial",
        owner_account_id="acct_001",
    )
    shop_a1 = V2Shop(
        shop_id="shop_a1",
        tenant_id="tenant_a",
        code="a-1",
        name="A 一号店",
        locale="zh-CN",
        timezone="Asia/Shanghai",
        status="active",
    )
    shop_a2 = V2Shop(
        shop_id="shop_a2",
        tenant_id="tenant_a",
        code="a-2",
        name="A 二号店",
        locale="zh-CN",
        timezone="Asia/Shanghai",
        status="active",
    )
    db_session.add_all(
        [
            account,
            tenant_a,
            tenant_b,
            V2TenantMembership(
                membership_id="mship_a",
                tenant_id="tenant_a",
                account_id="acct_001",
                role_key="owner",
                status="active",
            ),
            V2TenantMembership(
                membership_id="mship_b",
                tenant_id="tenant_b",
                account_id="acct_001",
                role_key="owner",
                status="active",
            ),
            shop_a1,
            shop_a2,
        ]
    )
    db_session.commit()

    memberships = db_session.scalars(
        select(V2TenantMembership).where(V2TenantMembership.account_id == "acct_001")
    ).all()
    shops = db_session.scalars(select(V2Shop).where(V2Shop.tenant_id == "tenant_a")).all()

    assert {membership.tenant_id for membership in memberships} == {"tenant_a", "tenant_b"}
    assert {shop.shop_id for shop in shops} == {"shop_a1", "shop_a2"}
```

- [ ] **Step 2: 运行测试，确认因为模型不存在或表不存在而失败**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_identity_context.py::test_v2_schema_supports_account_multiple_tenants_and_tenant_multiple_shops -q
```

Expected:

- 失败原因是 `ImportError`、`AttributeError` 或 `OperationalError: no such table`。

- [ ] **Step 3: 先新增共享时间工具，避免 ORM 和服务各自复制时间实现**

`backend/app/services/v2_time.py`

```python
from datetime import UTC, datetime


def utc_now_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)
```

- [ ] **Step 4: 新增 v2 ORM 模型**

`backend/app/models/v2_identity.py`

```python
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.services.v2_time import utc_now_naive


class V2Account(Base):
    __tablename__ = "v2_accounts"

    account_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    email: Mapped[str] = mapped_column(String(160), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(80), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(256), nullable=False)
    password_salt: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False, default=utc_now_naive)
    updated_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False, default=utc_now_naive)


class V2Tenant(Base):
    __tablename__ = "v2_tenants"

    tenant_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    slug: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    plan_code: Mapped[str] = mapped_column(String(40), nullable=False, default="trial")
    owner_account_id: Mapped[str] = mapped_column(ForeignKey("v2_accounts.account_id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False, default=utc_now_naive)
    updated_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False, default=utc_now_naive)


class V2Shop(Base):
    __tablename__ = "v2_shops"
    __table_args__ = (UniqueConstraint("tenant_id", "code", name="uq_v2_shops_tenant_code"),)

    shop_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("v2_tenants.tenant_id"), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(40), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    locale: Mapped[str] = mapped_column(String(16), nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False, default=utc_now_naive)
    updated_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False, default=utc_now_naive)


class V2TenantMembership(Base):
    __tablename__ = "v2_tenant_memberships"
    __table_args__ = (
        UniqueConstraint("tenant_id", "account_id", name="uq_v2_tenant_memberships_tenant_account"),
    )

    membership_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("v2_tenants.tenant_id"), nullable=False, index=True)
    account_id: Mapped[str] = mapped_column(ForeignKey("v2_accounts.account_id"), nullable=False, index=True)
    role_key: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    joined_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False, default=utc_now_naive)
    updated_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False, default=utc_now_naive)


class V2ShopAccess(Base):
    __tablename__ = "v2_shop_accesses"
    __table_args__ = (
        UniqueConstraint("shop_id", "membership_id", name="uq_v2_shop_accesses_shop_membership"),
    )

    shop_access_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("v2_tenants.tenant_id"), nullable=False, index=True)
    shop_id: Mapped[str] = mapped_column(ForeignKey("v2_shops.shop_id"), nullable=False, index=True)
    membership_id: Mapped[str] = mapped_column(ForeignKey("v2_tenant_memberships.membership_id"), nullable=False)
    access_level: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False, default=utc_now_naive)


class V2AuthSession(Base):
    __tablename__ = "v2_auth_sessions"

    auth_session_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    account_id: Mapped[str] = mapped_column(ForeignKey("v2_accounts.account_id"), nullable=False, index=True)
    access_token_hash: Mapped[str] = mapped_column(String(256), unique=True, nullable=False)
    refresh_token_hash: Mapped[str | None] = mapped_column(String(256), unique=True, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    expires_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False, default=utc_now_naive)


class V2ContextSession(Base):
    __tablename__ = "v2_context_sessions"

    context_session_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    auth_session_id: Mapped[str] = mapped_column(ForeignKey("v2_auth_sessions.auth_session_id"), nullable=False)
    account_id: Mapped[str] = mapped_column(ForeignKey("v2_accounts.account_id"), nullable=False, index=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("v2_tenants.tenant_id"), nullable=False, index=True)
    shop_id: Mapped[str] = mapped_column(ForeignKey("v2_shops.shop_id"), nullable=False, index=True)
    membership_id: Mapped[str] = mapped_column(ForeignKey("v2_tenant_memberships.membership_id"), nullable=False)
    permission_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    expires_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False, default=utc_now_naive)
```

- [ ] **Step 5: 新增迁移，创建与 ORM 一致的 v2 表**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m alembic revision -m "create v2 identity context"
```

然后把生成文件内容整理为：

```python
from alembic import op
import sqlalchemy as sa


revision = "20260418_01"
down_revision = "20260407_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "v2_accounts",
        sa.Column("account_id", sa.String(length=40), nullable=False),
        sa.Column("email", sa.String(length=160), nullable=False),
        sa.Column("display_name", sa.String(length=80), nullable=False),
        sa.Column("password_hash", sa.String(length=256), nullable=False),
        sa.Column("password_salt", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("account_id"),
        sa.UniqueConstraint("email"),
    )
    op.create_table(
        "v2_tenants",
        sa.Column("tenant_id", sa.String(length=40), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("slug", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("plan_code", sa.String(length=40), nullable=False),
        sa.Column("owner_account_id", sa.String(length=40), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["owner_account_id"], ["v2_accounts.account_id"]),
        sa.PrimaryKeyConstraint("tenant_id"),
        sa.UniqueConstraint("slug"),
    )
    op.create_table(
        "v2_shops",
        sa.Column("shop_id", sa.String(length=40), nullable=False),
        sa.Column("tenant_id", sa.String(length=40), nullable=False),
        sa.Column("code", sa.String(length=40), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("locale", sa.String(length=16), nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["v2_tenants.tenant_id"]),
        sa.PrimaryKeyConstraint("shop_id"),
        sa.UniqueConstraint("tenant_id", "code", name="uq_v2_shops_tenant_code"),
    )
    op.create_index("ix_v2_shops_tenant_id", "v2_shops", ["tenant_id"], unique=False)
    op.create_table(
        "v2_tenant_memberships",
        sa.Column("membership_id", sa.String(length=40), nullable=False),
        sa.Column("tenant_id", sa.String(length=40), nullable=False),
        sa.Column("account_id", sa.String(length=40), nullable=False),
        sa.Column("role_key", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("joined_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["v2_accounts.account_id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["v2_tenants.tenant_id"]),
        sa.PrimaryKeyConstraint("membership_id"),
        sa.UniqueConstraint("tenant_id", "account_id", name="uq_v2_tenant_memberships_tenant_account"),
    )
    op.create_index("ix_v2_tenant_memberships_account_id", "v2_tenant_memberships", ["account_id"], unique=False)
    op.create_index("ix_v2_tenant_memberships_tenant_id", "v2_tenant_memberships", ["tenant_id"], unique=False)
    op.create_table(
        "v2_shop_accesses",
        sa.Column("shop_access_id", sa.String(length=40), nullable=False),
        sa.Column("tenant_id", sa.String(length=40), nullable=False),
        sa.Column("shop_id", sa.String(length=40), nullable=False),
        sa.Column("membership_id", sa.String(length=40), nullable=False),
        sa.Column("access_level", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["membership_id"], ["v2_tenant_memberships.membership_id"]),
        sa.ForeignKeyConstraint(["shop_id"], ["v2_shops.shop_id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["v2_tenants.tenant_id"]),
        sa.PrimaryKeyConstraint("shop_access_id"),
        sa.UniqueConstraint("shop_id", "membership_id", name="uq_v2_shop_accesses_shop_membership"),
    )
    op.create_index("ix_v2_shop_accesses_shop_id", "v2_shop_accesses", ["shop_id"], unique=False)
    op.create_index("ix_v2_shop_accesses_tenant_id", "v2_shop_accesses", ["tenant_id"], unique=False)
    op.create_table(
        "v2_auth_sessions",
        sa.Column("auth_session_id", sa.String(length=40), nullable=False),
        sa.Column("account_id", sa.String(length=40), nullable=False),
        sa.Column("access_token_hash", sa.String(length=256), nullable=False),
        sa.Column("refresh_token_hash", sa.String(length=256), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["v2_accounts.account_id"]),
        sa.PrimaryKeyConstraint("auth_session_id"),
        sa.UniqueConstraint("access_token_hash"),
        sa.UniqueConstraint("refresh_token_hash"),
    )
    op.create_index("ix_v2_auth_sessions_account_id", "v2_auth_sessions", ["account_id"], unique=False)
    op.create_table(
        "v2_context_sessions",
        sa.Column("context_session_id", sa.String(length=40), nullable=False),
        sa.Column("auth_session_id", sa.String(length=40), nullable=False),
        sa.Column("account_id", sa.String(length=40), nullable=False),
        sa.Column("tenant_id", sa.String(length=40), nullable=False),
        sa.Column("shop_id", sa.String(length=40), nullable=False),
        sa.Column("membership_id", sa.String(length=40), nullable=False),
        sa.Column("permission_snapshot", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["v2_accounts.account_id"]),
        sa.ForeignKeyConstraint(["auth_session_id"], ["v2_auth_sessions.auth_session_id"]),
        sa.ForeignKeyConstraint(["membership_id"], ["v2_tenant_memberships.membership_id"]),
        sa.ForeignKeyConstraint(["shop_id"], ["v2_shops.shop_id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["v2_tenants.tenant_id"]),
        sa.PrimaryKeyConstraint("context_session_id"),
    )
    op.create_index("ix_v2_context_sessions_account_id", "v2_context_sessions", ["account_id"], unique=False)
    op.create_index("ix_v2_context_sessions_shop_id", "v2_context_sessions", ["shop_id"], unique=False)
    op.create_index("ix_v2_context_sessions_tenant_id", "v2_context_sessions", ["tenant_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_v2_context_sessions_tenant_id", table_name="v2_context_sessions")
    op.drop_index("ix_v2_context_sessions_shop_id", table_name="v2_context_sessions")
    op.drop_index("ix_v2_context_sessions_account_id", table_name="v2_context_sessions")
    op.drop_table("v2_context_sessions")
    op.drop_index("ix_v2_auth_sessions_account_id", table_name="v2_auth_sessions")
    op.drop_table("v2_auth_sessions")
    op.drop_index("ix_v2_shop_accesses_tenant_id", table_name="v2_shop_accesses")
    op.drop_index("ix_v2_shop_accesses_shop_id", table_name="v2_shop_accesses")
    op.drop_table("v2_shop_accesses")
    op.drop_index("ix_v2_tenant_memberships_tenant_id", table_name="v2_tenant_memberships")
    op.drop_index("ix_v2_tenant_memberships_account_id", table_name="v2_tenant_memberships")
    op.drop_table("v2_tenant_memberships")
    op.drop_index("ix_v2_shops_tenant_id", table_name="v2_shops")
    op.drop_table("v2_shops")
    op.drop_table("v2_tenants")
    op.drop_table("v2_accounts")
```

- [ ] **Step 6: 导入模型并运行迁移测试**

`backend/app/models/__init__.py`

```python
from app.models.v2_identity import (
    V2Account,
    V2AuthSession,
    V2ContextSession,
    V2Shop,
    V2ShopAccess,
    V2Tenant,
    V2TenantMembership,
)
```

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_identity_context.py::test_v2_schema_supports_account_multiple_tenants_and_tenant_multiple_shops -q
```

Expected:

- `1 passed`

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/v2_time.py backend/app/models/v2_identity.py backend/app/models/__init__.py backend/alembic/versions/20260418_01_create_v2_identity_context.py backend/tests/test_v2_identity_context.py
git commit -m "feat: add v2 identity context schema"
```

### Task 3: v2 登录、租户/门店查询与上下文选择

**Files:**
- Create: `backend/app/services/v2_identity.py`
- Create: `backend/app/contracts/v2/identity.py`
- Create: `backend/app/api/deps/v2_context.py`
- Create: `backend/app/api/v2/routes/identity.py`
- Modify: `backend/app/api/v2/router.py`
- Test: `backend/tests/test_v2_identity_context.py`

- [ ] **Step 1: 在测试文件顶部补齐共享 helper，避免测试只调用未定义的种子函数**

`backend/tests/test_v2_identity_context.py`

```python
from app.models import (
    V2Account,
    V2Shop,
    V2ShopAccess,
    V2Tenant,
    V2TenantMembership,
)
from app.services.v2_identity import hash_v2_password
from app.services.v2_time import utc_now_naive


def seed_v2_identity(
    db_session,
    *,
    account_id: str,
    email: str,
    password: str,
    tenants: list[tuple[str, str]],
    shops: dict[str, list[tuple[str, str]]],
    accessible_shops: list[str] | None = None,
) -> None:
    salt_hex = "11" * 16
    account = V2Account(
        account_id=account_id,
        email=email,
        display_name="Owner",
        password_hash=hash_v2_password(password, salt_hex),
        password_salt=salt_hex,
        status="active",
        created_at=utc_now_naive(),
        updated_at=utc_now_naive(),
    )
    db_session.add(account)
    for tenant_id, tenant_name in tenants:
        db_session.add(
            V2Tenant(
                tenant_id=tenant_id,
                name=tenant_name,
                slug=tenant_id,
                status="active",
                plan_code="trial",
                owner_account_id=account_id,
                created_at=utc_now_naive(),
                updated_at=utc_now_naive(),
            )
        )
        membership_id = f"mship_{tenant_id}"
        db_session.add(
            V2TenantMembership(
                membership_id=membership_id,
                tenant_id=tenant_id,
                account_id=account_id,
                role_key="owner",
                status="active",
                joined_at=utc_now_naive(),
                updated_at=utc_now_naive(),
            )
        )
        for shop_id, shop_name in shops.get(tenant_id, []):
            db_session.add(
                V2Shop(
                    shop_id=shop_id,
                    tenant_id=tenant_id,
                    code=shop_id,
                    name=shop_name,
                    locale="zh-CN",
                    timezone="Asia/Shanghai",
                    status="active",
                    created_at=utc_now_naive(),
                    updated_at=utc_now_naive(),
                )
            )
            if accessible_shops is None or shop_id in accessible_shops:
                db_session.add(
                    V2ShopAccess(
                        shop_access_id=f"access_{shop_id}",
                        tenant_id=tenant_id,
                        shop_id=shop_id,
                        membership_id=membership_id,
                        access_level="write",
                        status="active",
                        created_at=utc_now_naive(),
                    )
                )
    db_session.commit()


def login_v2(client, email: str, password: str) -> str:
    response = client.post("/api/v2/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return response.json()["data"]["access_token"]
```

- [ ] **Step 2: 写失败测试，确认登录只返回账号登录态，不绑定 tenant 或 shop**

```python
def test_v2_login_returns_account_session_without_shop_binding(client, db_session) -> None:
    seed_v2_identity(
        db_session,
        account_id="acct_001",
        email="owner@example.com",
        password="dev-password",
        tenants=[("tenant_a", "A 商家"), ("tenant_b", "B 商家")],
        shops={"tenant_a": [("shop_a1", "A 一号店")]},
    )

    response = client.post(
        "/api/v2/auth/login",
        json={"email": "owner@example.com", "password": "dev-password"},
    )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["token_type"] == "Bearer"
    assert payload["account_id"] == "acct_001"
    assert "tenant_id" not in payload
    assert "shop_id" not in payload
```

- [ ] **Step 3: 写失败测试，确认账号可列出多个 tenant，并只看到有权限的 shop**

```python
def test_v2_me_tenants_and_tenant_shops_use_membership_boundaries(client, db_session) -> None:
    seed_v2_identity(
        db_session,
        account_id="acct_001",
        email="owner@example.com",
        password="dev-password",
        tenants=[("tenant_a", "A 商家"), ("tenant_b", "B 商家")],
        shops={
            "tenant_a": [("shop_a1", "A 一号店"), ("shop_a2", "A 二号店")],
            "tenant_b": [("shop_b1", "B 一号店")],
        },
        accessible_shops=["shop_a1", "shop_b1"],
    )
    token = login_v2(client, "owner@example.com", "dev-password")

    tenants_response = client.get("/api/v2/me/tenants", headers={"Authorization": f"Bearer {token}"})
    shops_response = client.get(
        "/api/v2/tenants/tenant_a/shops",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert tenants_response.status_code == 200
    assert {tenant["tenant_id"] for tenant in tenants_response.json()["data"]["tenants"]} == {
        "tenant_a",
        "tenant_b",
    }
    assert shops_response.status_code == 200
    assert [shop["shop_id"] for shop in shops_response.json()["data"]["shops"]] == ["shop_a1"]
```

- [ ] **Step 4: 写失败测试，确认 context selection 拒绝无权访问的 shop**

```python
def test_v2_context_select_rejects_shop_without_access(client, db_session) -> None:
    seed_v2_identity(
        db_session,
        account_id="acct_001",
        email="owner@example.com",
        password="dev-password",
        tenants=[("tenant_a", "A 商家")],
        shops={"tenant_a": [("shop_a1", "A 一号店"), ("shop_a2", "A 二号店")]},
        accessible_shops=["shop_a1"],
    )
    token = login_v2(client, "owner@example.com", "dev-password")

    response = client.post(
        "/api/v2/context/select",
        headers={"Authorization": f"Bearer {token}"},
        json={"tenant_id": "tenant_a", "shop_id": "shop_a2"},
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "shop_access_denied"
```

- [ ] **Step 5: 写失败测试，确认有权访问的 shop 会创建 context session**

```python
def test_v2_context_select_creates_explicit_context_session(client, db_session) -> None:
    seed_v2_identity(
        db_session,
        account_id="acct_001",
        email="owner@example.com",
        password="dev-password",
        tenants=[("tenant_a", "A 商家")],
        shops={"tenant_a": [("shop_a1", "A 一号店")]},
        accessible_shops=["shop_a1"],
    )
    token = login_v2(client, "owner@example.com", "dev-password")

    response = client.post(
        "/api/v2/context/select",
        headers={"Authorization": f"Bearer {token}"},
        json={"tenant_id": "tenant_a", "shop_id": "shop_a1"},
    )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["tenant_id"] == "tenant_a"
    assert payload["shop_id"] == "shop_a1"
    assert payload["membership_id"].startswith("mship_")
    assert payload["context_token"]
    assert "inventory:read" in payload["permissions"]
```

- [ ] **Step 6: 运行任务测试，确认红灯**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_identity_context.py -q
```

Expected:

- v2 health 与 schema 测试通过。
- 登录、租户列表、门店列表、context selection 测试因 `404` 或缺失服务而失败。

- [ ] **Step 7: 新增 v2 identity 合同**

`backend/app/contracts/v2/identity.py`

```python
from pydantic import BaseModel


class V2LoginRequest(BaseModel):
    email: str
    password: str


class V2LoginData(BaseModel):
    access_token: str
    token_type: str
    account_id: str


class V2TenantData(BaseModel):
    tenant_id: str
    name: str
    role_key: str


class V2TenantListData(BaseModel):
    tenants: list[V2TenantData]


class V2ShopData(BaseModel):
    shop_id: str
    tenant_id: str
    code: str
    name: str
    access_level: str


class V2ShopListData(BaseModel):
    shops: list[V2ShopData]


class V2ContextSelectRequest(BaseModel):
    tenant_id: str
    shop_id: str


class V2ContextData(BaseModel):
    context_token: str
    context_session_id: str
    account_id: str
    tenant_id: str
    shop_id: str
    membership_id: str
    role_key: str
    permissions: list[str]
```

- [ ] **Step 8: 新增 v2 identity 服务**

`backend/app/services/v2_identity.py`

```python
from dataclasses import dataclass
from datetime import timedelta
import hashlib
import hmac
import secrets
import uuid

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.models import (
    V2Account,
    V2AuthSession,
    V2ContextSession,
    V2Shop,
    V2ShopAccess,
    V2Tenant,
    V2TenantMembership,
)
from app.services.v2_time import utc_now_naive

_PASSWORD_HASH_ITERATIONS = 310_000


@dataclass(frozen=True)
class IssuedV2AuthSession:
    access_token: str
    account_id: str


@dataclass(frozen=True)
class ResolvedV2AuthSession:
    auth_session_id: str
    account_id: str


def hash_v2_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def hash_v2_password(password: str, salt_hex: str) -> str:
    return hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        bytes.fromhex(salt_hex),
        _PASSWORD_HASH_ITERATIONS,
    ).hex()


def verify_v2_password(password: str, password_hash: str, password_salt: str) -> bool:
    candidate_hash = hash_v2_password(password, password_salt)
    return hmac.compare_digest(candidate_hash, password_hash)


def authenticate_v2_account(db_session: Session, email: str, password: str) -> V2Account | None:
    account = db_session.scalar(
        select(V2Account).where(V2Account.email == email, V2Account.status == "active")
    )
    if account is None:
        return None
    if not verify_v2_password(password, account.password_hash, account.password_salt):
        return None
    return account


def issue_v2_auth_session(db_session: Session, account_id: str, ttl_minutes: int) -> IssuedV2AuthSession:
    now = utc_now_naive()
    access_token = secrets.token_urlsafe(32)
    auth_session = V2AuthSession(
        auth_session_id=f"v2auth_{uuid.uuid4().hex}"[:40],
        account_id=account_id,
        access_token_hash=hash_v2_token(access_token),
        refresh_token_hash=None,
        status="active",
        expires_at=now + timedelta(minutes=ttl_minutes),
        revoked_at=None,
        last_seen_at=now,
        created_at=now,
    )
    db_session.add(auth_session)
    db_session.commit()
    return IssuedV2AuthSession(access_token=access_token, account_id=account_id)


def resolve_v2_auth_session(db_session: Session, bearer_token: str) -> ResolvedV2AuthSession | None:
    auth_session = db_session.scalar(
        select(V2AuthSession).where(
            V2AuthSession.access_token_hash == hash_v2_token(bearer_token),
            V2AuthSession.status == "active",
            V2AuthSession.revoked_at.is_(None),
            V2AuthSession.expires_at > utc_now_naive(),
        )
    )
    if auth_session is None:
        return None
    return ResolvedV2AuthSession(
        auth_session_id=auth_session.auth_session_id,
        account_id=auth_session.account_id,
    )


def list_v2_tenants_for_account(db_session: Session, account_id: str) -> list[tuple[V2Tenant, V2TenantMembership]]:
    return list(
        db_session.execute(
            select(V2Tenant, V2TenantMembership)
            .join(V2TenantMembership, V2TenantMembership.tenant_id == V2Tenant.tenant_id)
            .where(
                V2TenantMembership.account_id == account_id,
                V2TenantMembership.status == "active",
                V2Tenant.status == "active",
            )
            .order_by(V2Tenant.created_at.asc(), V2Tenant.tenant_id.asc())
        ).all()
    )


def list_v2_accessible_shops(
    db_session: Session,
    *,
    account_id: str,
    tenant_id: str,
) -> list[tuple[V2Shop, V2ShopAccess, V2TenantMembership]]:
    return list(
        db_session.execute(
            select(V2Shop, V2ShopAccess, V2TenantMembership)
            .join(V2ShopAccess, V2ShopAccess.shop_id == V2Shop.shop_id)
            .join(V2TenantMembership, V2TenantMembership.membership_id == V2ShopAccess.membership_id)
            .where(
                V2Shop.tenant_id == tenant_id,
                V2ShopAccess.tenant_id == tenant_id,
                V2TenantMembership.tenant_id == tenant_id,
                V2TenantMembership.account_id == account_id,
                V2Shop.status == "active",
                V2ShopAccess.status == "active",
                V2TenantMembership.status == "active",
            )
            .order_by(V2Shop.code.asc(), V2Shop.shop_id.asc())
        ).all()
    )


def select_v2_context(
    db_session: Session,
    *,
    auth_session_id: str,
    account_id: str,
    tenant_id: str,
    shop_id: str,
    ttl_minutes: int,
) -> V2ContextSession | None:
    row = db_session.execute(
        select(V2TenantMembership, V2ShopAccess)
        .join(V2ShopAccess, V2ShopAccess.membership_id == V2TenantMembership.membership_id)
        .join(
            V2Shop,
            and_(V2Shop.shop_id == V2ShopAccess.shop_id, V2Shop.tenant_id == V2ShopAccess.tenant_id),
        )
        .where(
            V2TenantMembership.account_id == account_id,
            V2TenantMembership.tenant_id == tenant_id,
            V2TenantMembership.status == "active",
            V2ShopAccess.tenant_id == tenant_id,
            V2ShopAccess.shop_id == shop_id,
            V2ShopAccess.status == "active",
            V2Shop.status == "active",
        )
    ).first()
    if row is None:
        return None
    membership, _ = row
    now = utc_now_naive()
    permission_snapshot = {
        "role_key": membership.role_key,
        "permissions": ["inventory:read", "conversation:write"],
    }
    context_session = V2ContextSession(
        context_session_id=f"ctx_{uuid.uuid4().hex}"[:40],
        auth_session_id=auth_session_id,
        account_id=account_id,
        tenant_id=tenant_id,
        shop_id=shop_id,
        membership_id=membership.membership_id,
        permission_snapshot=permission_snapshot,
        status="active",
        expires_at=now + timedelta(minutes=ttl_minutes),
        created_at=now,
    )
    db_session.add(context_session)
    db_session.commit()
    return context_session
```

- [ ] **Step 9: 新增 v2 auth/context 依赖**

`backend/app/api/deps/v2_context.py`

```python
from dataclasses import dataclass

from fastapi import Depends, Header
from sqlalchemy.orm import Session

from app.db.session import get_db_session
from app.services.v2_identity import resolve_v2_auth_session


class V2UnauthorizedError(Exception):
    pass


@dataclass(frozen=True)
class V2AuthenticatedAccount:
    auth_session_id: str
    account_id: str


def require_v2_authenticated_account(
    authorization: str | None = Header(default=None),
    db_session: Session = Depends(get_db_session),
) -> V2AuthenticatedAccount:
    if authorization is None:
        raise V2UnauthorizedError
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise V2UnauthorizedError
    resolved = resolve_v2_auth_session(db_session, token)
    if resolved is None:
        raise V2UnauthorizedError
    return V2AuthenticatedAccount(
        auth_session_id=resolved.auth_session_id,
        account_id=resolved.account_id,
    )
```

- [ ] **Step 10: 新增 v2 identity 路由**

`backend/app/api/v2/routes/identity.py`

```python
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api.deps.v2_context import V2AuthenticatedAccount, require_v2_authenticated_account
from app.contracts.v2.common import V2DataEnvelope, V2ErrorBody, V2ErrorEnvelope
from app.contracts.v2.identity import (
    V2ContextData,
    V2ContextSelectRequest,
    V2LoginData,
    V2LoginRequest,
    V2ShopData,
    V2ShopListData,
    V2TenantData,
    V2TenantListData,
)
from app.core.config import Settings, get_settings
from app.db.session import get_db_session
from app.services.v2_identity import (
    authenticate_v2_account,
    issue_v2_auth_session,
    list_v2_accessible_shops,
    list_v2_tenants_for_account,
    select_v2_context,
)

router = APIRouter(prefix="/api/v2", tags=["v2-identity"])


def _v2_error(status_code: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=V2ErrorEnvelope(error=V2ErrorBody(code=code, message=message)).model_dump(),
    )


@router.post("/auth/login", response_model=V2DataEnvelope[V2LoginData], responses={401: {"model": V2ErrorEnvelope}})
def login_v2(
    payload: V2LoginRequest,
    settings: Settings = Depends(get_settings),
    db_session: Session = Depends(get_db_session),
) -> V2DataEnvelope[V2LoginData] | JSONResponse:
    account = authenticate_v2_account(db_session, payload.email, payload.password)
    if account is None:
        return _v2_error(401, "unauthorized", "Unauthorized")
    issued = issue_v2_auth_session(
        db_session,
        account.account_id,
        ttl_minutes=settings.auth_session_ttl_minutes,
    )
    return V2DataEnvelope(
        data=V2LoginData(
            access_token=issued.access_token,
            token_type="Bearer",
            account_id=issued.account_id,
        )
    )


@router.get("/me/tenants", response_model=V2DataEnvelope[V2TenantListData])
def me_tenants_v2(
    account: V2AuthenticatedAccount = Depends(require_v2_authenticated_account),
    db_session: Session = Depends(get_db_session),
) -> V2DataEnvelope[V2TenantListData]:
    tenants = [
        V2TenantData(tenant_id=tenant.tenant_id, name=tenant.name, role_key=membership.role_key)
        for tenant, membership in list_v2_tenants_for_account(db_session, account.account_id)
    ]
    return V2DataEnvelope(data=V2TenantListData(tenants=tenants))


@router.get("/tenants/{tenant_id}/shops", response_model=V2DataEnvelope[V2ShopListData])
def tenant_shops_v2(
    tenant_id: str,
    account: V2AuthenticatedAccount = Depends(require_v2_authenticated_account),
    db_session: Session = Depends(get_db_session),
) -> V2DataEnvelope[V2ShopListData]:
    shops = [
        V2ShopData(
            shop_id=shop.shop_id,
            tenant_id=shop.tenant_id,
            code=shop.code,
            name=shop.name,
            access_level=access.access_level,
        )
        for shop, access, _ in list_v2_accessible_shops(
            db_session,
            account_id=account.account_id,
            tenant_id=tenant_id,
        )
    ]
    return V2DataEnvelope(data=V2ShopListData(shops=shops))


@router.post("/context/select", response_model=V2DataEnvelope[V2ContextData], responses={403: {"model": V2ErrorEnvelope}})
def select_context_v2(
    payload: V2ContextSelectRequest,
    account: V2AuthenticatedAccount = Depends(require_v2_authenticated_account),
    settings: Settings = Depends(get_settings),
    db_session: Session = Depends(get_db_session),
) -> V2DataEnvelope[V2ContextData] | JSONResponse:
    context_session = select_v2_context(
        db_session,
        auth_session_id=account.auth_session_id,
        account_id=account.account_id,
        tenant_id=payload.tenant_id,
        shop_id=payload.shop_id,
        ttl_minutes=settings.auth_session_ttl_minutes,
    )
    if context_session is None:
        return _v2_error(403, "shop_access_denied", "Shop access denied")
    permissions = context_session.permission_snapshot["permissions"]
    role_key = context_session.permission_snapshot["role_key"]
    return V2DataEnvelope(
        data=V2ContextData(
            context_token=context_session.context_session_id,
            context_session_id=context_session.context_session_id,
            account_id=context_session.account_id,
            tenant_id=context_session.tenant_id,
            shop_id=context_session.shop_id,
            membership_id=context_session.membership_id,
            role_key=role_key,
            permissions=permissions,
        )
    )
```

`backend/app/api/v2/router.py`

```python
from app.api.v2.routes.identity import router as identity_router

v2_router.include_router(identity_router)
```

- [ ] **Step 11: 注册 v2 未授权异常处理**

`backend/app/main.py`

```python
from app.api.deps.v2_context import V2UnauthorizedError


@app.exception_handler(V2UnauthorizedError)
async def _handle_v2_unauthorized(_, __) -> JSONResponse:
    return JSONResponse(
        status_code=401,
        content=V2ErrorEnvelope(
            error=V2ErrorBody(code="unauthorized", message="Unauthorized", details=[])
        ).model_dump(),
    )
```

- [ ] **Step 12: 重新运行 v2 identity/context 测试**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_identity_context.py -q
```

Expected:

- 本文件所有测试通过。

- [ ] **Step 13: Commit**

```bash
git add backend/app/services/v2_time.py backend/app/services/v2_identity.py backend/app/contracts/v2/identity.py backend/app/api/deps/v2_context.py backend/app/api/v2/routes/identity.py backend/app/api/v2/router.py backend/app/main.py backend/tests/test_v2_identity_context.py
git commit -m "feat: add v2 identity context flow"
```

### Task 4: 阻断无显式上下文的 v2 业务动作入口

**Files:**
- Modify: `backend/app/api/deps/v2_context.py`
- Test: `backend/tests/test_v2_identity_context.py`

- [ ] **Step 1: 写失败测试，固定没有 context token 时 v2 业务依赖拒绝执行**

```python
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.api.deps.v2_context import V2ExecutionContext, require_v2_execution_context
from app.main import register_exception_handlers


def test_v2_business_dependency_rejects_missing_context_token(db_session) -> None:
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/protected-business")
    def protected_business(
        context: V2ExecutionContext = Depends(require_v2_execution_context),
    ) -> dict[str, str]:
        return {"tenant_id": context.tenant_id}

    response = TestClient(app).get("/protected-business")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "context_required"
```

- [ ] **Step 2: 运行测试，确认依赖不存在而失败**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_identity_context.py::test_v2_business_dependency_rejects_missing_context_token -q
```

Expected:

- `ImportError` 或 `AttributeError`。

- [ ] **Step 3: 新增 v2 执行上下文依赖**

`backend/app/api/deps/v2_context.py`

```python
from dataclasses import dataclass

from sqlalchemy import select

from app.models import V2ContextSession
from app.services.v2_time import utc_now_naive


class V2ContextRequiredError(Exception):
    pass


@dataclass(frozen=True)
class V2ExecutionContext:
    account_id: str
    tenant_id: str
    shop_id: str
    membership_id: str
    role_key: str
    permissions: tuple[str, ...]
    context_session_id: str


def require_v2_execution_context(
    x_context_token: str | None = Header(default=None, alias="X-Context-Token"),
    db_session: Session = Depends(get_db_session),
) -> V2ExecutionContext:
    if not x_context_token:
        raise V2ContextRequiredError
    context_session = db_session.scalar(
        select(V2ContextSession).where(
            V2ContextSession.context_session_id == x_context_token,
            V2ContextSession.status == "active",
            V2ContextSession.expires_at > utc_now_naive(),
        )
    )
    if context_session is None:
        raise V2ContextRequiredError
    return V2ExecutionContext(
        account_id=context_session.account_id,
        tenant_id=context_session.tenant_id,
        shop_id=context_session.shop_id,
        membership_id=context_session.membership_id,
        role_key=context_session.permission_snapshot["role_key"],
        permissions=tuple(context_session.permission_snapshot["permissions"]),
        context_session_id=context_session.context_session_id,
    )
```

- [ ] **Step 4: 注册 context required 异常处理**

`backend/app/main.py`

```python
from app.api.deps.v2_context import V2ContextRequiredError


@app.exception_handler(V2ContextRequiredError)
async def _handle_v2_context_required(_, __) -> JSONResponse:
    return JSONResponse(
        status_code=401,
        content=V2ErrorEnvelope(
            error=V2ErrorBody(code="context_required", message="Context required", details=[])
        ).model_dump(),
    )
```

- [ ] **Step 5: 运行缺失上下文测试**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_identity_context.py::test_v2_business_dependency_rejects_missing_context_token -q
```

Expected:

- `1 passed`

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/deps/v2_context.py backend/app/main.py backend/tests/test_v2_identity_context.py
git commit -m "feat: require explicit v2 execution context"
```

### Task 5: 阶段验收

**Files:**
- Verify: `backend/tests/test_v2_identity_context.py`
- Verify: existing backend tests that may be impacted by app wiring and migrations

- [ ] **Step 1: 运行 v2 新测试**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_identity_context.py -q
```

Expected:

- 所有 v2 identity/context 测试通过。

- [ ] **Step 2: 运行认证、迁移与健康检查相关回归测试**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_health.py backend/tests/test_auth.py backend/tests/test_auth_context.py backend/tests/test_alembic_bootstrap.py -q
```

Expected:

- 现有 v1 行为未被破坏。
- Alembic 能从空库升级到最新 head。

- [ ] **Step 3: 检查 OpenAPI 中同时存在 v1 与 v2 路由**

Run:

```powershell
$env:PYTHONPATH="backend"; python - <<'PY'
from app.main import create_app

paths = sorted(create_app().openapi()["paths"])
assert "/api/v1/auth/login" in paths
assert "/api/v2/auth/login" in paths
assert "/api/v2/context/select" in paths
print("v1/v2 routes coexist")
PY
```

Expected:

- 输出 `v1/v2 routes coexist`。

- [ ] **Step 4: 检查 git 状态**

Run:

```powershell
git status --short
```

Expected:

- 只出现本计划相关文件。
- 不出现 `.worktrees/`、pytest cache、临时数据库或依赖目录。

## 自检

- Spec coverage：本计划覆盖最新 spec 的阶段 1 与阶段 2，并为阶段 3 之后提供显式后续拆分。
- Placeholder scan：本计划不包含 `TBD`、`TODO`、`implement later` 或无内容的“补充测试”步骤。
- Type consistency：计划中的 v2 模型、合同、服务和路由均使用 `V2*` 前缀，避免与旧 v1 模型混淆。
- 架构约束：v2 登录只绑定账号，不返回 `tenant_id` 或 `shop_id`；业务上下文必须通过 `context_session` 显式选择。
