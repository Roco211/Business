# AI 原生 SaaS V2 模型调用可观测性补强实施计划

> **给智能执行代理（agentic workers）：** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 按任务逐项实现本计划。步骤使用 checkbox（`- [ ]`）语法跟踪。

**Goal:** 为 V2 `model_call_log` 补齐 prompt/schema/confidence/fallback 等可观测元数据，让后续 OCR / Vision / LLM 调用可以按 spec 追踪模型行为。

**Architecture:** 本切片只增强 `media_ai_platform` 的日志真相，不改变业务写入路径。所有新增字段都继续显式挂在 `tenant / shop / context` 下，供后续 document extraction、runtime interpret 和评估链路复用。

**Tech Stack:** Python、SQLAlchemy、Alembic、pytest

---

## 文件结构

- 修改 `backend/app/models/v2_media_ai.py`：扩展 `V2ModelCallLog` 字段。
- 新增 `backend/alembic/versions/20260419_04_add_v2_model_call_log_observability_fields.py`：补列迁移。
- 修改 `backend/app/services/v2_model_call_logs.py`：扩展 helper 入参与落库逻辑。
- 修改 `backend/tests/test_v2_media_ai_platform.py`：补 observability 断言。
- 修改 `backend/tests/test_alembic_bootstrap.py`：补列断言。

### Task 1: 扩展 schema 与迁移

**Files:**
- Modify: `backend/app/models/v2_media_ai.py`
- Create: `backend/alembic/versions/20260419_04_add_v2_model_call_log_observability_fields.py`
- Modify: `backend/tests/test_alembic_bootstrap.py`
- Test: `backend/tests/test_v2_media_ai_platform.py`

- [x] **Step 1: 写失败测试，固定 model_call_log 持久化 prompt/schema/confidence/fallback**

```python
def test_append_v2_model_call_log_persists_observability_metadata(db_session) -> None:
    _seed_v2_media_context(db_session)
    uploaded_asset_id = _seed_v2_uploaded_media_asset(db_session)

    log = append_v2_model_call_log(
        db_session,
        tenant_id="tenant_a",
        shop_id="shop_a1",
        context_session_id="vctx_001",
        requested_by_account_id="acct_001",
        media_asset_id=uploaded_asset_id,
        task_run_id=None,
        conversation_session_id=None,
        provider_type="ocr",
        provider_key="mock",
        model_name="mock-ocr",
        operation_type="receipt.extract",
        status="completed",
        request_payload={"media_asset_id": uploaded_asset_id},
        response_payload={"total_amount": 18.5},
        error_code=None,
        latency_ms=25,
        cost_micros=0,
        prompt_version="receipt-extract@v1",
        schema_version="receipt.schema@v1",
        confidence_score=0.91,
        used_fallback=False,
    )

    assert log.prompt_version == "receipt-extract@v1"
    assert log.schema_version == "receipt.schema@v1"
    assert log.confidence_score == 0.91
    assert log.used_fallback is False
```

- [x] **Step 2: 运行红灯测试**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_media_ai_platform.py -k "observability_metadata" -q
```

- [x] **Step 3: 新增列与迁移**

新增字段：

- `prompt_version`
- `schema_version`
- `confidence_score`
- `used_fallback`

- [x] **Step 4: 更新 bootstrap 断言**

```python
assert {"prompt_version", "schema_version", "confidence_score", "used_fallback"} <= {
    column["name"] for column in inspector.get_columns("v2_model_call_logs")
}
```

- [x] **Step 5: 重跑 schema/迁移测试**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_media_ai_platform.py -k "observability_metadata" backend/tests/test_alembic_bootstrap.py -q
```

### Task 2: 扩展 helper 并验收

**Files:**
- Modify: `backend/app/services/v2_model_call_logs.py`
- Modify: `backend/tests/test_v2_media_ai_platform.py`

- [x] **Step 1: 扩展 helper 签名与最小实现**

规则：

- `prompt_version` / `schema_version` 允许为空，但传入时会去空白
- `confidence_score` 允许为空；若存在，范围必须在 `0` 到 `1`
- `used_fallback` 默认 `False`

- [x] **Step 2: 重跑 media AI 相关测试**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_media_ai_platform.py backend/tests/test_alembic_bootstrap.py -q
```

- [x] **Step 3: 运行相邻 V2 回归**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_identity_context.py backend/tests/test_v2_conversation_runtime.py backend/tests/test_v2_clarification_confirmation.py backend/tests/test_v2_media_ai_platform.py -q
```

- [x] **Step 4: 检查 git 状态并提交**

Run:

```powershell
git status --short
git add backend/app/models/v2_media_ai.py backend/alembic/versions/20260419_04_add_v2_model_call_log_observability_fields.py backend/app/services/v2_model_call_logs.py backend/tests/test_v2_media_ai_platform.py backend/tests/test_alembic_bootstrap.py docs/superpowers/plans/2026-04-19-ai-native-saas-v2-model-call-observability.md
git commit -m "feat: enrich v2 model call observability"
```
