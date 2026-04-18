# AI 原生 SaaS V2 Session Stream Fanout Implementation Plan

> **给智能执行代理（agentic workers）：** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 按任务逐项实现本计划。步骤使用 checkbox（`- [ ]`）语法跟踪。

**Goal:** 让 V2 durable session stream 在 HTTP 写操作提交成功后，能够 best-effort 即时 fanout 给当前在线 websocket 连接，而不必等 keepalive 周期做 catch-up。

**Architecture:** 继续坚持“数据库 durable event 是真相、websocket 只是分发层”。service 仍只负责写入 durable stream；API route 在 commit 成功后，根据提交前记录的 `last_event_seq` 读取新增区间，并通过 `SessionStreamConnectionManager.publish(...)` 做同进程 best-effort fanout。首版不引入 Redis、notification worker 或跨实例广播。

**Tech Stack:** Python、FastAPI、Starlette WebSocket、SQLAlchemy、AnyIO、pytest

---

## 文件结构

- Modify: `backend/tests/test_v2_session_stream_ws.py`
- Modify: `backend/app/api/v2/routes/conversation.py`

### Task 1: 用失败测试钉住“无需等待 keepalive 的即时 fanout”

**Files:**
- Modify: `backend/tests/test_v2_session_stream_ws.py`

- [x] **Step 1: 写失败测试，确认连接中的 session 在 POST message 后会立即收到 `message.created` 与 `task.updated`**

```python
def test_v2_session_stream_ws_pushes_new_events_without_waiting_for_keepalive(monkeypatch, tmp_path) -> None:
    with _create_v2_websocket_client(monkeypatch, tmp_path, keepalive_seconds="5") as client:
        token, context_token = _seed_v2_login_and_context_for_ws(client)
        session_id = _create_v2_ws_session(client, token=token, context_token=context_token)

        with client.websocket_connect(
            f"/api/v2/ws/sessions/{session_id}?token={token}&context_token={context_token}"
        ) as websocket:
            assert websocket.receive_json()["event_type"] == "session.ready"
            started = time.perf_counter()
            _post_v2_ws_message(...)
            first_event = websocket.receive_json()
            second_event = websocket.receive_json()
            elapsed = time.perf_counter() - started

    assert elapsed < 1.0
    assert [first_event["event_type"], second_event["event_type"]] == ["message.created", "task.updated"]
```

- [x] **Step 2: 运行 websocket 测试，确认红灯**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_session_stream_ws.py -q
```

Expected: FAIL，原因是当前只能靠 keepalive 周期做 pending flush。

### Task 2: 在 route 层实现 after-commit best-effort fanout

**Files:**
- Modify: `backend/app/api/v2/routes/conversation.py`

- [x] **Step 1: 新增 route 级 helper，读取新增 event 区间并 best-effort publish**

实现要点：

```python
def _publish_v2_stream_events_best_effort(...):
    manager = get_session_stream_manager(request.app)
    events = list_v2_session_events_after(...)
    for event in events:
        from_thread.run(manager.publish, session_id=session_id, event=event)
```

要求：

- 只读取 `after_seq` 之后的事件。
- 任意 publish 异常都吞掉，不影响主请求成功返回。
- helper 自己开短生命周期 `db_session`，避免复用已提交 session 做额外状态污染。

- [x] **Step 2: 在 V2 conversation 写路由中记录提交前 cursor，并在成功提交后触发 helper**

首批接入：

- `POST /api/v2/sessions/{session_id}/messages`
- `POST /api/v2/task-runs/{task_run_id}/draft`
- `POST /api/v2/task-runs/{task_run_id}/confirmations`
- `POST /api/v2/clarifications/{clarification_id}/answer`
- `POST /api/v2/confirmations/{confirmation_id}/approve`
- `POST /api/v2/confirmations/{confirmation_id}/reject`

规则：

- 先在当前 context 下定位目标 `session_id` 与提交前 `last_event_seq`。
- service 成功返回后再 publish。
- 如果前置对象不存在，本来就按现有错误语义返回 `404/409`，不 publish。

- [x] **Step 3: 重跑 websocket 测试，确认绿灯**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_session_stream_ws.py -q
```

### Task 3: 阶段验收

**Files:**
- Verify: `backend/tests/test_v2_session_stream_ws.py`
- Verify: `backend/tests/test_v2_session_stream_api.py`
- Verify: `backend/tests/test_v2_clarification_confirmation.py`

- [x] **Step 1: 运行 fanout 相关回归**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_session_stream_ws.py backend/tests/test_v2_session_stream_api.py backend/tests/test_v2_clarification_confirmation.py -q
```

- [x] **Step 2: 自检**

- durable stream 仍是唯一事实来源。
- websocket fanout 失败不会回滚业务提交。
- 不新增跨实例依赖，不提前承诺 Redis / notification worker 方案。
