# AI 原生 SaaS V2 票据澄清 Due Scope Sweep 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 receipt clarification 派生的库存提交补一条 due-scope sweep 端到端回归，确保 pending outbox 由范围扫描器选中后，仍能生成带票据来源的 `inventory.updated` replay 事件。

**Architecture:** 不新增生产逻辑，不改 outbox due-scope 选择策略。测试沿用现有 receipt OCR 缺行项目、澄清回答、确认审批链路，但将直接 dispatch 替换为 `drain_due_v2_outbox_scopes(...)`，验证定时 sweep 路径与直接 dispatch 路径拥有同等的 durable stream 结果。

**Tech Stack:** Python、FastAPI TestClient、SQLAlchemy、pytest、现有 V2 receipt clarification / outbox due scopes / session stream 服务

---

## 文件结构

- 修改 `backend/tests/test_v2_session_stream_api.py`：新增 due-scope sweep 入口的 receipt clarification replay 回归测试。
- 不修改生产代码：若测试首跑通过，说明当前 due-scope sweep 已经正确衔接 worker drain 与 dispatch。

### Task 1: 固定 receipt clarification pending outbox 的 due-scope sweep 链路

**Files:**
- Modify: `backend/tests/test_v2_session_stream_api.py`
- Test: `backend/tests/test_v2_session_stream_api.py::test_v2_session_stream_api_replays_receipt_clarification_inventory_update_from_due_scope_sweep`

- [x] **Step 1: 新增 due-scope sweep 回归测试**

```python
from app.services.v2_outbox_due_scopes import drain_due_v2_outbox_scopes

result = drain_due_v2_outbox_scopes(
    db_session,
    scope_limit=10,
    batch_limit_per_scope=10,
    max_batches_per_scope=2,
)
db_session.commit()

assert result.scope_count == 1
assert result.claimed_count == 1
assert result.completed_count == 1
```

随后从 `/api/v2/sessions/{session_id}/stream-events?after_seq=0&limit=20` replay，断言 `inventory.updated` 存在且包含 `source_document_id`、`source_media_asset_id`、`ledger_source_id`。

- [x] **Step 2: 运行目标测试**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_session_stream_api.py::test_v2_session_stream_api_replays_receipt_clarification_inventory_update_from_due_scope_sweep -q
```

Expected: 若 due-scope sweep 没有选中该 pending outbox，测试会在 `scope_count` 或 `claimed_count` 处失败；若选中但 dispatch 丢 provenance，则会在 replay payload 来源字段处失败；若首跑即 PASS，则说明生产实现已满足要求。本次执行首跑即 PASS，未修改生产代码。

### Task 2: 局部验证与提交

**Files:**
- Verify: `backend/tests/test_v2_session_stream_api.py`
- Verify: `docs/superpowers/plans/2026-04-19-ai-native-saas-v2-receipt-clarification-due-scope-sweep.md`

- [x] **Step 1: 运行相关 replay/API 切片**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_session_stream_api.py::test_v2_session_stream_api_replays_receipt_clarification_inventory_update_from_due_scope_sweep backend/tests/test_v2_session_stream_api.py::test_v2_session_stream_api_replays_receipt_clarification_inventory_update_provenance -q
```

Expected: due-scope sweep 与直接 dispatch 两条 replay/API 测试都通过。

- [x] **Step 2: 检查 diff 与工作区状态**

Run:

```powershell
git diff --check
git status --short --branch --untracked-files=no
```

Expected: 无格式错误；变更只包含本次 plan 文档与 API 测试。

- [x] **Step 3: 提交并推送**

Run:

```powershell
git add docs/superpowers/plans/2026-04-19-ai-native-saas-v2-receipt-clarification-due-scope-sweep.md backend/tests/test_v2_session_stream_api.py
git commit -m "test: cover receipt clarification due scope sweep"
$env:GIT_SSH_COMMAND='ssh -i ~/.ssh/id_ed25519_github_business_plan -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new -p 443'
git push ssh://git@ssh.github.com:443/Roco211/Business.git codex/ai-native-saas-rewrite:codex/ai-native-saas-rewrite
```

Expected: 形成一笔只聚焦 receipt clarification due-scope sweep 链路的提交，并同步到远端分支。
