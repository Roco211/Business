# AI 原生 SaaS V2 Session Stream WebSocket Implementation Plan

> **给智能执行代理（agentic workers）：** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 按任务逐项实现本计划。步骤使用 checkbox（`- [ ]`）语法跟踪。

**Goal:** 为 V2 conversation/runtime 增加 websocket replay 入口，让客户端可以在显式租户（tenant）/门店（shop）上下文内接收 durable session stream 事件。

**Architecture:** 数据库中的 `v2_session_stream_events` 继续是真相来源，websocket 只负责连接握手、ready 通知、durable replay 和 keepalive。复用现有 `SessionStreamConnectionManager`，通过可注入 pending event loader 兼容 v1 与 v2，避免复制一套连接管理器；V2 路由使用 `token` 和 `context_token` 查询参数完成与 HTTP `Authorization` + `X-Context-Token` 等价的鉴权。

**Tech Stack:** Python、FastAPI、Starlette WebSocket、SQLAlchemy、pytest

---

## 文件结构

- Modify: `backend/app/realtime/connection_manager.py`：把 pending event 读取逻辑改为可注入 loader，默认仍使用 v1 `list_session_events_after`。
- Modify: `backend/app/api/v2/routes/conversation.py`：新增 `/api/v2/ws/sessions/{session_id}` websocket 路由，执行 V2 token、context token 和 session scope 校验。
- Create: `backend/tests/test_v2_session_stream_ws.py`：覆盖 V2 websocket 鉴权、scope、ready、replay 与 keepalive 行为。
- Modify: `project_docs/generated/openapi-v1.json`：如 FastAPI snapshot 生成内容变化则同步；websocket 通常不进入 OpenAPI，但仍通过 snapshot 测试确认无意外合约漂移。

## 设计约束

- V2 websocket 必须同时提供 `token` 与 `context_token` 查询参数。
- `token` 必须解析为 active 且未过期的 V2 auth session。
- `context_token` 必须解析为 active 且未过期的 V2 context session。
- auth session 的 `account_id` 必须与 context session 的 `account_id` 一致。
- session 必须属于当前 context 的 `tenant_id` 与 `shop_id`，否则关闭 `4404`。
- 鉴权失败或 context 失效统一关闭 `4401`。
- 连接成功先发送 ephemeral `session.ready`，其 `seq` 等于当前 `last_event_seq`。
- 连接成功后按 `after_seq` 回放 durable event；未传 `after_seq` 时从当前 `last_event_seq` 开始，只接收后续事件。
- keepalive 继续使用 `stream.keepalive`，其 `seq` 等于该连接已发送的最后 durable seq。

### Task 1: 固定 V2 websocket handshake 与 replay 行为

**Files:**
- Create: `backend/tests/test_v2_session_stream_ws.py`
- Modify: `backend/app/api/v2/routes/conversation.py`

- [x] **Step 1: 写失败测试，确认非法 token 会被关闭为 `4401`**

```python
def test_v2_session_stream_ws_rejects_invalid_token(monkeypatch, tmp_path) -> None:
    with _create_v2_websocket_client(monkeypatch, tmp_path) as client:
        with client.websocket_connect(
            "/api/v2/ws/sessions/vsess_missing?token=bad_token&context_token=bad_context"
        ) as websocket:
            with pytest.raises(WebSocketDisconnect) as disconnect:
                websocket.receive_json()

    assert disconnect.value.code == 4401
```

- [x] **Step 2: 写失败测试，确认缺失或无效 context token 会被关闭为 `4401`**

```python
def test_v2_session_stream_ws_rejects_missing_context_token(monkeypatch, tmp_path) -> None:
    with _create_v2_websocket_client(monkeypatch, tmp_path) as client:
        token, context_token = _seed_v2_login_and_context_for_ws(client)
        session_id = _create_v2_ws_session(client, token=token, context_token=context_token)

        with client.websocket_connect(f"/api/v2/ws/sessions/{session_id}?token={token}") as websocket:
            with pytest.raises(WebSocketDisconnect) as disconnect:
                websocket.receive_json()

    assert disconnect.value.code == 4401
```

