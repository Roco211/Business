# AI 原生 SaaS V2 系统结果流事件载荷闭环实施计划

> **给智能执行代理（agentic workers）：** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 按任务逐项实现本计划。步骤使用 checkbox（`- [ ]`）语法跟踪。

**Goal:** 让 `system_result` 类型的 `message.created` stream event 直接携带结构化 `payload_json` 和关联 `task_run_id`，使 receipt 流程的 websocket / replay 消费端无需额外拉取消息列表就能拿到 confirmation 与 provenance。

**Architecture:** 保持普通消息流事件仍然只暴露轻量预览字段；仅对 `message_kind == "system_result"` 的消息，把原始 `payload_json` 透传进 stream event `data`，并在事件顶层补齐 `task_run_id`。receipt 相关测试将直接断言 websocket 和 replay 里都能拿到 `source_document_id` / `source_media_asset_id`。

**Tech Stack:** Python、FastAPI、SQLAlchemy、pytest、现有 V2 conversation / session stream / websocket 基础设施

---

## 文件结构

- 修改 `backend/app/services/v2_conversation.py`：扩展 `append_v2_message_created_event(...)` 的 system result stream 负载。
- 修改 `backend/tests/test_v2_session_stream_ws.py`：补 receipt extraction websocket 事件 payload 红绿测试。
- 修改 `backend/tests/test_v2_clarification_confirmation.py`：补 receipt-derived commit replay 事件 payload 红绿测试。

### Task 1: 用失败测试固定 system_result stream payload 缺口

**Files:**
- Modify: `backend/tests/test_v2_session_stream_ws.py`
- Modify: `backend/tests/test_v2_clarification_confirmation.py`

- [x] **Step 1: 给 receipt extraction websocket 测试补结构化 payload 断言**

```python
assert third_event["task_run_id"] == task_run_id
assert third_event["data"]["payload_json"]["confirmation_id"]
assert third_event["data"]["payload_json"]["source_type"] == "receipt-document"
assert third_event["data"]["payload_json"]["source_document_id"]
assert third_event["data"]["payload_json"]["source_media_asset_id"] == media_asset_id
```

- [x] **Step 2: 新增 receipt-derived commit replay 测试**

```python
stream_events = _list_v2_stream_events(...)
system_result_event = stream_events[-2]

assert system_result_event["event_type"] == "message.created"
assert system_result_event["task_run_id"] == task_run_id
assert system_result_event["data"]["message_kind"] == "system_result"
assert system_result_event["data"]["payload_json"]["source_type"] == "receipt-document"
assert "receipt stock-in committed" in system_result_event["data"]["payload_json"]["text"].lower()
```

- [x] **Step 3: 运行红灯测试**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_session_stream_ws.py::test_v2_session_stream_ws_pushes_receipt_extraction_progression_without_waiting_for_keepalive backend/tests/test_v2_clarification_confirmation.py::test_v2_approve_receipt_derived_stock_in_confirmation_appends_receipt_provenance_to_stream_event_message -q
```

Expected: FAIL，因为当前 `message.created` 事件 data 仍然只有 `preview_text` / `actor_type` / `actor_id` / `message_kind`。

### Task 2: 仅为 system_result stream event 透传 payload_json

**Files:**
- Modify: `backend/app/services/v2_conversation.py`

- [x] **Step 1: 抽出 message.created 事件 data builder**

```python
def _build_v2_message_created_event_data(message: V2Message) -> dict[str, object]:
    data = {
        "message_kind": message.message_kind,
        "actor_type": message.actor_type,
        "actor_id": message.actor_id,
        "preview_text": _message_preview_text(message.payload_json, message.message_kind),
    }
    if message.message_kind == SYSTEM_RESULT_MESSAGE_KIND:
        data["payload_json"] = dict(message.payload_json)
    return data
```

- [x] **Step 2: 把 system_result 的 `task_run_id` 写到 stream event 顶层**

```python
def _resolve_v2_message_event_task_run_id(message: V2Message) -> str | None:
    raw_task_run_id = message.payload_json.get("task_run_id")
    return raw_task_run_id.strip() if isinstance(raw_task_run_id, str) and raw_task_run_id.strip() else None
```

- [x] **Step 3: 重跑目标测试，确认绿灯**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_session_stream_ws.py::test_v2_session_stream_ws_pushes_receipt_extraction_progression_without_waiting_for_keepalive backend/tests/test_v2_clarification_confirmation.py::test_v2_approve_receipt_derived_stock_in_confirmation_appends_receipt_provenance_to_stream_event_message -q
```

Expected: PASS。

### Task 3: 局部回归与整理

**Files:**
- Verify: `backend/tests/test_v2_session_stream_ws.py`
- Verify: `backend/tests/test_v2_clarification_confirmation.py`
- Verify: `backend/app/services/v2_conversation.py`

- [x] **Step 1: 运行本刀相关测试切片**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_session_stream_ws.py backend/tests/test_v2_clarification_confirmation.py -q
```

Expected: PASS。

- [x] **Step 2: 检查 diff 与工作区状态**

Run:

```powershell
git diff --check
git status --short
```

Expected: 无格式错误，只包含本刀相关改动。
