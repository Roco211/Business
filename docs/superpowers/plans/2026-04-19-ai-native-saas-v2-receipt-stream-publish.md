# AI 原生 SaaS V2 票据抽取实时流推送实施计划

> **给智能执行代理（agentic workers）：** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 按任务逐项实现本计划。步骤使用 checkbox（`- [ ]`）语法跟踪。

**Goal:** 让 receipt extraction API 在生成 draft、confirmation、system result 后，也能像 conversation 路由一样把新增 session stream events 实时推给 websocket 订阅端。

**Architecture:** 不改变 receipt extraction 已经落库的 durable events，只补 route 层 best-effort publish。实现复用现有 session stream publish 模式：在 mutation 前先解析当前 `after_seq`，mutation 成功后按 session_id 把新增 events fanout 给 `SessionStreamManager`。这样数据库仍是唯一真相源，websocket 只消费已提交的 durable projection。

**Tech Stack:** Python、FastAPI、SQLAlchemy、pytest、现有 V2 websocket/session stream 基础设施

---

## 文件结构

- 新建 `backend/app/api/v2/session_stream_publish.py`：抽出 route 可复用的 stream cursor / best-effort publish helper。
- 修改 `backend/app/api/v2/routes/conversation.py`：切到共享 publish helper，保持行为不变。
- 修改 `backend/app/api/v2/routes/media_ai.py`：在 receipt extraction 成功后补 session stream publish。
- 修改 `backend/tests/test_v2_session_stream_ws.py`：补 websocket 红绿测试。

### Task 1: 用 websocket 红灯固定 receipt extraction 的 live publish 缺口

**Files:**
- Modify: `backend/tests/test_v2_session_stream_ws.py`

- [x] **Step 1: 写失败测试，固定 receipt extraction 成功后 websocket 会立即收到新增 runtime events**

测试目标：
- 先建立 `receipt` session、消息和 `task_run_id`。
- websocket 订阅建立后调用 `/api/v2/documents/receipt-extractions`。
- 不等 keepalive，直接收到新增 events。
- 事件序列至少包含：
  - `task.updated` with `status == "drafted"`
  - `task.updated` with `status == "awaiting_confirmation"`
  - `message.created` with `message_kind == "system_result"`

- [x] **Step 2: 运行红灯测试**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_session_stream_ws.py::test_v2_session_stream_ws_pushes_receipt_extraction_progression_without_waiting_for_keepalive -q
```

Expected: FAIL，因为当前 `media_ai` 路由还没有 publish 新增 stream events。

### Task 2: 抽出共享 publish helper 并接到 media_ai route

**Files:**
- Create: `backend/app/api/v2/session_stream_publish.py`
- Modify: `backend/app/api/v2/routes/conversation.py`
- Modify: `backend/app/api/v2/routes/media_ai.py`

- [x] **Step 1: 抽出共享 helper**

至少包含：
- `publish_v2_stream_events_best_effort(...)`
- `resolve_v2_session_cursor(...)`
- `resolve_v2_task_run_session_cursor(...)`

- [x] **Step 2: conversation route 切到共享 helper**

要求：
- 不改变现有 conversation API 行为。
- 只替换 helper 来源，保证回归风险最小。

- [x] **Step 3: media_ai route 在 receipt extraction 成功后补 publish**

实现要点：
- 只有传入 `task_run_id` 且能解析到 session cursor 时才 publish。
- mutation 前先拿 `after_seq`。
- mutation 成功后用共享 helper fanout 新增 events。
- 不因为 publish 失败影响 API 成功返回。

- [x] **Step 4: 重跑目标 websocket 测试**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_session_stream_ws.py::test_v2_session_stream_ws_pushes_receipt_extraction_progression_without_waiting_for_keepalive -q
```

Expected: PASS。

### Task 3: 局部回归与提交

**Files:**
- Verify: `backend/tests/test_v2_session_stream_ws.py`
- Verify: `backend/tests/test_v2_session_stream_api.py`
- Verify: `backend/tests/test_v2_media_ai_platform.py`

- [x] **Step 1: 运行本切片相关测试**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_session_stream_ws.py backend/tests/test_v2_session_stream_api.py backend/tests/test_v2_media_ai_platform.py -q
```

- [ ] **Step 2: 检查 diff 与工作区状态**

Run:

```powershell
git diff --check
git status --short
```

- [ ] **Step 3: 提交并推送**

Run:

```powershell
git add docs/superpowers/plans/2026-04-19-ai-native-saas-v2-receipt-stream-publish.md backend/app/api/v2/session_stream_publish.py backend/app/api/v2/routes/conversation.py backend/app/api/v2/routes/media_ai.py backend/tests/test_v2_session_stream_ws.py
git commit -m "feat: publish v2 receipt stream progression"
git push ssh://git@ssh.github.com:443/Roco211/Business.git codex/ai-native-saas-rewrite:codex/ai-native-saas-rewrite
```