- [x] **Step 3: 写失败测试，确认 session 不属于当前 context 时关闭 `4404`**

```python
def test_v2_session_stream_ws_rejects_session_outside_context(monkeypatch, tmp_path) -> None:
    with _create_v2_websocket_client(monkeypatch, tmp_path) as client:
        token, context_token = _seed_v2_login_and_context_for_ws(client)

        with client.websocket_connect(
            f"/api/v2/ws/sessions/vsess_missing?token={token}&context_token={context_token}"
        ) as websocket:
            with pytest.raises(WebSocketDisconnect) as disconnect:
                websocket.receive_json()

    assert disconnect.value.code == 4404
```

- [x] **Step 4: 写失败测试，确认成功连接先发送 `session.ready` 再发送 keepalive**

```python
def test_v2_session_stream_ws_sends_ready_and_keepalive(monkeypatch, tmp_path) -> None:
    with _create_v2_websocket_client(monkeypatch, tmp_path, keepalive_seconds="0.001") as client:
        token, context_token = _seed_v2_login_and_context_for_ws(client)
        session_id = _create_v2_ws_session(client, token=token, context_token=context_token)

        with client.websocket_connect(
            f"/api/v2/ws/sessions/{session_id}?token={token}&context_token={context_token}"
        ) as websocket:
            ready_event = websocket.receive_json()
            keepalive_event = websocket.receive_json()

    assert ready_event["event_type"] == "session.ready"
    assert ready_event["session_id"] == session_id
    assert ready_event["seq"] == 0
    assert keepalive_event["event_type"] == "stream.keepalive"
    assert keepalive_event["seq"] == 0
```

- [x] **Step 5: 写失败测试，确认 `after_seq` 会回放 durable V2 events**

```python
def test_v2_session_stream_ws_replays_events_after_requested_seq(monkeypatch, tmp_path) -> None:
    with _create_v2_websocket_client(monkeypatch, tmp_path, keepalive_seconds="1") as client:
        token, context_token = _seed_v2_login_and_context_for_ws(client)
        session_id = _create_v2_ws_session(client, token=token, context_token=context_token)
        _post_v2_ws_message(client, token=token, context_token=context_token, session_id=session_id, text="one")
        _post_v2_ws_message(client, token=token, context_token=context_token, session_id=session_id, text="two")

        with client.websocket_connect(
            f"/api/v2/ws/sessions/{session_id}?token={token}&context_token={context_token}&after_seq=2"
        ) as websocket:
            ready_event = websocket.receive_json()
            replayed_event = websocket.receive_json()

    assert ready_event["event_type"] == "session.ready"
    assert replayed_event["event_type"] == "message.created"
    assert replayed_event["seq"] == 3
    assert replayed_event["data"]["preview_text"] == "two"
```

- [x] **Step 6: 运行测试并确认红灯**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_session_stream_ws.py -q
```

Expected: FAIL，原因是 `/api/v2/ws/sessions/{session_id}` 尚未实现。

### Task 2: 复用连接管理器支持 V2 durable replay

**Files:**
- Modify: `backend/app/realtime/connection_manager.py`
- Modify: `backend/app/api/v2/routes/conversation.py`

- [x] **Step 1: 给 manager 增加 pending loader 参数，默认保持 v1 行为**

实现要点：

```python
PendingEventLoader = Callable[[object, str, int], list[SessionStreamEventEnvelope]]
```

`SessionStreamConnectionManager.__init__` 新增 `pending_event_loader: PendingEventLoader | None = None`，未提供时使用 v1 `list_session_events_after`。`_flush_pending_events(...)` 内部调用 `self.pending_event_loader(db_session, session_id, after_seq)`。

- [x] **Step 2: 在 V2 路由中传入闭包 loader**

实现要点：

```python
def _load_v2_pending_events(db_session, session_id: str, after_seq: int):
    return list_v2_session_events_after(
        db_session,
        tenant_id=context.tenant_id,
        shop_id=context.shop_id,
        session_id=session_id,
        after_seq=after_seq,
    )
