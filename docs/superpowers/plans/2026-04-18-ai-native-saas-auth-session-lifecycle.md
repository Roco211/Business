# AI 原生 SaaS V2 认证会话生命周期实施计划

> **给智能执行代理（agentic workers）：** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 按任务逐项实现本计划。步骤使用 checkbox（`- [ ]`）语法跟踪。

**Goal:** 补齐 spec 中缺失的 `/api/v2/me`、`/api/v2/auth/logout`、`/api/v2/auth/refresh`，让 v2 账号级认证具备可查询、可刷新、可撤销的基础会话生命周期。

**Architecture:** 本阶段仍保持“账号登录态与业务上下文分离”的原则。`auth_session` 负责 access / refresh token 生命周期，`context_session` 继续承载当前租户与门店上下文；logout 会撤销当前 auth session 并同步失效其 active context session，refresh 会轮换 auth session 而不是原地覆盖，避免旧 access token 继续可用。

**Tech Stack:** Python, FastAPI, Pydantic, SQLAlchemy, Alembic, pytest, SQLite 测试库, MySQL 生产目标

---

## 范围拆分

本计划覆盖 identity_access 与 workspace_context 之间的最小会话闭环：

- 登录返回 `refresh_token`
- `GET /api/v2/me`
- `POST /api/v2/auth/logout`
- `POST /api/v2/auth/refresh`
- logout 撤销当前 `auth_session` 与其关联 `context_session`
- refresh 轮换 `auth_session`

本计划暂不覆盖：

- 多设备 session 管理
- refresh token 版本治理与设备指纹
- `/api/v2/auth/logout-all`
- `/api/v2/me` 下更多组织统计信息

## 文件结构

- 修改 `backend/app/contracts/v2/identity.py`：新增 `me / refresh / logout` 合同并扩展 login 返回。
- 修改 `backend/app/services/v2_identity.py`：新增 refresh token 签发、resolve、revoke、轮换与 account 查询服务。
- 修改 `backend/app/api/v2/routes/identity.py`：新增 `me / logout / refresh` 路由。
- 修改 `backend/tests/test_v2_identity_context.py`：新增 auth lifecycle 验收测试。
- 修改 `project_docs/generated/openapi-v1.json`：刷新 OpenAPI 快照。

### Task 1: 写失败测试固定 auth lifecycle 行为

**Files:**
- Modify: `backend/tests/test_v2_identity_context.py`

- [x] **Step 1: 写失败测试，固定 login 返回 refresh token**

```python
def test_v2_login_returns_refresh_token(client, db_session) -> None:
    seed_v2_identity(
        db_session,
        account_id="acct_001",
        email="owner@example.com",
        password="dev-password",
        tenants=[("tenant_a", "Tenant A")],
        shops={"tenant_a": [("shop_a1", "Shop A1")]},
    )

    response = client.post(
        "/api/v2/auth/login",
        json={"email": "owner@example.com", "password": "dev-password"},
    )

    assert response.status_code == 200
    assert response.json()["data"]["refresh_token"]
```

- [x] **Step 2: 写失败测试，固定 `GET /api/v2/me` 只返回账号信息**

```python
def test_v2_me_returns_authenticated_account_profile(client, db_session) -> None:
    seed_v2_identity(
        db_session,
        account_id="acct_001",
        email="owner@example.com",
        password="dev-password",
        tenants=[("tenant_a", "Tenant A")],
        shops={"tenant_a": [("shop_a1", "Shop A1")]},
    )
    token = login_v2(client)

    response = client.get(
        "/api/v2/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["account_id"] == "acct_001"
    assert payload["email"] == "owner@example.com"
    assert "tenant_id" not in payload
    assert "shop_id" not in payload
```

- [x] **Step 3: 写失败测试，固定 logout 会撤销 access token 与 context token**

```python
def test_v2_logout_revokes_auth_and_context_sessions(client, db_session) -> None:
    seed_v2_identity(
        db_session,
        account_id="acct_001",
        email="owner@example.com",
        password="dev-password",
        tenants=[("tenant_a", "Tenant A")],
        shops={"tenant_a": [("shop_a1", "Shop A1")]},
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
    context_token = select_response.json()["data"]["context_token"]

    logout_response = client.post(
        "/api/v2/auth/logout",
        headers={"Authorization": f"Bearer {token}"},
    )
    me_response = client.get("/api/v2/me", headers={"Authorization": f"Bearer {token}"})
    context_response = client.get(
        "/api/v2/context/current",
        headers={"Authorization": f"Bearer {token}", "X-Context-Token": context_token},
    )

    assert logout_response.status_code == 200
    assert me_response.status_code == 401
    assert context_response.status_code == 401
```

- [x] **Step 4: 写失败测试，固定 refresh 会轮换 auth session 并使旧 access token 失效**

```python
def test_v2_refresh_rotates_auth_session(client, db_session) -> None:
    seed_v2_identity(
        db_session,
        account_id="acct_001",
        email="owner@example.com",
        password="dev-password",
        tenants=[("tenant_a", "Tenant A")],
        shops={"tenant_a": [("shop_a1", "Shop A1")]},
    )
    login_response = client.post(
        "/api/v2/auth/login",
        json={"email": "owner@example.com", "password": "dev-password"},
    )
    old_access_token = login_response.json()["data"]["access_token"]
    old_refresh_token = login_response.json()["data"]["refresh_token"]

    refresh_response = client.post(
        "/api/v2/auth/refresh",
        json={"refresh_token": old_refresh_token},
    )
    new_access_token = refresh_response.json()["data"]["access_token"]

    old_me_response = client.get("/api/v2/me", headers={"Authorization": f"Bearer {old_access_token}"})
    new_me_response = client.get("/api/v2/me", headers={"Authorization": f"Bearer {new_access_token}"})

    assert refresh_response.status_code == 200
    assert refresh_response.json()["data"]["refresh_token"] != old_refresh_token
    assert old_me_response.status_code == 401
    assert new_me_response.status_code == 200
```

