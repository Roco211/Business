# AI 原生 SaaS V2 票据文档生成入库草稿实施计划

> **给智能执行代理（agentic workers）：** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 按任务逐项实现本计划。步骤使用 checkbox（`- [ ]`）语法跟踪。

**Goal:** 让已完成 OCR 的 V2 采购票据文档可以生成待确认的 `inventory.stock_in` 任务草稿，但不直接写入库存业务真相。

**Architecture:** 新增一个独立服务把 `V2Document.extracted_fields["items"][0]` 映射为现有单条入库草稿 payload，并通过 `upsert_v2_task_draft` 复用已有 task 状态机、draft 校验和 generic task specialization。receipt extraction 若关联了 `task_run_id`，在文档创建成功后自动生成草稿，让用户下一步可以调用既有 confirmation API；库存 ledger/snapshot 仍只在确认审批后写入。

**Tech Stack:** Python、FastAPI、SQLAlchemy、pytest、现有 V2 media_ai / conversation / inventory 服务

---

## 文件结构

- 新建 `backend/app/services/v2_receipt_stock_in_drafts.py`：负责从 receipt document 生成 `inventory.stock_in` 草稿。
- 修改 `backend/app/services/v2_receipt_documents.py`：在 receipt extraction 成功且提供 `task_run_id` 时调用草稿生成服务。
- 修改 `backend/app/services/v2_conversation.py`：允许 `document.receipt.extract` 这类 document task 被 specialization 为业务草稿。
- 修改 `backend/tests/test_v2_media_ai_platform.py`：补 service 与 API 级别验收测试。

### Task 1: Document-to-draft service

**Files:**
- Create: `backend/app/services/v2_receipt_stock_in_drafts.py`
- Modify: `backend/app/services/v2_conversation.py`
- Modify: `backend/tests/test_v2_media_ai_platform.py`

- [x] **Step 1: 写失败测试，固定 receipt document 生成单条 stock-in draft**

测试目标：
- 从 `V2Document.extracted_fields["items"][0]` 读取 `name / quantity / unit / price`。
- 生成 `inventory.stock_in` draft。
- `task_run.status` 进入 `drafted`。
- draft payload 保留 `source_document_id`、`source_media_asset_id`、`source_type`。
- 不写 `V2InventoryLedgerEvent`，不写 `V2InventoryStockSnapshot`。

- [x] **Step 2: 运行红灯测试**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_media_ai_platform.py::test_create_v2_receipt_stock_in_draft_from_document_materializes_first_line_item -q
```

Expected: FAIL，原因是 `app.services.v2_receipt_stock_in_drafts` 尚不存在。

- [x] **Step 3: 实现最小服务**

实现要点：
- 只支持 `document_type == "purchase-receipt"` 且 `extraction_status == "completed"`。
- 只取第一条 line item，暂不实现批量入库。
- 使用 `upsert_v2_task_draft(..., draft_type="inventory.stock_in", ...)`，不直接创建 confirmation，也不写库存真相。
- 对缺少 items 或字段无法通过现有 draft validator 的情况抛出显式 validation error。

- [x] **Step 4: 重跑 service 测试**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_media_ai_platform.py::test_create_v2_receipt_stock_in_draft_from_document_materializes_first_line_item -q
```

Expected: PASS。

### Task 2: Receipt extraction 自动生成 draft

**Files:**
- Modify: `backend/app/services/v2_receipt_documents.py`
- Modify: `backend/tests/test_v2_media_ai_platform.py`

- [x] **Step 1: 写失败测试，固定 API extraction 后 task run 可查询到 stock-in draft**

测试目标：
- `POST /api/v2/documents/receipt-extractions` 仍返回 document。
- `V2ModelCallLog` 继续挂到 `task_run_id / conversation_session_id`。
- `GET /api/v2/task-runs/{task_run_id}` 返回 `status == "drafted"`、`intent_type == "inventory.stock_in"`。
- `draft_payload` 含 OCR 第一条商品和来源 document/media id。
- 继续调用 `POST /api/v2/task-runs/{task_run_id}/confirmations` 可以创建 `inventory.stock_in` confirmation。

- [x] **Step 2: 实现 receipt extraction 接线**

实现要点：
- 在 `extract_v2_receipt_document` 创建 document 后，如果 `normalized_task_run_id` 不为空，调用 document-to-draft service。
- 不改变无 `task_run_id` 的纯文档抽取行为。
- 不扩大库存写入边界，仍然不写 ledger/snapshot。

- [x] **Step 3: 运行 API 目标测试**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_media_ai_platform.py::test_v2_extract_receipt_document_links_task_run_and_session -q
```

Expected: PASS。

### Task 3: 局部回归与提交

**Files:**
- Verify: `backend/tests/test_v2_media_ai_platform.py`
- Verify: `backend/tests/test_v2_clarification_confirmation.py`

- [x] **Step 1: 运行本切片相关测试**

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

Expected: `git diff --check` 无输出，工作区只包含本切片文件。

- [x] **Step 3: 提交并推送**

Run:

```powershell
git add docs/superpowers/plans/2026-04-19-ai-native-saas-v2-receipt-stock-in-draft-from-document.md backend/app/services/v2_receipt_stock_in_drafts.py backend/app/services/v2_receipt_documents.py backend/app/services/v2_conversation.py backend/tests/test_v2_media_ai_platform.py
git commit -m "feat: draft v2 stock-in from receipt document"
git push ssh://git@ssh.github.com:443/Roco211/Business.git codex/ai-native-saas-rewrite:codex/ai-native-saas-rewrite
```
