# AI 原生 SaaS V2 票据澄清 WebSocket 重放顺序实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 receipt clarification 派生提交流程补一条 websocket `after_seq` 重连回放测试，确保客户端从 `system_result` 之后恢复时，先收到 `task.updated(committed)`，再收到 `inventory.updated`。

**Architecture:** 本切片不改 websocket 路由或 connection manager，只给现有 durable stream replay 语义加回归保护。测试先用 HTTP replay API 读取真实 `seq`，再以同一 `after_seq` 建 websocket，验证重放顺序与 provenance 字段都稳定存在。

**Tech Stack:** Python、FastAPI TestClient、Starlette WebSocket、pytest、现有 V2 session stream / outbox dispatch 服务

---

## 文件结构

- 修改 `backend/tests/test_v2_session_stream_ws.py`：新增 receipt clarification `after_seq` websocket 重放顺序测试。
- 不修改生产代码：若测试首跑通过，说明当前 websocket replay 语义已经满足顺序要求。

### Task 1: 固定 websocket `after_seq` 的 clarification-derived 重放顺序

**Files:**
- Modify: `backend/tests/test_v2_session_stream_ws.py`
- Test: `backend/tests/test_v2_session_stream_ws.py::test_v2_session_stream_ws_replays_receipt_clarification_suffix_after_system_result_seq`

- [x] **Step 1: 先取 durable `seq` 再做 websocket 回放断言**

```python
events = replay_response.json()["data"]["events"]
system_result_event = ...
committed_event = ...
inventory_event = ...

with client.websocket_connect(
    f"/api/v2/ws/sessions/{session_id}?token={token}&context_token={context_token}&after_seq={system_result_event['seq']}"
) as websocket:
    ready_event = websocket.receive_json()
    replayed_committed_event = websocket.receive_json()
    replayed_inventory_event = websocket.receive_json()

assert replayed_committed_event["seq"] == committed_event["seq"]
assert replayed_inventory_event["seq"] == inventory_event["seq"]
assert replayed_inventory_event["data"]["source_document_id"] == document_id
```

- [x] **Step 2: 运行目标 websocket 测试**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_session_stream_ws.py::test_v2_session_stream_ws_replays_receipt_clarification_suffix_after_system_result_seq -q
```

Expected: 若 websocket `after_seq` 回放丢事件或顺序错误，则在 `seq` / `event_type` / provenance 断言处失败；若首跑即 PASS，则说明生产实现已满足要求。本次执行首跑即 PASS，未修改生产代码。

### Task 2: 局部验证与提交

**Files:**
- Verify: `backend/tests/test_v2_session_stream_ws.py`
- Verify: `docs/superpowers/plans/2026-04-19-ai-native-saas-v2-receipt-clarification-ws-replay-ordering.md`

- [x] **Step 1: 运行相关 websocket 切片**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_session_stream_ws.py::test_v2_session_stream_ws_replays_receipt_clarification_suffix_after_system_result_seq -q
```

Expected: 单条 websocket 回放测试通过。

- [ ] **Step 2: 检查 diff 与工作区状态**

Run:

```powershell
git diff --check
git status --short --branch --untracked-files=no
```

Expected: 无格式错误；变更只包含本次 plan 文档与 websocket 测试。

- [ ] **Step 3: 提交并推送**

Run:

```powershell
git add docs/superpowers/plans/2026-04-19-ai-native-saas-v2-receipt-clarification-ws-replay-ordering.md backend/tests/test_v2_session_stream_ws.py
git commit -m "test: cover receipt clarification websocket replay ordering"
$env:GIT_SSH_COMMAND='ssh -i ~/.ssh/id_ed25519_github_business_plan -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new -p 443'
git push ssh://git@ssh.github.com:443/Roco211/Business.git codex/ai-native-saas-rewrite:codex/ai-native-saas-rewrite
```

Expected: 形成一笔只聚焦 receipt clarification websocket 重连回放顺序的提交，并同步到远端分支。
