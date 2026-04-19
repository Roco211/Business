# AI 原生 SaaS V2 票据澄清 Worker Task 入口实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 Celery worker task `drain_v2_outbox` 补一条 receipt-derived outbox 回归，确保任务入口自行打开 session、drain 指定 scope 并提交后，`inventory.updated` durable stream 事件仍保留票据来源字段。

**Architecture:** 不改 worker task 生产逻辑，只在 task wrapper 层增加真实 DB 场景测试。测试 seed 一条 receipt clarification 派生的 pending outbox，调用 `app.workers.v2_outbox_tasks.drain_v2_outbox(...)`，验证 task 返回计数、outbox 完成状态和 stream payload。

**Tech Stack:** Python、SQLAlchemy、pytest、Celery task wrapper、现有 V2 outbox worker / session stream 服务

---

## 文件结构

- 修改 `backend/tests/test_v2_outbox_tasks.py`：新增真实 DB 的 worker task entrypoint 回归测试。
- 不修改生产代码：若测试首跑通过，说明当前 worker task wrapper 已正确提交 drain 结果。

### Task 1: 固定 worker task 对 receipt-derived outbox 的真实执行路径

**Files:**
- Modify: `backend/tests/test_v2_outbox_tasks.py`
- Test: `backend/tests/test_v2_outbox_tasks.py::test_v2_outbox_task_drains_receipt_clarification_scope_and_commits_inventory_stream`

- [x] **Step 1: Seed receipt-derived pending outbox 并调用 task**

```python
result = v2_outbox_tasks.drain_v2_outbox(
    "tenant_a",
    "shop_a1",
    batch_limit=10,
    max_batches=2,
    retry_after_seconds=60,
)

assert result["claimed_count"] == 1
assert result["completed_count"] == 1
```

- [x] **Step 2: 验证 task wrapper 已提交 stream 事件**

```python
stream_event = db_session.scalar(...)
assert stream_event.event_type == "inventory.updated"
assert stream_event.payload_json["source_document_id"] == "vdoc_receipt_001"
assert stream_event.payload_json["source_media_asset_id"] == "vmedia_receipt_001"
assert stream_event.payload_json["ledger_source_id"] == "vtask_receipt_worker_task_001"
```

- [x] **Step 3: 运行目标测试**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_outbox_tasks.py::test_v2_outbox_task_drains_receipt_clarification_scope_and_commits_inventory_stream -q
```

Expected: 若 task wrapper 没有提交事务，测试会在 stream event 或 outbox completed 状态处失败；若 worker drain/dispatch 丢 provenance，则会在 payload 来源字段断言处失败；若首跑即 PASS，则说明生产实现已满足要求。本次执行首跑即 PASS，未修改生产代码。

### Task 2: 局部验证与提交

**Files:**
- Verify: `backend/tests/test_v2_outbox_tasks.py`
- Verify: `docs/superpowers/plans/2026-04-19-ai-native-saas-v2-receipt-clarification-worker-task-entrypoint.md`

- [x] **Step 1: 运行 worker task 相关切片**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_outbox_tasks.py::test_v2_outbox_task_wrapper_invokes_drain_and_commits backend/tests/test_v2_outbox_tasks.py::test_v2_outbox_task_drains_receipt_clarification_scope_and_commits_inventory_stream -q
```

Expected: fake wrapper 行为测试与真实 DB entrypoint 测试都通过。

- [x] **Step 2: 检查 diff 与工作区状态**

Run:

```powershell
git diff --check
git status --short --branch --untracked-files=no
```

Expected: 无格式错误；变更只包含本次 plan 文档与 worker task 测试。

- [x] **Step 3: 提交并推送**

Run:

```powershell
git add docs/superpowers/plans/2026-04-19-ai-native-saas-v2-receipt-clarification-worker-task-entrypoint.md backend/tests/test_v2_outbox_tasks.py
git commit -m "test: cover receipt clarification worker task entrypoint"
$env:GIT_SSH_COMMAND='ssh -i ~/.ssh/id_ed25519_github_business_plan -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new -p 443'
git push ssh://git@ssh.github.com:443/Roco211/Business.git codex/ai-native-saas-rewrite:codex/ai-native-saas-rewrite
```

Expected: 形成一笔只聚焦 receipt clarification worker task 入口语义的提交，并同步到远端分支。
