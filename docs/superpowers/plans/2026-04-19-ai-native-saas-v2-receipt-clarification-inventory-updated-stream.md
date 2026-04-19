# AI 原生 SaaS V2 票据澄清库存更新流闭环实施计划

> **给智能执行代理（agentic workers）：** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 按任务逐项实现本计划。步骤使用 checkbox（`- [ ]`）语法跟踪。

**Goal:** 验证 receipt OCR 缺失 line item 后进入 clarification，用户补全并审批提交，再由 outbox dispatch 派发 `inventory.updated` 时，replay API 与 websocket 消费面都持续保留票据文档 provenance。

**Architecture:** 不新增业务写入路径，不改变 inventory ledger / outbox / projection 的职责。测试完整走现有 receipt clarification answer API 链路，再手动触发 `dispatch_v2_outbox_events(...)`，最终分别从 durable replay API 和 websocket pending-poll 消费 `inventory.updated`，确认 provenance 从 clarification draft 延续到 outbox payload，再延续到实时流事件。

**Tech Stack:** Python、FastAPI、Starlette WebSocket、SQLAlchemy、pytest、现有 V2 media_ai / conversation / outbox / session stream 服务

---

## 文件结构

- 修改 `backend/tests/test_v2_session_stream_api.py`：新增 replay API 对 receipt clarification inventory update provenance 的回归测试。
- 修改 `backend/tests/test_v2_session_stream_ws.py`：新增 websocket 对同一链路的实时消费回归测试。
- 复核 `backend/app/services/v2_outbox_dispatch.py`：确认 outbox payload provenance 继续透传到 `inventory.updated` data。

### Task 1: 用 replay API 回归固定 clarification 后的 inventory.updated provenance

**Files:**
- Modify: `backend/tests/test_v2_session_stream_api.py`
- Test: `backend/tests/test_v2_session_stream_api.py::test_v2_session_stream_api_replays_receipt_clarification_inventory_update_provenance`

- [x] **Step 1: 新增端到端 API 测试**

```python
inventory_event = [event for event in events if event["event_type"] == "inventory.updated"][0]
assert inventory_event["task_run_id"] == task_run_id
assert inventory_event["data"]["source_type"] == "receipt-document"
assert inventory_event["data"]["source_document_id"] == document_id
assert inventory_event["data"]["source_media_asset_id"] == media_asset_id
assert inventory_event["data"]["ledger_source_type"] == "task_run"
assert inventory_event["data"]["ledger_source_id"] == task_run_id
```

- [x] **Step 2: 运行目标 replay 测试**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_session_stream_api.py::test_v2_session_stream_api_replays_receipt_clarification_inventory_update_provenance -q
```

Expected: 如果 outbox dispatch 或 replay API 丢 provenance，则 FAIL 在 `inventory.updated` data 缺失来源字段；若直接 PASS，说明生产实现已满足该链路。本次执行首次运行即 PASS。

### Task 2: 用 websocket 回归固定同一 outbox 消费链路

**Files:**
- Modify: `backend/tests/test_v2_session_stream_ws.py`
- Test: `backend/tests/test_v2_session_stream_ws.py::test_v2_session_stream_ws_delivers_receipt_clarification_inventory_update_provenance_before_keepalive`

- [x] **Step 1: 新增 websocket pending-poll 测试**

```python
assert inventory_event["event_type"] == "inventory.updated"
assert inventory_event["session_id"] == session_id
assert inventory_event["task_run_id"] == task_run_id
assert inventory_event["data"]["source_document_id"] == document_id
assert inventory_event["data"]["source_media_asset_id"] == media_asset_id
```

- [x] **Step 2: 运行目标 websocket 测试**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_session_stream_ws.py::test_v2_session_stream_ws_delivers_receipt_clarification_inventory_update_provenance_before_keepalive -q
```

Expected: PASS 或暴露 websocket pending-poll 消费链路缺口。本次执行首次运行即 PASS。

### Task 3: 局部回归与整理

**Files:**
- Verify: `backend/tests/test_v2_session_stream_api.py`
- Verify: `backend/tests/test_v2_session_stream_ws.py`
- Verify: `backend/tests/test_v2_outbox_dispatch.py`

- [x] **Step 1: 运行本刀相关测试切片**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_session_stream_api.py::test_v2_session_stream_api_replays_receipt_clarification_inventory_update_provenance backend/tests/test_v2_session_stream_ws.py::test_v2_session_stream_ws_delivers_receipt_clarification_inventory_update_provenance_before_keepalive backend/tests/test_v2_outbox_dispatch.py::test_dispatch_v2_outbox_events_appends_receipt_provenance_to_inventory_updated_stream_event -q
```

Expected: PASS。只跑 replay / websocket / outbox provenance 相关切片。

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
git add docs/superpowers/plans/2026-04-19-ai-native-saas-v2-receipt-clarification-inventory-updated-stream.md backend/tests/test_v2_session_stream_api.py backend/tests/test_v2_session_stream_ws.py
git commit -m "test: cover receipt clarification inventory update stream"
git push ssh://git@ssh.github.com:443/Roco211/Business.git codex/ai-native-saas-rewrite:codex/ai-native-saas-rewrite
```

Expected: 形成一笔只聚焦 receipt clarification inventory-updated stream 消费面的提交。
