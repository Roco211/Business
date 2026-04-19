# AI 原生 SaaS V2 票据澄清 Enqueue 交接实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 receipt clarification 派生库存提交补一条 enqueue 交接回归，确保审批完成后触发 `enqueue_v2_outbox_drain(...)` 时，独立事务已经能看到带完整票据来源字段的 pending outbox 事件。

**Architecture:** 不改审批或 enqueue 生产逻辑，只在 `approve_v2_confirmation(...)` 的回归测试上增加 receipt-derived 场景。测试通过 monkeypatch `enqueue_v2_outbox_drain`，在独立 session 中读取 task 与 outbox，验证“先提交、后 enqueue”的交接语义及 provenance 完整性。

**Tech Stack:** Python、SQLAlchemy、pytest、现有 V2 clarification confirmation / outbox runtime dispatch 服务

---

## 文件结构

- 修改 `backend/tests/test_v2_clarification_confirmation.py`：新增 receipt-derived enqueue after commit 回归测试。
- 不修改生产代码：若测试首跑通过，说明当前审批提交与 runtime enqueue 的交接已经满足要求。

### Task 1: 固定 receipt clarification 的 enqueue 交接语义

**Files:**
- Modify: `backend/tests/test_v2_clarification_confirmation.py`
- Test: `backend/tests/test_v2_clarification_confirmation.py::test_v2_approve_receipt_derived_inventory_confirmation_enqueues_outbox_drain_after_commit_with_provenance`

- [x] **Step 1: 新增 receipt-derived enqueue 回归测试**

```python
def fake_enqueue_v2_outbox_drain(*, tenant_id: str, shop_id: str, **kwargs) -> bool:
    verification_session = get_session_factory()()
    try:
        verification_outbox = verification_session.scalar(...)
        observed["source_type"] = verification_outbox.payload_json["source_type"]
        observed["source_document_id"] = verification_outbox.payload_json["source_document_id"]
        observed["source_media_asset_id"] = verification_outbox.payload_json["source_media_asset_id"]
        observed["ledger_source_id"] = verification_outbox.payload_json["ledger_source_id"]
    finally:
        verification_session.close()
    return True
```

断言 enqueue 被调用时：
- `task_status == "committed"`
- `outbox_status == "pending"`
- outbox payload 里的 receipt provenance 字段已经可见

- [x] **Step 2: 运行目标测试**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_clarification_confirmation.py::test_v2_approve_receipt_derived_inventory_confirmation_enqueues_outbox_drain_after_commit_with_provenance -q
```

Expected: 若审批尚未提交就 enqueue，测试会在独立 session 读取 `task_status` 或 `outbox_status` 处失败；若提交了但 provenance 未写入 outbox payload，则会在来源字段断言处失败；若首跑即 PASS，则说明生产实现已满足要求。本次执行首跑即 PASS，未修改生产代码。

### Task 2: 局部验证与提交

**Files:**
- Verify: `backend/tests/test_v2_clarification_confirmation.py`
- Verify: `docs/superpowers/plans/2026-04-19-ai-native-saas-v2-receipt-clarification-enqueue-handoff.md`

- [x] **Step 1: 运行相关 confirmation 切片**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_clarification_confirmation.py::test_v2_approve_inventory_confirmation_enqueues_outbox_drain_after_commit backend/tests/test_v2_clarification_confirmation.py::test_v2_approve_receipt_derived_inventory_confirmation_enqueues_outbox_drain_after_commit_with_provenance -q
```

Expected: 通用 enqueue 与 receipt-derived enqueue 两条切片都通过。

- [x] **Step 2: 检查 diff 与工作区状态**

Run:

```powershell
git diff --check
git status --short --branch --untracked-files=no
```

Expected: 无格式错误；变更只包含本次 plan 文档与 clarification confirmation 测试。

- [x] **Step 3: 提交并推送**

Run:

```powershell
git add docs/superpowers/plans/2026-04-19-ai-native-saas-v2-receipt-clarification-enqueue-handoff.md backend/tests/test_v2_clarification_confirmation.py
git commit -m "test: cover receipt clarification enqueue handoff"
$env:GIT_SSH_COMMAND='ssh -i ~/.ssh/id_ed25519_github_business_plan -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new -p 443'
git push ssh://git@ssh.github.com:443/Roco211/Business.git codex/ai-native-saas-rewrite:codex/ai-native-saas-rewrite
```

Expected: 形成一笔只聚焦 receipt clarification enqueue 交接语义的提交，并同步到远端分支。
