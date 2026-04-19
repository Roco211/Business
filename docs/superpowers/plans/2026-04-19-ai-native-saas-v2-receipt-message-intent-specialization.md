# AI 原生 SaaS V2 票据消息意图前移专门化实施计划

> **给智能执行代理（agentic workers）：** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 按任务逐项实现本计划。步骤使用 checkbox（`- [ ]`）语法跟踪。

**Goal:** 让 `POST /api/v2/sessions/{session_id}/messages` 在 `message_kind="receipt-image"` 且未显式传 `intent_type` 时，直接把 `task_run.intent_type` 设为 `document.receipt.extract`，从 task 创建源头消除后续 receipt extraction 链路中的泛型 `conversation.capture` 语义泄漏。

**Architecture:** 本切片只调整 V2 conversation message 的默认 intent 归一化规则，不改 runtime worker、不改 receipt extraction API、不改 confirmation / commit 边界。显式 `intent_type` 仍优先，其他 message kind 仍保持默认 `conversation.capture`。这样既保留 typed entrypoint 的白名单约束，也让 receipt 文档抽取任务在创建瞬间就拥有正确业务语义。

**Tech Stack:** Python、FastAPI、SQLAlchemy、pytest、现有 V2 conversation / media_ai 服务

---

## 文件结构

- 修改 `backend/tests/test_v2_conversation_runtime.py`：新增 `receipt-image` 默认 intent 测试。
- 修改 `backend/app/services/v2_conversation.py`：让 receipt-image 在未显式传 intent 时默认归一化为 `document.receipt.extract`。

### Task 1: 固定 receipt-image 默认 intent 行为

**Files:**
- Modify: `backend/tests/test_v2_conversation_runtime.py`

- [x] **Step 1: 新增失败测试，确认 receipt-image message 会直接创建 document.receipt.extract task**

```python
assert response.status_code == 201
assert response.json()["data"]["intent_type"] == "document.receipt.extract"
assert task_response.status_code == 200
assert task_response.json()["data"]["intent_type"] == "document.receipt.extract"
```

- [x] **Step 2: 运行红灯测试**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_conversation_runtime.py::test_v2_post_receipt_message_defaults_to_receipt_extraction_intent -q
```

Expected: FAIL，因为当前默认 intent 仍是 `conversation.capture`。

### Task 2: 实现 receipt-image 默认 intent 专门化

**Files:**
- Modify: `backend/app/services/v2_conversation.py`

- [x] **Step 1: 在消息 intent 归一化逻辑中识别 receipt-image 默认值**

```python
if intent_type is None and message_kind == "receipt-image":
    return "document.receipt.extract"
```

- [x] **Step 2: 保持显式 intent 优先，其他 message kind 仍默认 conversation.capture**

- [x] **Step 3: 重跑目标测试，确认绿灯**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_conversation_runtime.py::test_v2_post_receipt_message_defaults_to_receipt_extraction_intent -q
```

Expected: PASS。

### Task 3: 局部回归与整理

**Files:**
- Verify: `backend/tests/test_v2_conversation_runtime.py`
- Verify: `backend/tests/test_v2_media_ai_platform.py`
- Verify: `backend/tests/test_v2_session_stream_ws.py`

- [x] **Step 1: 运行相关测试切片**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_conversation_runtime.py::test_v2_post_message_creates_message_and_captured_task_run backend/tests/test_v2_conversation_runtime.py::test_v2_post_receipt_message_defaults_to_receipt_extraction_intent backend/tests/test_v2_media_ai_platform.py::test_v2_extract_receipt_document_without_line_items_falls_back_to_clarification backend/tests/test_v2_session_stream_ws.py::test_v2_session_stream_ws_pushes_receipt_extraction_clarification_without_waiting_for_keepalive -q
```

Expected: PASS。只验证受本次默认 intent 变化影响的 receipt / conversation 切片。

- [x] **Step 2: 检查 diff 与工作区状态**

Run:

```powershell
git diff --check
git status --short
```

Expected: 无格式错误，只包含本刀相关变更。