```

闭包绑定当前 `tenant_id` 与 `shop_id`，确保 manager 即使只拿到 `session_id` 也不会跨上下文回放。

- [x] **Step 3: 实现 V2 websocket route**

实现边界：

- 缺少 `token` 或 `context_token` 时调用 `_close_websocket(..., code=4401)`。
- `resolve_v2_auth_session(...)` 返回 `None` 时关闭 `4401`。
- context session 不存在、非 active、过期时关闭 `4401`。
- account/context 不匹配时关闭 `4401`。
- `get_v2_session(...)` 找不到当前 context 下 session 时关闭 `4404`。
- `after_seq` 解析失败时回退到 `session.last_event_seq`。
- 连接后循环接收，直到 websocket disconnect。
- finally 中关闭数据库 session，并在已连接时从 manager 断开。

- [x] **Step 4: 重跑 V2 websocket 测试确认绿灯**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_session_stream_ws.py -q
```

Expected: PASS。

### Task 3: 鉴权重校验与相关回归

**Files:**
- Modify: `backend/tests/test_v2_session_stream_ws.py`
- Modify: `backend/app/api/v2/routes/conversation.py`

- [x] **Step 1: 写失败测试，确认 auth logout 后 websocket 在 keepalive 周期关闭 `4401`**

```python
def test_v2_session_stream_ws_closes_when_auth_session_is_revoked(monkeypatch, tmp_path) -> None:
    with _create_v2_websocket_client(monkeypatch, tmp_path, keepalive_seconds="0.001") as client:
        token, context_token = _seed_v2_login_and_context_for_ws(client)
        session_id = _create_v2_ws_session(client, token=token, context_token=context_token)

        with client.websocket_connect(
            f"/api/v2/ws/sessions/{session_id}?token={token}&context_token={context_token}"
        ) as websocket:
            assert websocket.receive_json()["event_type"] == "session.ready"
            logout = client.post("/api/v2/auth/logout", headers={"Authorization": f"Bearer {token}"})
            assert logout.status_code == 200

            disconnect = None
            for _ in range(25):
                try:
                    websocket.receive_json()
                except WebSocketDisconnect as exc:
                    disconnect = exc
                    break

    assert disconnect is not None
    assert disconnect.code == 4401
```

- [x] **Step 2: 实现 V2 websocket `auth_is_valid` 回调**

实现要点：

```python
def _is_v2_websocket_auth_still_valid(...):
    refreshed_auth = resolve_v2_auth_session(db_session, bearer_token=token)
    refreshed_context = _resolve_v2_context_session(db_session, context_token=context_token)
    return (
        refreshed_auth is not None
        and refreshed_context is not None
        and refreshed_auth.account_id == expected_account_id
        and refreshed_context.account_id == expected_account_id
        and refreshed_context.tenant_id == expected_tenant_id
        and refreshed_context.shop_id == expected_shop_id
    )
```

- [x] **Step 3: 运行 websocket 与现有 stream/API 相关测试**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_session_stream_ws.py backend/tests/test_v2_session_stream_api.py backend/tests/test_session_stream_ws.py -q
```

Expected: PASS，且 v1 websocket 行为未回归。

### Task 4: 合约快照与阶段验收

**Files:**
- Verify: `backend/tests/test_openapi_contract_snapshot.py`
- Verify: `project_docs/generated/openapi-v1.json`

- [x] **Step 1: 生成 OpenAPI snapshot**

Run:

```powershell
$env:PYTHONPATH="backend"; python backend/scripts/generate_openapi_snapshot.py
```

- [x] **Step 2: 运行本切片相关测试**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_session_stream_ws.py backend/tests/test_v2_session_stream_api.py backend/tests/test_session_stream_ws.py backend/tests/test_openapi_contract_snapshot.py -q
```

Expected: PASS。

## 自检

- spec 覆盖：本计划覆盖阶段 6 的 websocket replay 要求，并保持“数据库事件是真相，websocket 是投影分发”的原则。
- 占位扫描：无 TBD、TODO、implement later。
- 类型一致性：V2 websocket 使用现有 `V2SessionStreamEventData` 字段，不引入新的 event envelope。
