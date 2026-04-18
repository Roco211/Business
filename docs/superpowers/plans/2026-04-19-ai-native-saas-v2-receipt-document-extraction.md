# AI 原生 SaaS V2 票据文档抽取实施计划

> **给智能执行代理（agentic workers）：** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 按任务逐项实现本计划。步骤使用 checkbox（`- [ ]`）语法跟踪。

**Goal:** 打通 V2 `receipt-image media_asset -> OCR gateway -> model_call_log -> V2Document` 的抽取闭环，为后续 clarification / confirmation / tool commit 链路提供结构化票据文档事实。

**Architecture:** 本切片复用现有 `V2MediaAsset`、`V2Document`、`V2ModelCallLog`、`ocr_gateway` 能力，不让 AI 直接写库存真相。公开接口仍要求 `Authorization + X-Context-Token`，并通过专用 receipt extraction service 在同一 `tenant / shop / context` 下完成 ready media 校验、模型调用可观测记录和 document 创建。

**Tech Stack:** Python、FastAPI、Pydantic、SQLAlchemy、pytest、现有 OCR gateway/provider 抽象

---

## 文件结构

- 新增 `backend/app/services/v2_receipt_documents.py`：负责 receipt-image 到 document 的抽取编排。
- 修改 `backend/app/contracts/v2/media_ai.py`：新增 receipt extraction 请求合同。
- 修改 `backend/app/api/v2/routes/media_ai.py`：新增 `/api/v2/documents/receipt-extractions` 路由。
- 修改 `backend/tests/test_v2_media_ai_platform.py`：补 service 与 API 红绿测试。
- 修改 `project_docs/generated/openapi-v1.json`：刷新 OpenAPI snapshot。
- 修改 `docs/superpowers/plans/2026-04-19-ai-native-saas-v2-receipt-document-extraction.md`：按执行结果勾选。

### Task 1: Receipt extraction service

**Files:**
- Create: `backend/app/services/v2_receipt_documents.py`
- Modify: `backend/tests/test_v2_media_ai_platform.py`

- [x] **Step 1: 写失败测试，固定成功抽取会创建 document 与 model_call_log**

```python
def test_extract_v2_receipt_document_creates_document_and_model_call_log(db_session, monkeypatch) -> None:
    import app.services.v2_receipt_documents as receipt_documents_service

    _seed_v2_media_context(db_session)
    media_asset_id = _seed_v2_uploaded_media_asset(db_session)
    monkeypatch.setattr(
        receipt_documents_service,
        "get_default_ocr_gateway",
        lambda: _StubOcrGateway(),
    )

    document = receipt_documents_service.extract_v2_receipt_document(
        db_session,
        tenant_id="tenant_a",
        shop_id="shop_a1",
        context_session_id="vctx_001",
        requested_by_account_id="acct_001",
        media_asset_id=media_asset_id,
    )

    assert document.media_asset_id == media_asset_id
    assert document.document_type == "purchase-receipt"
    assert document.model_call_log_id is not None
```

- [x] **Step 2: 写失败测试，固定 provider 失败也会落 failed model_call_log**

```python
def test_extract_v2_receipt_document_persists_failed_model_call_log_on_provider_error(db_session, monkeypatch) -> None:
    import app.services.v2_receipt_documents as receipt_documents_service

    _seed_v2_media_context(db_session)
    media_asset_id = _seed_v2_uploaded_media_asset(db_session)
    monkeypatch.setattr(
        receipt_documents_service,
        "get_default_ocr_gateway",
        lambda: _StubOcrGateway(error=OcrProviderError("ocr_unavailable", "provider down", retryable=False)),
    )

    with pytest.raises(OcrProviderError):
        receipt_documents_service.extract_v2_receipt_document(
            db_session,
            tenant_id="tenant_a",
            shop_id="shop_a1",
            context_session_id="vctx_001",
            requested_by_account_id="acct_001",
            media_asset_id=media_asset_id,
        )
```

