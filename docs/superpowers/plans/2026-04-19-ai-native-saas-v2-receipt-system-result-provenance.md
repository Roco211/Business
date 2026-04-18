# AI 原生 SaaS V2 票据系统结果消息来源闭环实施计划

> **给智能执行代理（agentic workers）：** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 按任务逐项实现本计划。步骤使用 checkbox（`- [ ]`）语法跟踪。

**Goal:** 让 receipt-derived confirmation 生成的 `system_result` 消息携带票据来源字段，并在票据审批提交后输出 receipt-specific 文案，便于会话时间线直接回溯对应 document / media。

**Architecture:** 复用 confirmation 上已经存在的 `source_type` / `source_document_id` / `source_media_asset_id`，在 `append_v2_system_result_message(...)` 内统一归一化并附加到消息 `payload_json`。审批提交文案仅在 `inventory.stock_in` 且来源为 `receipt-document` 时切换为 `Receipt stock-in committed.`，其余路径保持不变。

**Tech Stack:** Python、FastAPI、SQLAlchemy、pytest、现有 V2 conversation / media_ai 服务

---

## 文件结构

- 修改 `backend/app/services/v2_conversation.py`：为 system result message 补充 confirmation provenance 透传与 receipt-specific commit 文案。
- 修改 `backend/tests/test_v2_media_ai_platform.py`：补 receipt draft ready message 的 provenance 断言。
- 修改 `backend/tests/test_v2_clarification_confirmation.py`：补 receipt-derived stock-in commit message 的 provenance 与文案断言。

### Task 1: 用失败测试固定 receipt system_result payload

**Files:**
- Modify: `backend/tests/test_v2_media_ai_platform.py`
- Modify: `backend/tests/test_v2_clarification_confirmation.py`

- [x] **Step 1: 给 receipt ready-for-confirmation 消息补 provenance 断言**

```python
assert messages[-1].payload_json["source_type"] == "receipt-document"
assert messages[-1].payload_json["source_document_id"] == document.document_id
assert messages[-1].payload_json["source_media_asset_id"] == media_asset_id
```

- [x] **Step 2: 给 receipt-derived commit 消息补 provenance 与文案断言**

```python
assert messages[-1]["payload_json"]["source_type"] == "receipt-document"
assert messages[-1]["payload_json"]["source_document_id"] == "vdoc_receipt_001"
assert messages[-1]["payload_json"]["source_media_asset_id"] == "vmedia_receipt_001"
assert "receipt stock-in committed" in messages[-1]["payload_json"]["text"].lower()
```

- [x] **Step 3: 运行红灯测试**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_media_ai_platform.py::test_create_v2_receipt_stock_in_confirmation_from_document_appends_system_result_message backend/tests/test_v2_clarification_confirmation.py::test_v2_approve_receipt_derived_stock_in_confirmation_appends_receipt_provenance_to_system_result_message -q
```

Expected: FAIL，因为当前 `append_v2_system_result_message(...)` 还不会附带 provenance，且 stock-in commit 文案仍然是通用的 `Inventory stock-in committed.`。

### Task 2: 在 system_result message 中透传 confirmation provenance

**Files:**
- Modify: `backend/app/services/v2_conversation.py`

- [x] **Step 1: 提取 confirmation provenance 并写入消息 payload**

```python
payload_json = {
    "text": text,
    "task_run_id": task_run.task_run_id,
    "task_run_status": task_run.status,
    "intent_type": task_run.intent_type,
    "confirmation_id": confirmation.confirmation_id,
    "confirmation_type": confirmation.confirmation_type,
    **_build_v2_confirmation_source_payload(confirmation),
}
```

- [x] **Step 2: 仅对 receipt-derived stock-in commit 切换文案**

```python
if confirmation.confirmation_type == "inventory.stock_in" and source_payload.get("source_type") == "receipt-document":
    system_result_text = "Receipt stock-in committed."
else:
    system_result_text = "Inventory stock-in committed."
```

- [x] **Step 3: 重跑目标测试，确认绿灯**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_media_ai_platform.py::test_create_v2_receipt_stock_in_confirmation_from_document_appends_system_result_message backend/tests/test_v2_clarification_confirmation.py::test_v2_approve_receipt_derived_stock_in_confirmation_appends_receipt_provenance_to_system_result_message -q
```

Expected: PASS。

### Task 3: 局部回归与整理

**Files:**
- Verify: `backend/tests/test_v2_media_ai_platform.py`
- Verify: `backend/tests/test_v2_clarification_confirmation.py`
- Verify: `backend/app/services/v2_conversation.py`

- [x] **Step 1: 运行本刀相关测试切片**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_media_ai_platform.py backend/tests/test_v2_clarification_confirmation.py -q
```

Expected: PASS。

- [x] **Step 2: 检查 diff 与工作区状态**

Run:

```powershell
git diff --check
git status --short
```

Expected: 无格式错误，只包含本刀相关改动。
