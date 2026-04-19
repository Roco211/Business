# AI 原生 SaaS V2 票据意图形状约束实施计划

> **给智能执行代理（agentic workers）：** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 按任务逐项实现本计划。步骤使用 checkbox（`- [ ]`）语法跟踪。

**Goal:** 收紧 `POST /api/v2/sessions/{session_id}/messages` 的 `message_kind / intent_type` 组合边界，确保 `document.receipt.extract` 只出现在 `receipt-image` 消息上，避免非票据输入错误地进入票据文档抽取语义。

**Architecture:** 本切片只补 message API 的输入校验，不改默认 `receipt-image -> document.receipt.extract` 行为，不改 typed inventory intent 行为，也不改 receipt extraction service。路由层继续把校验错误映射为 `422 validation_error`，从而保持“AI/调用方可以建议，但后端必须验证语义边界”的原则。

**Tech Stack:** Python、FastAPI、SQLAlchemy、pytest、现有 V2 conversation 服务

---

## 文件结构

- 修改 `backend/tests/test_v2_conversation_runtime.py`：新增非法 message/intention 组合测试。
- 修改 `backend/app/services/v2_conversation.py`：在 message intent 归一化中校验 `document.receipt.extract` 的输入形状。

### Task 1: 固定非法 receipt intent 组合行为

**Files:**
- Modify: `backend/tests/test_v2_conversation_runtime.py`

- [x] **Step 1: 新增失败测试，确认 text message 不能显式声明 document.receipt.extract**

```python
assert response.status_code == 422
assert response.json()["error"]["code"] == "validation_error"
```

- [x] **Step 2: 运行红灯测试**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_conversation_runtime.py::test_v2_post_message_rejects_receipt_extraction_intent_for_non_receipt_message -q
```

Expected: FAIL，因为当前实现会接受该组合。

### Task 2: 实现 receipt intent 形状校验

**Files:**
- Modify: `backend/app/services/v2_conversation.py`

- [x] **Step 1: 在 message intent 归一化逻辑中拒绝非 receipt-image 的 document.receipt.extract**

```python
if normalized == RECEIPT_EXTRACTION_INTENT_TYPE and normalized_message_kind != "receipt-image":
    raise V2UnsupportedIntentTypeError(...)
```

- [x] **Step 2: 保持 receipt-image 默认 intent 和显式 inventory intent 行为不变**

- [x] **Step 3: 重跑目标测试，确认绿灯**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_conversation_runtime.py::test_v2_post_message_rejects_receipt_extraction_intent_for_non_receipt_message -q
```

Expected: PASS。

### Task 3: 局部回归与整理

**Files:**
- Verify: `backend/tests/test_v2_conversation_runtime.py`
- Verify: `backend/tests/test_v2_media_ai_platform.py`

- [x] **Step 1: 运行相关测试切片**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_conversation_runtime.py::test_v2_post_receipt_message_defaults_to_receipt_extraction_intent backend/tests/test_v2_conversation_runtime.py::test_v2_post_message_rejects_receipt_extraction_intent_for_non_receipt_message backend/tests/test_v2_conversation_runtime.py::test_v2_post_message_accepts_explicit_inventory_intent backend/tests/test_v2_media_ai_platform.py::test_v2_extract_receipt_document_without_line_items_falls_back_to_clarification -q
```

Expected: PASS。

- [x] **Step 2: 检查 diff 与工作区状态**

Run:

```powershell
git diff --check
git status --short --untracked-files=no
```

Expected: 无格式错误，只包含本刀相关变更。