- [x] **Step 3: 运行 service 红灯测试**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_media_ai_platform.py -k "receipt_document" -q
```

- [x] **Step 4: 实现最小抽取 service**

实现：

- `extract_v2_receipt_document(...)`
- receipt-image ready media 校验
- OCR gateway 调用
- `V2ModelCallLog` 成功 / 失败可观测记录
- `V2Document` 创建

关键规则：

- 只接受 `media_type="receipt-image"` 且 `status="uploaded"` 的媒体
- 成功日志固定 `operation_type="document.receipt.extract"`
- `prompt_version` 固定为 `receipt-extract@v1`
- `schema_version` 固定为 `purchase-receipt@v1`
- `confidence_summary` 至少包含 `overall` 与 `low_confidence_fields`

- [x] **Step 5: 重跑 service 测试**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_media_ai_platform.py -k "receipt_document" -q
```

### Task 2: Receipt extraction API

**Files:**
- Modify: `backend/app/contracts/v2/media_ai.py`
- Modify: `backend/app/api/v2/routes/media_ai.py`
- Modify: `backend/tests/test_v2_media_ai_platform.py`
- Modify: `project_docs/generated/openapi-v1.json`

- [x] **Step 1: 写失败测试，确认 `/api/v2/documents/receipt-extractions` 仍要求上下文**

```python
def test_v2_extract_receipt_document_requires_context(client, db_session) -> None:
    token, context_token = _seed_v2_media_login_and_context(client, db_session)
    media_asset_id = _seed_v2_uploaded_media_asset(db_session, context_session_id=context_token)

    response = client.post(
        "/api/v2/documents/receipt-extractions",
        headers={"Authorization": f"Bearer {token}"},
        json={"media_asset_id": media_asset_id},
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "context_required"
```

- [x] **Step 2: 写失败测试，确认 extraction API 按当前 context 抽取并返回 document**

```python
def test_v2_extract_receipt_document_uses_current_context(client, db_session, monkeypatch) -> None:
    import app.services.v2_receipt_documents as receipt_documents_service

    token, context_token = _seed_v2_media_login_and_context(client, db_session)
    media_asset_id = _seed_v2_uploaded_media_asset(db_session, context_session_id=context_token)
    monkeypatch.setattr(receipt_documents_service, "get_default_ocr_gateway", lambda: _StubOcrGateway())

    response = client.post(
        "/api/v2/documents/receipt-extractions",
        headers={"Authorization": f"Bearer {token}", "X-Context-Token": context_token},
        json={"media_asset_id": media_asset_id},
    )

    assert response.status_code == 201
    assert response.json()["data"]["media_asset_id"] == media_asset_id
    assert response.json()["data"]["document_type"] == "purchase-receipt"
```

- [x] **Step 3: 实现路由与错误映射**

错误映射：

- media asset 不存在 -> `404 media_asset_not_found`
- media asset 未就绪 / 类型不匹配 -> `409 document_conflict`
- OCR provider 不可用 -> `503 ocr_*`

- [x] **Step 4: 刷新 OpenAPI 并运行目标测试**

Run:

```powershell
python backend/scripts/generate_openapi_snapshot.py
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_media_ai_platform.py backend/tests/test_openapi_contract_snapshot.py -q
```

### Task 3: 阶段验收

**Files:**
- Verify: `backend/tests/test_v2_media_ai_platform.py`
- Verify: `backend/tests/test_v2_identity_context.py`
- Verify: `backend/tests/test_v2_conversation_runtime.py`
- Verify: `backend/tests/test_v2_clarification_confirmation.py`

- [x] **Step 1: 运行本切片相关测试**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_media_ai_platform.py backend/tests/test_openapi_contract_snapshot.py -q
```

- [x] **Step 2: 运行相邻 V2 回归**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_identity_context.py backend/tests/test_v2_conversation_runtime.py backend/tests/test_v2_clarification_confirmation.py backend/tests/test_v2_media_ai_platform.py -q
```

- [x] **Step 3: 检查 git 状态并提交**

Run:

```powershell
git status --short
git add backend/app/services/v2_receipt_documents.py backend/app/contracts/v2/media_ai.py backend/app/api/v2/routes/media_ai.py backend/tests/test_v2_media_ai_platform.py project_docs/generated/openapi-v1.json docs/superpowers/plans/2026-04-19-ai-native-saas-v2-receipt-document-extraction.md
git commit -m "feat: add v2 receipt document extraction"
```

说明：按当前协作约定，此计划只要求跑与改动直接相关的 backend 测试；完整 backend 回归不作为每轮默认步骤。
