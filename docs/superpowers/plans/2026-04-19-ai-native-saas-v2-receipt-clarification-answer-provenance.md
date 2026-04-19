# AI 原生 SaaS V2 票据澄清回复来源延续实施计划

> **给智能执行代理（agentic workers）：** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 按任务逐项实现本计划。步骤使用 checkbox（`- [ ]`）语法跟踪。

**Goal:** 验证 receipt OCR 因缺少 line item 而转入 clarification 后，用户回答产生的 draft、随后创建的 confirmation，以及最终 inventory commit 产物都持续保留 `source_type` / `source_document_id` / `source_media_asset_id` provenance。

**Architecture:** 复用现有 `answer_v2_clarification()` 的“clarification draft payload + answer payload”合并语义，以及 `build_v2_confirmation_source_payload()` 对 confirmation draft/resolution 的回退读取规则。本刀优先用一条 API 级端到端回归测试把 receipt fallback clarification -> answer -> confirmation -> approve 串起来；若测试暴露 provenance 丢失，则只在 `backend/app/services/v2_conversation.py` 做最小修复，不新增 receipt 专属分支。

**Tech Stack:** Python、FastAPI、SQLAlchemy、pytest、现有 V2 conversation / media_ai / inventory 服务

---

## 文件结构

- 修改 `backend/tests/test_v2_media_ai_platform.py`：新增 receipt clarification answer provenance 端到端回归测试。
- 复核 `backend/app/services/v2_conversation.py`：确认 clarification answer 产生的 draft 与 confirmation 持续保留 provenance。
- 验证 `backend/tests/test_v2_clarification_confirmation.py`：确认已有 receipt commit provenance 测试与新链路认知一致。

### Task 1: 用端到端测试钉住 clarification answer 之后的 provenance 链路

**Files:**
- Modify: `backend/tests/test_v2_media_ai_platform.py`
- Test: `backend/tests/test_v2_media_ai_platform.py::test_v2_receipt_clarification_answer_preserves_provenance_through_confirmation_and_commit`

- [x] **Step 1: 新增 API 测试，串起 receipt fallback clarification -> answer -> confirmation -> approve**

```python
expected_draft_payload = {
    "raw_text": "Unreadable receipt text",
    "source_type": "receipt-document",
    "source_document_id": document_id,
    "source_media_asset_id": media_asset_id,
    "item_name": "Sprite 330ml",
    "quantity": 2,
    "unit": "can",
    "price": 6.5,
}

assert drafted_task_response.json()["data"]["intent_type"] == "document.receipt.extract"
assert drafted_task_response.json()["data"]["draft_payload"] == expected_draft_payload
assert confirmation_response.json()["data"]["draft_payload"] == expected_draft_payload
assert awaiting_task_response.json()["data"]["intent_type"] == "inventory.stock_in"
assert audit_log.metadata_json["source_document_id"] == document_id
assert outbox_event.payload_json["source_media_asset_id"] == media_asset_id
assert messages[-1]["payload_json"]["source_type"] == "receipt-document"
```

- [x] **Step 2: 运行目标测试**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_media_ai_platform.py::test_v2_receipt_clarification_answer_preserves_provenance_through_confirmation_and_commit -q
```

Expected: 若 clarification answer 或 draft -> confirmation specialization 丢失 provenance，则 FAIL 在 `draft_payload` / `audit_log` / `outbox_event` / `system_result` 缺少来源字段；若直接 PASS，说明生产逻辑已具备该能力，本刀主要补齐回归保护。

### Task 2: 复核 clarification provenance 关键实现边界

**Files:**
- Verify: `backend/app/services/v2_conversation.py`
- Test: `backend/tests/test_v2_media_ai_platform.py::test_v2_receipt_clarification_answer_preserves_provenance_through_confirmation_and_commit`

- [x] **Step 1: 确保回答澄清时保留 clarification draft payload**

```python
merged_draft_payload = dict(clarification.draft_payload or {})
merged_draft_payload.update(answer_payload)
_upsert_v2_task_draft(
    db_session,
    tenant_id=tenant_id,
    shop_id=shop_id,
    task_run=task_run,
    draft_payload=merged_draft_payload,
    created_by_account_id=answered_by_account_id,
    now=now,
)
```

- [x] **Step 2: 确保从 draft 请求 confirmation 时复制完整 draft payload**

```python
return create_v2_confirmation(
    db_session,
    tenant_id=tenant_id,
    shop_id=shop_id,
    task_run_id=task_run_id,
    confirmation_type=confirmation_type,
    draft_payload=dict(draft.payload_json),
)
```

- [x] **Step 3: 重跑目标测试，确认绿灯**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_media_ai_platform.py::test_v2_receipt_clarification_answer_preserves_provenance_through_confirmation_and_commit -q
```

Expected: PASS。本次执行中该测试首次运行已直接绿灯，说明现有 `answer_v2_clarification()` 与 `request_v2_confirmation_from_task_draft()` 已满足 provenance 延续语义，因此不需要修改生产代码。

### Task 3: 局部回归与整理

**Files:**
- Verify: `backend/tests/test_v2_media_ai_platform.py`
- Verify: `backend/tests/test_v2_clarification_confirmation.py`
- Verify: `backend/app/services/v2_conversation.py`

- [x] **Step 1: 运行本刀相关测试切片**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_media_ai_platform.py::test_v2_extract_receipt_document_without_line_items_falls_back_to_clarification backend/tests/test_v2_media_ai_platform.py::test_v2_receipt_clarification_answer_preserves_provenance_through_confirmation_and_commit backend/tests/test_v2_clarification_confirmation.py::test_v2_approve_receipt_derived_stock_in_confirmation_appends_receipt_provenance_to_audit_log_and_outbox_event -q
```

Expected: PASS。按用户要求只跑 receipt clarification / confirmation provenance 相关切片，不做完整 backend 回归。

- [x] **Step 2: 检查 diff 与工作区状态**

Run:

```powershell
git diff --check
git status --short --branch --untracked-files=no
```

Expected: 无格式错误，只包含本刀相关改动。

- [x] **Step 3: 提交本刀**

Run:

```powershell
git add docs/superpowers/plans/2026-04-19-ai-native-saas-v2-receipt-clarification-answer-provenance.md backend/tests/test_v2_media_ai_platform.py backend/app/services/v2_conversation.py
git commit -m "test: cover receipt clarification provenance chain"
```

Expected: 生成一笔聚焦 receipt clarification provenance 闭环的提交；若最终未改 `backend/app/services/v2_conversation.py`，提交时只加入实际变更文件。
