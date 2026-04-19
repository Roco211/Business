# AI 原生 SaaS V2 票据澄清回复实时推进实施计划

> **给智能执行代理（agentic workers）：** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 按任务逐项实现本计划。步骤使用 checkbox（`- [ ]`）语法跟踪。

**Goal:** 为 receipt extraction fallback clarification 在 websocket 观察面补齐端到端回归，验证用户回答澄清后，`drafted -> awaiting_confirmation -> committed` 与 receipt provenance 的系统结果消息都能即时推送给订阅端。

**Architecture:** 复用现有 V2 route 层的 best-effort stream publish，不新增 receipt 专属 publish 分支。本刀只在 `backend/tests/test_v2_session_stream_ws.py` 增加 websocket 回归测试，串起 receipt clarification answer、request confirmation、approve confirmation 三个已存在 mutation；如果测试直接绿灯，说明生产代码已有能力，本刀只补观察面回归保护。

**Tech Stack:** Python、FastAPI、Starlette WebSocket、SQLAlchemy、pytest、现有 V2 session stream / conversation / media_ai 服务

---

## 文件结构

- 新增或修改 `backend/tests/test_v2_session_stream_ws.py`：补 receipt clarification answer 的 websocket progression 测试。
- 复核 `backend/app/api/v2/routes/conversation.py`：确认 clarification / confirmation / approve route 都会在成功后 publish session stream events。
- 复核 `backend/app/api/v2/session_stream_publish.py`：确认 publish 逻辑只消费已提交 durable events。

### Task 1: 用 websocket 回归测试钉住 receipt clarification answer 的实时推进链路

**Files:**
- Modify: `backend/tests/test_v2_session_stream_ws.py`
- Test: `backend/tests/test_v2_session_stream_ws.py::test_v2_session_stream_ws_pushes_receipt_clarification_answer_progression_without_waiting_for_keepalive`

- [x] **Step 1: 新增端到端 websocket 测试**

```python
assert answer_event["event_type"] == "task.updated"
assert answer_event["data"]["status"] == "drafted"

assert confirmation_event["event_type"] == "task.updated"
assert confirmation_event["data"]["status"] == "awaiting_confirmation"

assert system_result_event["event_type"] == "message.created"
assert system_result_event["data"]["payload_json"]["source_type"] == "receipt-document"
assert system_result_event["data"]["payload_json"]["source_document_id"] == document_id
assert committed_event["event_type"] == "task.updated"
assert committed_event["data"]["status"] == "committed"
```

- [x] **Step 2: 运行目标测试**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_session_stream_ws.py::test_v2_session_stream_ws_pushes_receipt_clarification_answer_progression_without_waiting_for_keepalive -q
```

Expected: 如果 route 层 publish 或 websocket fanout 有缺口，则 FAIL 在事件缺失、事件顺序错误，或必须等到 pending poll / keepalive 才能看到结果；若直接 PASS，说明现有实现已满足此链路。

### Task 2: 复核现有 publish 边界，必要时做最小修复

**Files:**
- Verify: `backend/app/api/v2/routes/conversation.py`
- Verify: `backend/app/api/v2/session_stream_publish.py`
- Test: `backend/tests/test_v2_session_stream_ws.py::test_v2_session_stream_ws_pushes_receipt_clarification_answer_progression_without_waiting_for_keepalive`

- [x] **Step 1: 复核 clarification 回答路由的 publish 时机**

```python
clarification_cursor = _resolve_v2_clarification_session_cursor(...)
clarification = answer_v2_clarification(...)
_publish_v2_stream_events_best_effort(..., after_seq=after_seq)
```

- [x] **Step 2: 复核 confirmation / approve 路由的 publish 时机**

```python
task_run_cursor = _resolve_v2_task_run_session_cursor(...)
confirmation_cursor = _resolve_v2_confirmation_session_cursor(...)
_publish_v2_stream_events_best_effort(..., after_seq=after_seq)
```

- [x] **Step 3: 重跑目标测试，确认绿灯**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_session_stream_ws.py::test_v2_session_stream_ws_pushes_receipt_clarification_answer_progression_without_waiting_for_keepalive -q
```

Expected: PASS。本次执行中测试首次运行已直接绿灯，说明现有 route 层 publish 与 websocket fanout 已满足该链路，因此无需修改生产代码。

### Task 3: 局部回归与整理

**Files:**
- Verify: `backend/tests/test_v2_session_stream_ws.py`
- Verify: `backend/tests/test_v2_media_ai_platform.py`
- Verify: `backend/tests/test_v2_clarification_confirmation.py`

- [x] **Step 1: 运行相关测试切片**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_session_stream_ws.py::test_v2_session_stream_ws_pushes_receipt_extraction_clarification_without_waiting_for_keepalive backend/tests/test_v2_session_stream_ws.py::test_v2_session_stream_ws_pushes_receipt_clarification_answer_progression_without_waiting_for_keepalive backend/tests/test_v2_media_ai_platform.py::test_v2_receipt_clarification_answer_preserves_provenance_through_confirmation_and_commit backend/tests/test_v2_clarification_confirmation.py::test_v2_approve_receipt_derived_stock_in_confirmation_appends_receipt_provenance_to_stream_event_message -q
```

Expected: PASS。只跑 receipt clarification / confirmation / websocket 相关切片。

- [x] **Step 2: 检查 diff 与工作区状态**

Run:

```powershell
git diff --check
git status --short --branch --untracked-files=no
```

Expected: 无格式错误，只包含本刀相关变更。

- [ ] **Step 3: 提交并推送**

Run:

```powershell
git add docs/superpowers/plans/2026-04-19-ai-native-saas-v2-receipt-clarification-websocket-progression.md backend/tests/test_v2_session_stream_ws.py
git commit -m "test: cover receipt clarification websocket progression chain"
git push ssh://git@ssh.github.com:443/Roco211/Business.git codex/ai-native-saas-rewrite:codex/ai-native-saas-rewrite
```

Expected: 形成一笔只聚焦 receipt clarification websocket progression 的提交。
