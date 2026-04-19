# AI 原生 SaaS V2 票据澄清 Outbox Worker 来源透传实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 receipt clarification 派生的库存提交补一层 worker 入口回归保护，确保 `drain_v2_outbox_events(...)` 触发 outbox dispatch 后，`inventory.updated` 事件仍保留票据来源（provenance）字段。

**Architecture:** 本切片不新增业务写入路径，也不改变 outbox worker / dispatch / session stream 的职责边界。测试直接构造 clarification-derived 的 outbox payload，经由 worker service drain 进入现有 dispatch 逻辑，验证 durable stream 事件中的来源字段未丢失。

**Tech Stack:** Python、SQLAlchemy、pytest、现有 V2 outbox worker / dispatch / session stream 服务

---

## 文件结构

- 修改 `backend/tests/test_v2_outbox_worker.py`：新增 worker 级 receipt clarification provenance 回归测试与最小种子辅助函数。
- 复核 `backend/app/services/v2_outbox_worker.py`：确认 worker 仍只负责批量 drain，不自行裁剪 payload。
- 复核 `backend/app/services/v2_outbox_dispatch.py`：确认 `inventory.updated` 仍从 outbox payload 透传 provenance 字段。

### Task 1: 固定 worker 入口对 receipt clarification provenance 的回归保护

**Files:**
- Modify: `backend/tests/test_v2_outbox_worker.py`
- Verify: `backend/app/services/v2_outbox_worker.py`
- Verify: `backend/app/services/v2_outbox_dispatch.py`
- Test: `backend/tests/test_v2_outbox_worker.py::test_drain_v2_outbox_events_preserves_receipt_clarification_provenance_in_inventory_updated_stream`

- [x] **Step 1: 写 worker 级回归测试**

```python
result = worker_service.drain_v2_outbox_events(
    db_session,
    tenant_id="tenant_a",
    shop_id="shop_a1",
    batch_limit=10,
    max_batches=2,
    now=_dt("2026-04-19T10:00:00"),
)

assert result.completed_count == 1
assert stream_event.event_type == "inventory.updated"
assert stream_event.payload_json["source_type"] == "receipt-document"
assert stream_event.payload_json["source_document_id"] == "vdoc_receipt_001"
assert stream_event.payload_json["source_media_asset_id"] == "vmedia_receipt_001"
assert stream_event.payload_json["ledger_source_type"] == "task_run"
assert stream_event.payload_json["ledger_source_id"] == "vtask_receipt_clarification_001"
```

- [x] **Step 2: 运行单测确认当前行为**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_outbox_worker.py::test_drain_v2_outbox_events_preserves_receipt_clarification_provenance_in_inventory_updated_stream -q
```

Expected: 若 worker 入口或 dispatch 过程中丢失 provenance，则断言在 `inventory.updated` payload 缺少来源字段处失败；若首跑即 PASS，则说明生产实现已满足该链路，当前切片只需补回归保护。本次执行首跑即 PASS，未修改生产代码。

- [x] **Step 3: 仅在失败时补最小实现**

```python
for key in INVENTORY_UPDATED_PROVENANCE_KEYS:
    value = outbox_event.payload_json.get(key)
    if value is not None:
        payload[key] = value
```

说明：优先检查 `backend/app/services/v2_outbox_dispatch.py` 的 `_build_inventory_updated_stream_payload(...)` 是否仍完整透传 provenance；如测试首跑已绿，则不修改生产代码。本次测试首跑已绿，因此该步骤无需生产代码变更。

### Task 2: 对 worker 切片做局部回归验证与整理

**Files:**
- Verify: `backend/tests/test_v2_outbox_worker.py`
- Verify: `docs/superpowers/plans/2026-04-19-ai-native-saas-v2-receipt-clarification-outbox-worker-provenance.md`

- [x] **Step 1: 运行 worker 相关测试切片**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_outbox_worker.py -q
```

Expected: `test_v2_outbox_worker.py` 全绿，确认新增 helper 未破坏既有 batch / limit / 空批次行为。

- [ ] **Step 2: 检查 diff 与工作区状态**

Run:

```powershell
git diff --check
git status --short --branch --untracked-files=no
```

Expected: 无格式错误；变更只包含本次 plan 文档与 worker 测试。

- [ ] **Step 3: 提交并推送**

Run:

```powershell
git add docs/superpowers/plans/2026-04-19-ai-native-saas-v2-receipt-clarification-outbox-worker-provenance.md backend/tests/test_v2_outbox_worker.py
git commit -m "test: cover receipt clarification outbox worker provenance"
$env:GIT_SSH_COMMAND='ssh -i ~/.ssh/id_ed25519_github_business_plan -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new -p 443'
git push ssh://git@ssh.github.com:443/Roco211/Business.git codex/ai-native-saas-rewrite:codex/ai-native-saas-rewrite
```

Expected: 形成一笔只聚焦 receipt clarification worker provenance 回归保护的提交，并同步到远端分支。
