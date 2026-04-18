# AI 原生 SaaS V2 Runtime Stream Progression Implementation Plan

> **给智能执行代理（agentic workers）：** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 按任务逐项实现本计划。步骤使用 checkbox（`- [ ]`）语法跟踪。

**Goal:** 让 V2 clarification、draft、confirmation、system result 等 runtime 进展也写入 durable session stream，确保 replay / websocket 能感知核心协作状态。

**Architecture:** 继续沿用“业务事实先落库，session stream 只记录 durable projection”的边界，不新增新的业务真相表。`v2_conversation` 内凡是修改 `task_run.status` 的路径，都在同一事务内追加 `task.updated`；凡是创建 `system_result` 消息的路径，都同步追加 `message.created`，使 websocket 能通过现有 replay 机制感知状态推进。

**Tech Stack:** Python、FastAPI、SQLAlchemy、pytest

---

## 文件结构

- Modify: `backend/tests/test_v2_clarification_confirmation.py`
- Modify: `backend/tests/test_v2_session_stream_api.py`
- Modify: `backend/app/services/v2_conversation.py`

### Task 1: 用失败测试钉住 clarification / draft / confirmation 的 stream progression

**Files:**
- Modify: `backend/tests/test_v2_clarification_confirmation.py`
- Modify: `backend/tests/test_v2_session_stream_api.py`

- [x] **Step 1: 写失败测试，确认 `create_v2_clarification(...)` 与 `answer_v2_clarification(...)` 会追加 `task.updated` durable events**

```python
events = list_v2_session_events_after(
    db_session,
    tenant_id="tenant_a",
    shop_id="shop_a1",
    session_id="vsess_001",
    after_seq=0,
)
assert [event.data["status"] for event in events] == [
    "needs_clarification",
    "drafted",
]
```

- [x] **Step 2: 写失败测试，确认 draft -> confirmation -> reject 的 API 流程会追加 `task.updated` 和 `message.created(system_result)`**

```python
assert [event["event_type"] for event in replay["data"]["events"]] == [
    "message.created",
    "task.updated",
    "task.updated",
    "task.updated",
    "message.created",
    "task.updated",
]
assert replay["data"]["events"][-2]["data"]["message_kind"] == "system_result"
assert replay["data"]["events"][-1]["data"]["status"] == "rejected"
```

- [x] **Step 3: 写失败测试，确认 manual review approve 也会追加 `task.updated(executing)`**

```python
assert events[-1].event_type == "task.updated"
assert events[-1].data["status"] == "executing"
```

- [x] **Step 4: 运行目标测试，确认红灯**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_clarification_confirmation.py -k "stream or executing" backend/tests/test_v2_session_stream_api.py -q
```

Expected: FAIL，原因是当前状态推进路径没有追加新的 stream events。

### Task 2: 在同一事务内追加 runtime progression stream events

**Files:**
- Modify: `backend/app/services/v2_conversation.py`

- [x] **Step 1: 在所有 `task_run.status` 变更路径后追加 `append_v2_task_updated_event(...)`**

覆盖范围：

- `upsert_v2_task_draft(...)`
- `create_v2_clarification(...)`
- `create_v2_confirmation(...)`
- `answer_v2_clarification(...)`
- `approve_v2_confirmation(...)`
- `reject_v2_confirmation(...)`

- [x] **Step 2: 在 `append_v2_system_result_message(...)` 内同步追加 `append_v2_message_created_event(...)`**

实现要点：

```python
db_session.add(message)
append_v2_message_created_event(db_session, message=message)
return message
```

- [x] **Step 3: 保持事件顺序稳定**

顺序规则：

- 同一事务里如果既有 system result message 又有 task status 变化，先追加 `message.created`，再追加 `task.updated`。
- clarification / draft / confirmation 这类不生成消息的路径，只追加 `task.updated`。

- [x] **Step 4: 重跑目标测试确认绿灯**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_clarification_confirmation.py -k "stream or executing" backend/tests/test_v2_session_stream_api.py -q
```

### Task 3: 阶段验收

**Files:**
- Verify: `backend/tests/test_v2_clarification_confirmation.py`
- Verify: `backend/tests/test_v2_session_stream_api.py`
- Verify: `backend/tests/test_v2_session_stream_ws.py`

- [x] **Step 1: 运行本切片相关回归**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_clarification_confirmation.py backend/tests/test_v2_session_stream_api.py backend/tests/test_v2_session_stream_ws.py -q
```

- [x] **Step 2: 自检**

- clarification / confirmation 的 durable stream 事件不绕开 `tenant_id` / `shop_id`。
- websocket 不新增新的真相源，只消费这些新增 durable events。
- 没有把 AI 不确定性状态伪装成直接写业务真相。