- [x] **Step 5: 运行测试，确认因为合同或路由不存在而失败**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_identity_context.py::test_v2_login_returns_refresh_token backend/tests/test_v2_identity_context.py::test_v2_me_returns_authenticated_account_profile backend/tests/test_v2_identity_context.py::test_v2_logout_revokes_auth_and_context_sessions backend/tests/test_v2_identity_context.py::test_v2_refresh_rotates_auth_session -q
```

Expected:

- `404`、缺字段或 `KeyError`。

### Task 2: identity 合同与服务

**Files:**
- Modify: `backend/app/contracts/v2/identity.py`
- Modify: `backend/app/services/v2_identity.py`

- [x] **Step 1: 新增 identity 合同**

`backend/app/contracts/v2/identity.py`

```python
class V2LoginData(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str
    account_id: str


class V2RefreshRequest(BaseModel):
    refresh_token: str


class V2MeData(BaseModel):
    account_id: str
    email: str
    display_name: str
    status: str
```

- [x] **Step 2: 新增 auth session lifecycle 服务**

`backend/app/services/v2_identity.py`

```python
@dataclass(frozen=True)
class IssuedV2AuthSession:
    access_token: str
    refresh_token: str
    account_id: str


def issue_v2_auth_session(...):
    # 同时签发 access_token 与 refresh_token，并落 refresh_token_hash。


def get_v2_account(...):
    # 读取 active account。


def revoke_v2_auth_session(...):
    # auth_session.status -> revoked, revoked_at -> now，并把关联 context_session.status -> revoked。


def rotate_v2_auth_session(...):
    # 使用 refresh_token 定位当前 active auth_session，先 revoke，再签发新的 auth_session。
```

- [x] **Step 3: 重新运行失败测试，确认红灯收敛到路由缺失**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_identity_context.py::test_v2_login_returns_refresh_token backend/tests/test_v2_identity_context.py::test_v2_me_returns_authenticated_account_profile backend/tests/test_v2_identity_context.py::test_v2_logout_revokes_auth_and_context_sessions backend/tests/test_v2_identity_context.py::test_v2_refresh_rotates_auth_session -q
```

Expected:

- login 字段已齐，但 `/api/v2/me`、`/api/v2/auth/logout`、`/api/v2/auth/refresh` 仍红灯。

### Task 3: identity 路由

**Files:**
- Modify: `backend/app/api/v2/routes/identity.py`

- [x] **Step 1: 新增 `GET /api/v2/me`**

```python
@router.get("/me", response_model=V2DataEnvelope[V2MeData])
def me_v2(...):
    ...
```

- [x] **Step 2: 新增 `POST /api/v2/auth/logout`**

```python
@router.post("/auth/logout", response_model=V2DataEnvelope[dict[str, str]])
def logout_v2(...):
    ...
```

- [x] **Step 3: 新增 `POST /api/v2/auth/refresh`**

```python
@router.post("/auth/refresh", response_model=V2DataEnvelope[V2LoginData], responses={401: {"model": V2ErrorEnvelope}})
def refresh_v2(...):
    ...
```

- [x] **Step 4: 重新运行 auth lifecycle 测试**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_identity_context.py::test_v2_login_returns_refresh_token backend/tests/test_v2_identity_context.py::test_v2_me_returns_authenticated_account_profile backend/tests/test_v2_identity_context.py::test_v2_logout_revokes_auth_and_context_sessions backend/tests/test_v2_identity_context.py::test_v2_refresh_rotates_auth_session -q
```

Expected:

- `4 passed`

### Task 4: 阶段验收

**Files:**
- Verify: `backend/tests/test_v2_identity_context.py`
- Modify: `project_docs/generated/openapi-v1.json`

- [x] **Step 1: 运行 v2 identity/context 测试**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_identity_context.py -q
```

- [x] **Step 2: 运行 v2 关键回归**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_identity_context.py backend/tests/test_v2_conversation_runtime.py backend/tests/test_v2_clarification_confirmation.py -q
```

- [x] **Step 3: 刷新 OpenAPI 快照并校验**

Run:

```powershell
$env:PYTHONPATH="backend"; python backend/scripts/generate_openapi_snapshot.py
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_openapi_contract_snapshot.py -q
```

- [x] **Step 4: 运行全量后端测试**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests -q
```

- [x] **Step 5: 检查 git 状态并提交**

Run:

```powershell
git status --short
git add backend/app/contracts/v2/identity.py backend/app/services/v2_identity.py backend/app/api/v2/routes/identity.py backend/tests/test_v2_identity_context.py docs/superpowers/plans/2026-04-18-ai-native-saas-auth-session-lifecycle.md project_docs/generated/openapi-v1.json
git commit -m "feat: add v2 auth session lifecycle"
```

## 自检

- Spec coverage：补齐了 spec 中明确列出的 `/api/v2/me`、`/api/v2/auth/logout`、`/api/v2/auth/refresh`。
- Placeholder scan：没有使用 `TODO`、`TBD` 或未定义步骤。
- Type consistency：统一使用 `refresh_token`、`V2MeData`、`IssuedV2AuthSession`。
- 架构约束：auth session 只绑定 account，不回退到 tenant/shop；context session 继续显式建模并在 logout 时协同失效。
