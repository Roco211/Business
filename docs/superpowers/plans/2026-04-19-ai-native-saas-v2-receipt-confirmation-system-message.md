# AI 原生 SaaS V2 票据确认系统消息实施计划

> **给智能执行代理（agentic workers）：** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 按任务逐项实现本计划。步骤使用 checkbox（`- [ ]`）语法跟踪。

**Goal:** 让 receipt extraction 自动发起 confirmation 后，在会话历史中写入一条可读的 `system_result` 消息，明确提示用户当前待确认的入库动作。

**Architecture:** 不改变 confirmation、审批或库存落账逻辑，只在 receipt confirmation helper 成功创建 pending confirmation 后复用现有 `append_v2_system_result_message` 写回一条会话消息。这样 `messages`、`stream_events` 和后续前端都能直接看到“已生成待确认入库草稿”的说明，而不必额外解释当前状态。

**Tech Stack:** Python、FastAPI、SQLAlchemy、pytest、现有 V2 conversation / media_ai 服务

---

## 文件结构

- 修改 `backend/app/services/v2_receipt_stock_in_drafts.py`：在自动发起 confirmation 后追加系统消息。
- 修改 `backend/tests/test_v2_media_ai_platform.py`：补 service/API 级回写消息测试。
- 修改 `docs/superpowers/plans/2026-04-19-ai-native-saas-v2-receipt-confirmation-from-document.md`：补勾上一条计划的“提交并推送”状态。

### Task 1: Confirmation helper system_result writeback

**Files:**
- Modify: `backend/app/services/v2_receipt_stock_in_drafts.py`
- Modify: `backend/tests/test_v2_media_ai_platform.py`

- [x] **Step 1: 写失败测试，固定 helper 会追加 receipt confirmation system_result 消息**

测试目标：
- helper 执行后 `V2Confirmation` 仍为 pending。
- 会话 `messages` 中新增一条 `system_result`。
- 消息 payload 包含 `task_run_id`、`confirmation_id`、`confirmation_type`、`task_run_status`。
- `text` 明确表示 receipt stock-in draft 已准备好等待确认。

- [x] **Step 2: 运行红灯测试**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_media_ai_platform.py::test_create_v2_receipt_stock_in_confirmation_from_document_appends_system_result_message -q
```

Expected: FAIL，因为 helper 目前还不会写回消息。

- [x] **Step 3: 实现最小消息写回**

实现要点：
- 复用现有 `append_v2_system_result_message`。
- 文案明确但简短，例如说明票据入库草稿已生成并等待确认。
- 不额外改动 task_run 状态，不新建额外 confirmation。

- [x] **Step 4: 重跑 service 测试**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_media_ai_platform.py::test_create_v2_receipt_stock_in_confirmation_from_document_appends_system_result_message -q
```

Expected: PASS。

### Task 2: Receipt extraction API 会话可见性

**Files:**
- Modify: `backend/tests/test_v2_media_ai_platform.py`

- [x] **Step 1: 写失败测试，固定 API extraction 后 messages 中存在 confirmation system_result**

测试目标：
- `POST /api/v2/documents/receipt-extractions` 成功后，`GET /api/v2/sessions/{session_id}/messages` 返回一条新的 `system_result`。
- 该消息绑定本次 `task_run_id` 与自动创建的 `confirmation_id`。
- 文案可读，能表达“等待确认”。

- [x] **Step 2: 运行 API 目标测试**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_media_ai_platform.py::test_v2_extract_receipt_document_links_task_run_and_session -q
```

Expected: PASS。

### Task 3: 局部回归与提交

**Files:**
- Verify: `backend/tests/test_v2_media_ai_platform.py`
- Verify: `backend/tests/test_v2_clarification_confirmation.py`
- Modify: `docs/superpowers/plans/2026-04-19-ai-native-saas-v2-receipt-confirmation-from-document.md`

- [x] **Step 1: 运行本切片相关测试**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_media_ai_platform.py backend/tests/test_v2_clarification_confirmation.py -q
```

- [x] **Step 2: 检查 diff 与工作区状态**

Run:

```powershell
git diff --check
git status --short
```

- [ ] **Step 3: 提交并推送**

Run:

```powershell
git add docs/superpowers/plans/2026-04-19-ai-native-saas-v2-receipt-confirmation-system-message.md docs/superpowers/plans/2026-04-19-ai-native-saas-v2-receipt-confirmation-from-document.md backend/app/services/v2_receipt_stock_in_drafts.py backend/tests/test_v2_media_ai_platform.py
git commit -m "feat: append receipt confirmation system message"
git push ssh://git@ssh.github.com:443/Roco211/Business.git codex/ai-native-saas-rewrite:codex/ai-native-saas-rewrite
```
