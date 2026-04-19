# AI 原生 SaaS V2 票据草稿失败转澄清实施计划

> **给智能执行代理（agentic workers）：** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 按任务逐项实现本计划。步骤使用 checkbox（`- [ ]`）语法跟踪。

**Goal:** 当 receipt OCR 成功生成 document，但无法自动生成 `inventory.stock_in` draft/confirmation 时，将 `task_run` 显式推进到 `needs_clarification` 并创建 clarification，而不是返回未处理异常。

**Architecture:** 保持 document 持久化与 OCR observability 不变。仅在 `backend/app/services/v2_receipt_documents.py` 中捕获 receipt draft validation 失败，并调用新的“document -> clarification” helper，把可用 provenance 与 raw_text 放进 clarification draft payload，继续遵守“不确定性进入澄清/确认工作流”的架构原则。

**Tech Stack:** Python、FastAPI、SQLAlchemy、pytest、现有 V2 media_ai / conversation / receipt draft 服务

---

## 文件结构

- 修改 `backend/app/services/v2_receipt_stock_in_drafts.py`：新增从 receipt document 创建 clarification 的 helper。
- 修改 `backend/app/services/v2_receipt_documents.py`：捕获 receipt draft validation error 并自动降级到 clarification。
- 修改 `backend/tests/test_v2_media_ai_platform.py`：新增 receipt extraction clarification fallback 红绿测试。

### Task 1: 用失败测试固定 clarification fallback 预期

**Files:**
- Modify: `backend/tests/test_v2_media_ai_platform.py`

- [x] **Step 1: 新增 API 测试，模拟 OCR 没有 line items**

```python
assert response.status_code == 201
assert task_response.json()["data"]["status"] == "needs_clarification"
assert clarifications_response.json()["data"]["count"] == 1
assert clarifications_response.json()["data"]["clarifications"][0]["reason_code"] == "receipt_stock_in_fields_missing"
assert pending_confirmations_response.json()["data"]["count"] == 0
assert stream_events[-1]["event_type"] == "task.updated"
assert stream_events[-1]["data"]["status"] == "needs_clarification"
```

- [x] **Step 2: 运行红灯测试**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_media_ai_platform.py::test_v2_extract_receipt_document_without_line_items_falls_back_to_clarification -q
```

Expected: FAIL，因为当前自动 confirmation 路径会抛 `V2ReceiptStockInDraftValidationError`，不会转成 clarification。

### Task 2: 在 receipt document 路径中自动降级到 clarification

**Files:**
- Modify: `backend/app/services/v2_receipt_stock_in_drafts.py`
- Modify: `backend/app/services/v2_receipt_documents.py`

- [x] **Step 1: 新增 document -> clarification helper**

```python
def create_v2_receipt_stock_in_clarification_from_document(...):
    document = get_v2_document(...)
    clarification_draft_payload = {
        "raw_text": document.extracted_fields.get("raw_text"),
        "source_type": "receipt-document",
        "source_document_id": document.document_id,
        "source_media_asset_id": document.media_asset_id,
    }
    return create_v2_clarification(
        ...,
        reason_code="receipt_stock_in_fields_missing",
        question_text="I could not identify a complete receipt line item. Please confirm item name, quantity, unit, and price.",
        requested_fields=["item_name", "quantity", "unit", "price"],
        draft_payload=clarification_draft_payload,
    )
```

- [x] **Step 2: 在 receipt extraction 中捕获 validation error 并调用 clarification helper**

```python
try:
    create_v2_receipt_stock_in_confirmation_from_document(...)
except V2ReceiptStockInDraftValidationError:
    create_v2_receipt_stock_in_clarification_from_document(...)
```

- [x] **Step 3: 重跑目标测试，确认绿灯**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_media_ai_platform.py::test_v2_extract_receipt_document_without_line_items_falls_back_to_clarification -q
```

Expected: PASS。

### Task 3: 局部回归与整理

**Files:**
- Verify: `backend/tests/test_v2_media_ai_platform.py`
- Verify: `backend/app/services/v2_receipt_stock_in_drafts.py`
- Verify: `backend/app/services/v2_receipt_documents.py`

- [x] **Step 1: 运行本刀相关测试切片**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_media_ai_platform.py -q
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_session_stream_ws.py::test_v2_session_stream_ws_pushes_receipt_extraction_progression_without_waiting_for_keepalive -q
```

Expected: PASS。按用户要求只跑本次改动涉及的 API / stream 相关切片，不做完整 backend 回归。

- [ ] **Step 2: 检查 diff 与工作区状态**

Run:

```powershell
git diff --check
git status --short
```

Expected: 无格式错误，只包含本刀相关改动。
