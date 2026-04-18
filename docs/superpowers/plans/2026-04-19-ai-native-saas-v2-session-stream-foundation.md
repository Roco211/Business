# AI 原生 SaaS V2 Session Stream Foundation 实现计划

> **给智能执行代理（agentic workers）：** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 按任务逐项实现本计划。步骤使用 checkbox（`- [ ]`）语法跟踪。

**Goal:** 为 V2 conversation/runtime 增加 durable session stream 基础，使 V2 会话能够持久记录业务事件并通过 replay API 回放，为后续 notification worker 与 websocket replay 提供事实来源。

**Architecture:** 复用现有 v1 的“数据库事件是真相、websocket 只是分发层”经验，但不复用旧的单门店隐式上下文假设。该切片新增 `v2_session_stream_events` 表和 `v2_conversation_sessions.last_event_seq` 光标，通过 service 在同一事务内追加递增序号事件；首批只接入最小 conversation/runtime 事件发出，并提供 `GET /api/v2/sessions/{session_id}/stream-events` 作为 durable replay 读面。

**Tech Stack:** Python、FastAPI、SQLAlchemy、Alembic、pytest

---

## 文件结构

- 创建 `backend/app/models/v2_realtime.py`：定义 `V2SessionStreamEvent`。
- 修改 `backend/app/models/v2_conversation.py`：给 session 增加 `last_event_seq`。
- 修改 `backend/app/models/__init__.py`：导出新模型。
- 创建 `backend/app/services/v2_session_stream.py`：实现追加与回放。
- 修改 `backend/app/services/v2_conversation.py`：在消息/任务最小流里追加 stream 事件。
- 修改 `backend/app/contracts/v2/conversation.py`：增加 V2 stream replay 返回模型。
- 修改 `backend/app/api/v2/routes/conversation.py`：增加 replay API。
- 创建 `backend/alembic/versions/20260419_01_create_v2_session_stream_events.py`：迁移表与 session cursor。
- 修改 `backend/tests/test_alembic_bootstrap.py`：校验新表、新列、新索引。
- 创建 `backend/tests/test_v2_session_stream_service.py`：覆盖事件追加、顺序与 limit clamp。
- 创建 `backend/tests/test_v2_session_stream_api.py`：覆盖 replay API 授权与最小消息/任务事件回放。
- 修改 `project_docs/generated/openapi-v1.json`：同步新 V2 API 合约。

### Task 1: 固定 schema 与 service 行为

**Files:**
- Create: `backend/tests/test_v2_session_stream_service.py`
- Modify: `backend/tests/test_alembic_bootstrap.py`
- Create: `backend/app/models/v2_realtime.py`
- Modify: `backend/app/models/v2_conversation.py`
- Modify: `backend/app/models/__init__.py`
- Create: `backend/app/services/v2_session_stream.py`
- Create: `backend/alembic/versions/20260419_01_create_v2_session_stream_events.py`

- [x] **Step 1: 先写失败测试，确认 V2 session stream 事件会按 session 递增 seq 追加并可回放**

测试要点：

```python
def test_append_v2_session_event_assigns_incrementing_seq_and_lists_after_cursor(db_session) -> None:
    stream_service = _load_v2_session_stream_service()
    _seed_v2_stream_context(db_session)

    first = stream_service.append_v2_session_event(
        db_session,
        tenant_id="tenant_a",
        shop_id="shop_a1",
        session_id="vsess_001",
        event_type="message.created",
        task_run_id="vtask_001",
        message_id="vmsg_001",
        data={"preview_text": "restock cola"},
    )
    second = stream_service.append_v2_session_event(...)
    db_session.commit()

    replay = stream_service.list_v2_session_events_after(
        db_session,
        tenant_id="tenant_a",
        shop_id="shop_a1",
        session_id="vsess_001",
        after_seq=first.seq,
    )

    assert first.seq == 1
    assert second.seq == 2
    assert [event.event_type for event in replay] == ["task.updated"]
```

- [x] **Step 2: 再写失败测试，确认 replay 会 clamp `limit` 且 session cursor 持久化到 `last_event_seq`**

测试要点：

```python
def test_list_v2_session_events_after_clamps_limit_and_updates_session_cursor(db_session) -> None:
    ...
    session = db_session.get(V2ConversationSession, "vsess_001")
    assert session.last_event_seq == 3
    replay = stream_service.list_v2_session_events_after(..., after_seq=0, limit=999)
    assert len(replay) == 3
```

- [x] **Step 3: 扩展 alembic bootstrap 测试，确认新表、新列和索引存在**

测试要点：

```python
assert "v2_session_stream_events" in inspector.get_table_names()
assert {"last_event_seq"} <= {column["name"] for column in inspector.get_columns("v2_conversation_sessions")}
assert {"event_id", "tenant_id", "shop_id", "session_id", "seq", "event_type", "payload"} <= {
    column["name"] for column in inspector.get_columns("v2_session_stream_events")
}
assert "ix_v2_session_stream_events_session_id_seq" in {
    index["name"] for index in inspector.get_indexes("v2_session_stream_events")
}
```

