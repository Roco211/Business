# AI 原生 SaaS V2 Session Stream Fast Poll Implementation Plan

> **给智能执行代理（agentic workers）：** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 按任务逐项实现本计划。步骤使用 checkbox（`- [ ]`）语法跟踪。

**Goal:** 为已连接的 V2 websocket session 增加比 keepalive 更快的 durable event 轮询，使 worker/outbox 追加的 `inventory.updated` 也能在短延迟内推送到客户端。

**Architecture:** 继续坚持“数据库 durable stream 是唯一真相”。不引入 Redis 订阅或新的 notification worker；而是在 `SessionStreamConnectionManager` 中把“pending event flush 频率”与“keepalive 发送频率”拆开，让 app 进程对已连接 session 更频繁地从数据库拉取新增事件，同时保持 keepalive 节奏不变。

**Tech Stack:** Python、FastAPI、SQLAlchemy、Starlette WebSocket、pytest

---

## 文件结构

- Modify: `backend/app/core/config.py`
- Modify: `backend/app/main.py`
- Modify: `backend/app/realtime/connection_manager.py`
- Modify: `.env.example`
- Modify: `backend/tests/test_v2_session_stream_ws.py`

### Task 1: 用失败测试钉住 worker 事件的短延迟推送

**Files:**
- Modify: `backend/tests/test_v2_session_stream_ws.py`

- [x] **Step 1: 写失败测试，确认 outbox dispatch 追加 `inventory.updated` 后，websocket 不必等 keepalive 也能收到**

```python
def test_v2_session_stream_ws_delivers_worker_inventory_update_before_keepalive(monkeypatch, tmp_path) -> None:
    with _create_v2_websocket_client(
        monkeypatch,
        tmp_path,
        keepalive_seconds="5",
        pending_poll_seconds="0.05",
    ) as client:
        token, context_token = _seed_v2_login_and_context_for_ws(client)
        session_id = _create_v2_stock_in_confirmed_session(...)

        with client.websocket_connect(
            f"/api/v2/ws/sessions/{session_id}?token={token}&context_token={context_token}"
        ) as websocket:
            assert websocket.receive_json()["event_type"] == "session.ready"
            started = time.perf_counter()
            _dispatch_v2_outbox_scope()
            inventory_event = websocket.receive_json()
            elapsed = time.perf_counter() - started

    assert elapsed < 1.0
    assert inventory_event["event_type"] == "inventory.updated"
```

- [x] **Step 2: 运行目标测试，确认红灯**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_session_stream_ws.py -k "worker_inventory_update" -q
```

Expected: FAIL，原因是当前 pending flush 节奏仍与 keepalive 绑定。

### Task 2: 拆分 pending poll 与 keepalive 频率

**Files:**
- Modify: `backend/app/core/config.py`
- Modify: `backend/app/main.py`
- Modify: `backend/app/realtime/connection_manager.py`
- Modify: `.env.example`

- [x] **Step 1: 新增 `SESSION_STREAM_PENDING_POLL_SECONDS` 设置**

实现要点：

- `Settings` 增加 `session_stream_pending_poll_seconds: float`
- `get_settings()` 读取 env，默认值建议 `1.0`
- `.env.example` 写出该配置项

- [x] **Step 2: `create_app()` 把 pending poll 配置传给 manager**

```python
app.state.session_stream_manager = SessionStreamConnectionManager(
    keepalive_interval_seconds=settings.session_stream_keepalive_seconds,
    pending_poll_interval_seconds=settings.session_stream_pending_poll_seconds,
    session_factory=get_session_factory(),
)
```

- [x] **Step 3: 调整 manager 循环，让 `_flush_pending_events()` 更频繁执行，但 keepalive 仍按原周期发送**

规则：

- 每个连接继续只维护一个后台 task。
- task 的 sleep 周期使用 `min(pending_poll_interval_seconds, keepalive_interval_seconds)`。
- 每轮先执行 `_flush_pending_events()`。
- 只有到达 keepalive deadline 才发送 `stream.keepalive`。
- 如果 pending poll 更快，不应更频繁发送 keepalive。

- [x] **Step 4: 重跑目标测试确认绿灯**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_session_stream_ws.py -k "worker_inventory_update" -q
```

### Task 3: 阶段验收

**Files:**
- Verify: `backend/tests/test_v2_session_stream_ws.py`
- Verify: `backend/tests/test_v2_session_stream_api.py`
- Verify: `backend/tests/test_v2_clarification_confirmation.py`

- [x] **Step 1: 运行相关回归**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_session_stream_ws.py backend/tests/test_v2_session_stream_api.py backend/tests/test_v2_clarification_confirmation.py -q
```

- [x] **Step 2: 自检**

- 没有新增新的业务真相源。
- worker 产出的 `inventory.updated` 仍来自 durable stream，而不是 websocket side effect。
- 即使快速 poll 失败，也不影响业务提交结果。
