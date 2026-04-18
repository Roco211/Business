# AI 原生 SaaS V2 票据抽取任务关联实施计划

> **给智能执行代理（agentic workers）：** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 按任务逐项实现本计划。步骤使用 checkbox（`- [ ]`）语法跟踪。

**Goal:** 让 V2 receipt document extraction 在需要时显式关联 `task_run_id` 与 `conversation_session_id`，把 `model_call_log` 正式挂回 runtime 上下文。

**Architecture:** 不改变 receipt extraction 的主路径，只给 request/service 增加可选的 task/session 关联参数，并在同一 `tenant / shop` 边界下校验它们。成功后把这两个 id 落到 `V2ModelCallLog`，为后续 runtime、审计和回放链路复用。

**Tech Stack:** Python、FastAPI、SQLAlchemy、pytest、现有 V2 conversation/media_ai 服务

---

## 文件结构

- 修改 `backend/app/services/v2_receipt_documents.py`：支持 task/session 关联校验与落库。
- 修改 `backend/app/contracts/v2/media_ai.py`：扩展 extraction request。
- 修改 `backend/app/api/v2/routes/media_ai.py`：透传可选 task/session 参数。
- 修改 `backend/tests/test_v2_media_ai_platform.py`：补 service/API 测试。
- 修改 `project_docs/generated/openapi-v1.json`：刷新 OpenAPI snapshot。

### Task 1: Service task/session affinity

**Files:**
- Modify: `backend/app/services/v2_receipt_documents.py`
- Modify: `backend/tests/test_v2_media_ai_platform.py`

- [x] **Step 1: 写失败测试，固定 service 会把 model_call_log 挂到指定 task/session**
- [x] **Step 2: 运行红灯测试**
- [x] **Step 3: 实现 task/session 校验与自动补 session_id**
- [x] **Step 4: 重跑 service 测试**

### Task 2: API task/session affinity

**Files:**
- Modify: `backend/app/contracts/v2/media_ai.py`
- Modify: `backend/app/api/v2/routes/media_ai.py`
- Modify: `backend/tests/test_v2_media_ai_platform.py`
- Modify: `project_docs/generated/openapi-v1.json`

- [x] **Step 1: 写失败测试，固定 API 接收 task_run_id 与 conversation_session_id 并透传**
- [x] **Step 2: 实现 request 合同与路由透传**
- [x] **Step 3: 刷新 OpenAPI 并运行目标测试**

### Task 3: 阶段验收

**Files:**
- Verify: `backend/tests/test_v2_media_ai_platform.py`
- Verify: `backend/tests/test_openapi_contract_snapshot.py`
- Verify: `backend/tests/test_v2_identity_context.py`
- Verify: `backend/tests/test_v2_conversation_runtime.py`
- Verify: `backend/tests/test_v2_clarification_confirmation.py`

- [x] **Step 1: 运行本切片相关测试**
- [x] **Step 2: 运行相邻 V2 回归**
- [x] **Step 3: 检查 git 状态并提交**
