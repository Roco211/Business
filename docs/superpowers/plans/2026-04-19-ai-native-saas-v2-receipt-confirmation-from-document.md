# AI 原生 SaaS V2 票据文档自动发起确认实施计划

> **给智能执行代理（agentic workers）：** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 按任务逐项实现本计划。步骤使用 checkbox（`- [ ]`）语法跟踪。

**Goal:** 让已关联 `task_run_id` 的 V2 receipt extraction 在生成 stock-in draft 后，自动进入 `awaiting_confirmation` 并创建 pending confirmation。

**Architecture:** 复用现有 `request_v2_confirmation_from_task_draft`，不新增 confirmation 类型，也不改变库存写入边界。receipt extraction 仍先创建 document，再通过 receipt draft service 生成 `inventory.stock_in` draft，最后自动发起 `inventory.stock_in` confirmation；库存 ledger/snapshot 仍只在审批通过后写入。

**Tech Stack:** Python、FastAPI、SQLAlchemy、pytest、现有 V2 media_ai / conversation / confirmation 服务

---

## 文件结构

- 修改 `backend/app/services/v2_receipt_stock_in_drafts.py`：增加“从 receipt document 自动发起 confirmation”的编排辅助。
- 修改 `backend/app/services/v2_receipt_documents.py`：在已有 draft 生成后自动请求 confirmation。
- 修改 `backend/tests/test_v2_media_ai_platform.py`：补 service/API 红绿测试。

### Task 1: Document-to-confirmation service

**Files:**
- Modify: `backend/app/services/v2_receipt_stock_in_drafts.py`
- Modify: `backend/tests/test_v2_media_ai_platform.py`

- [x] **Step 1: 写失败测试，固定 receipt document 可直接推进到 awaiting_confirmation**

测试目标：
- service 调用后 `task_run.status == "awaiting_confirmation"`。
- 新建 `V2Confirmation`，`confirmation_type == "inventory.stock_in"`。
- `confirmation.draft_payload` 与 draft payload 一致。
- 仍然不写 `V2InventoryLedgerEvent` / `V2InventoryStockSnapshot`。

- [x] **Step 2: 运行红灯测试**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_media_ai_platform.py::test_create_v2_receipt_stock_in_confirmation_from_document_moves_task_to_awaiting_confirmation -q
```

Expected: FAIL，因为新 confirmation helper 尚不存在。

- [x] **Step 3: 实现最小 helper**

实现要点：
- 先复用现有 `create_v2_receipt_stock_in_draft_from_document`。
- 再调用 `request_v2_confirmation_from_task_draft(..., confirmation_type="inventory.stock_in")`。
- 不追加业务真相写入，也不审批。

- [x] **Step 4: 重跑 service 测试**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_media_ai_platform.py::test_create_v2_receipt_stock_in_confirmation_from_document_moves_task_to_awaiting_confirmation -q
```

Expected: PASS。

### Task 2: Receipt extraction 自动推进到 pending confirmation

**Files:**
- Modify: `backend/app/services/v2_receipt_documents.py`
- Modify: `backend/tests/test_v2_media_ai_platform.py`

- [x] **Step 1: 写失败测试，固定 API extraction 后 task run 为 awaiting_confirmation**

测试目标：
- `POST /api/v2/documents/receipt-extractions` 继续返回 document。
- `GET /api/v2/task-runs/{task_run_id}` 返回 `status == "awaiting_confirmation"`。
- `GET /api/v2/confirmations?status=pending` 可看到一条 `inventory.stock_in` confirmation。
- confirmation payload 含 OCR 第一条商品与来源 document/media id。

- [x] **Step 2: 实现 receipt extraction 接线**

实现要点：
- 保持没有 `task_run_id` 时的纯文档抽取路径不变。
- 有 `task_run_id` 时，自动调用 confirmation helper。
- 不改变审批 API 与库存 commit API。

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

- [x] **Step 3: 提交并推送**

Run:

```powershell
git add docs/superpowers/plans/2026-04-19-ai-native-saas-v2-receipt-confirmation-from-document.md backend/app/services/v2_receipt_stock_in_drafts.py backend/app/services/v2_receipt_documents.py backend/tests/test_v2_media_ai_platform.py
git commit -m "feat: request v2 receipt confirmation from document"
git push ssh://git@ssh.github.com:443/Roco211/Business.git codex/ai-native-saas-rewrite:codex/ai-native-saas-rewrite
```
