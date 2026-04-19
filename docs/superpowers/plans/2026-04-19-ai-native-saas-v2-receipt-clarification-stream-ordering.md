# AI 原生 SaaS V2 票据澄清 Stream 顺序实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 固定 receipt clarification 派生提交在 durable replay API 中的事件顺序，确保 `system_result`、`task.updated(committed)`、`inventory.updated` 按可恢复顺序被消费。

**Architecture:** 不改变 session stream 写入模型，只在现有端到端 replay 测试里增加顺序与 `after_seq` 后缀断言。该测试继续走真实 receipt OCR 缺行项目、澄清回答、确认、审批、outbox dispatch、replay API 链路，验证前端或 worker 重连时不会错过最终库存更新。

**Tech Stack:** Python、FastAPI TestClient、SQLAlchemy、pytest、现有 V2 session stream / receipt clarification / outbox dispatch 服务

---

## 文件结构

- 修改 `backend/tests/test_v2_session_stream_api.py`：扩展 receipt clarification replay 测试，加入 durable 顺序与 `after_seq` 后缀断言。
- 不修改生产代码：若测试首跑通过，说明现有 stream 追加顺序已符合预期，本切片只补回归保护。

### Task 1: 为 receipt clarification replay 固定 durable 顺序

**Files:**
- Modify: `backend/tests/test_v2_session_stream_api.py`
- Test: `backend/tests/test_v2_session_stream_api.py::test_v2_session_stream_api_replays_receipt_clarification_inventory_update_provenance`

- [x] **Step 1: 增加顺序断言**

```python
assert system_result_event["seq"] < committed_task_event["seq"] < inventory_event["seq"]
```

该断言固定审批提交后用户可见的结果消息先出现，随后任务进入 committed，最后 outbox dispatch 派发库存更新。

- [x] **Step 2: 增加 `after_seq` 后缀 replay 断言**

```python
after_system_result_response = client.get(
    f"/api/v2/sessions/{session_id}/stream-events?after_seq={system_result_event['seq']}&limit=5",
    headers=_headers(token, context_token),
)
after_committed_response = client.get(
    f"/api/v2/sessions/{session_id}/stream-events?after_seq={committed_task_event['seq']}&limit=5",
    headers=_headers(token, context_token),
)

assert [event["seq"] for event in after_system_result_events] == [
    committed_task_event["seq"],
    inventory_event["seq"],
]
assert [event["seq"] for event in after_committed_events] == [inventory_event["seq"]]
```

该断言保护断线重连或 worker 延迟消费时，客户端从任意确认点恢复都能稳定拿到后续库存更新。

- [x] **Step 3: 运行目标 replay 测试**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_session_stream_api.py::test_v2_session_stream_api_replays_receipt_clarification_inventory_update_provenance -q
```

Expected: 若现有 durable 顺序不稳定，则在 `seq` 或 `after_seq` 断言处失败；若首跑即 PASS，则说明生产实现已满足该顺序要求。本次执行首跑即 PASS，未修改生产代码。

### Task 2: 局部验证与提交

**Files:**
- Verify: `backend/tests/test_v2_session_stream_api.py`
- Verify: `docs/superpowers/plans/2026-04-19-ai-native-saas-v2-receipt-clarification-stream-ordering.md`

- [x] **Step 1: 运行相关 replay/API 切片**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_session_stream_api.py::test_v2_session_stream_api_replays_receipt_clarification_inventory_update_provenance -q
```

Expected: 单条 replay/API 测试通过。

- [ ] **Step 2: 检查 diff 与工作区状态**

Run:

```powershell
git diff --check
git status --short --branch --untracked-files=no
```

Expected: 无格式错误；变更只包含本次 plan 文档与 API 测试。

- [ ] **Step 3: 提交并推送**

Run:

```powershell
git add docs/superpowers/plans/2026-04-19-ai-native-saas-v2-receipt-clarification-stream-ordering.md backend/tests/test_v2_session_stream_api.py
git commit -m "test: cover receipt clarification replay ordering"
$env:GIT_SSH_COMMAND='ssh -i ~/.ssh/id_ed25519_github_business_plan -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new -p 443'
git push ssh://git@ssh.github.com:443/Roco211/Business.git codex/ai-native-saas-rewrite:codex/ai-native-saas-rewrite
```

Expected: 形成一笔只聚焦 receipt clarification replay 顺序和恢复语义的提交，并同步到远端分支。