- [x] **Step 4: 运行 schema/service 测试，确认红灯**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_session_stream_service.py backend/tests/test_alembic_bootstrap.py -q
```

- [x] **Step 5: 实现最小 schema、迁移与 service**

实现边界：

- `V2ConversationSession` 增加 `last_event_seq`，默认 `0`。
- 新表 `v2_session_stream_events` 字段：
  - `event_id`
  - `tenant_id`
  - `shop_id`
  - `session_id`
  - `seq`
  - `event_type`
  - `task_run_id`
  - `message_id`
  - `payload`
  - `occurred_at`
- `append_v2_session_event(...)` 要在同事务内 `SELECT ... FOR UPDATE` 锁定 session，再递增 `last_event_seq`。
- `list_v2_session_events_after(...)` 要按 `seq ASC` 返回并 clamp `limit` 到 `<= 200`。

- [x] **Step 6: 重跑 schema/service 测试**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_session_stream_service.py backend/tests/test_alembic_bootstrap.py -q
```

### Task 2: 固定 V2 replay API 与最小事件发出

**Files:**
- Create: `backend/tests/test_v2_session_stream_api.py`
- Modify: `backend/app/contracts/v2/conversation.py`
- Modify: `backend/app/api/v2/routes/conversation.py`
- Modify: `backend/app/services/v2_conversation.py`
- Modify: `project_docs/generated/openapi-v1.json`

- [x] **Step 1: 先写失败 API 测试，确认 V2 stream replay 需要 `Authorization` + `X-Context-Token`，且能回放最小消息/任务事件**

测试要点：

```python
def test_v2_session_stream_api_replays_message_and_task_events(client, db_session) -> None:
    token, context_token = seed_v2_login_and_context(client, db_session)
    session_id = _create_v2_session(...)
    client.post(
        f"/api/v2/sessions/{session_id}/messages",
        headers={"Authorization": f"Bearer {token}", "X-Context-Token": context_token},
        json={
            "message_kind": "text",
            "payload_json": {"text": "restock cola"},
            "client_request_id": "v2_stream_001",
        },
    )

    unauthorized = client.get(f"/api/v2/sessions/{session_id}/stream-events?after_seq=0")
    response = client.get(
        f"/api/v2/sessions/{session_id}/stream-events?after_seq=0",
        headers={"Authorization": f"Bearer {token}", "X-Context-Token": context_token},
    )

    assert unauthorized.status_code == 401
    assert response.status_code == 200
    assert [event["event_type"] for event in response.json()["data"]["events"]] == [
        "message.created",
        "task.updated",
    ]
```

- [x] **Step 2: 再写失败 API 测试，确认 `after_seq` 和 `limit` 生效，并且跨上下文 session 会返回 404**

- [x] **Step 3: 运行 replay API 测试，确认红灯**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_session_stream_api.py -q
```

- [x] **Step 4: 实现最小事件发出与 replay API**

实现边界：

- 新增 `V2SessionStreamEventData` / `V2SessionStreamReplayData`。
- `GET /api/v2/sessions/{session_id}/stream-events`
  - 依赖 `Authorization` + `X-Context-Token`
  - query: `after_seq`、`limit`
  - 若当前 context 下 session 不存在，返回 `404 session_not_found`
- `create_v2_message_and_task_run(...)` 在同一事务内追加：
  - `message.created`
  - `task.updated`
- 事件 payload 保持最小：
  - `message.created`: `message_kind`、`actor_type`、`actor_id`、`preview_text`
  - `task.updated`: `status`、`intent_type`、`error_code`

- [x] **Step 5: 重跑 replay API 测试并刷新 OpenAPI snapshot**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_session_stream_api.py -q
python backend/scripts/generate_openapi_snapshot.py
```

### Task 3: 阶段验收

**Files:**
- Verify: `backend/tests/test_v2_session_stream_service.py`
- Verify: `backend/tests/test_v2_session_stream_api.py`
- Verify: `backend/tests/test_v2_conversation_runtime.py`
- Verify: `backend/tests/test_alembic_bootstrap.py`
- Verify: `backend/tests/test_openapi_contract_snapshot.py`

- [x] **Step 1: 运行 V2 session stream 目标回归**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_session_stream_service.py backend/tests/test_v2_session_stream_api.py backend/tests/test_v2_conversation_runtime.py backend/tests/test_alembic_bootstrap.py backend/tests/test_openapi_contract_snapshot.py -q
```

- [x] **Step 2: 运行 V2 / worker 关键回归**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_alembic_bootstrap.py backend/tests/test_v2_identity_context.py backend/tests/test_v2_conversation_runtime.py backend/tests/test_v2_clarification_confirmation.py backend/tests/test_v2_inventory_ledger.py backend/tests/test_v2_inventory_read_api.py backend/tests/test_v2_inventory_corrections_api.py backend/tests/test_v2_inventory_stock_out_api.py backend/tests/test_v2_outbox.py backend/tests/test_v2_outbox_dispatch.py backend/tests/test_v2_outbox_worker.py backend/tests/test_v2_outbox_tasks.py backend/tests/test_v2_outbox_runtime_dispatch.py backend/tests/test_v2_outbox_due_scopes.py backend/tests/test_v2_outbox_due_tasks.py backend/tests/test_v2_inventory_projection_replay.py backend/tests/test_v2_internal_api.py backend/tests/test_v2_session_stream_service.py backend/tests/test_v2_session_stream_api.py backend/tests/test_worker_bootstrap.py backend/tests/test_infra_docker_compose.py backend/tests/test_openapi_contract_snapshot.py -q
```
