# AI 原生 SaaS V2 文档抽取基础实施计划

> **给智能执行代理（agentic workers）：** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 按任务逐项实现本计划。步骤使用 checkbox（`- [ ]`）语法跟踪。

**Goal:** 在 V2 `media_ai_platform` 中补齐 `document` 这一层，让已完成上传的 `media_asset` 能在显式 `tenant / shop / context` 下沉淀为可查询的结构化文档结果。

**Architecture:** 沿用现有 `/api/v2`、`Authorization + X-Context-Token`、显式上下文校验和 tenant-first 数据边界。`document` 只保存“媒体抽取结果事实”，不直接写库存等业务真相；若有 AI 调用来源，只通过可选 `model_call_log_id` 建立可追溯关联。

**Tech Stack:** Python、FastAPI、Pydantic、SQLAlchemy、Alembic、pytest、OpenAPI snapshot

---

## 文件结构

- 修改 `backend/app/models/v2_media_ai.py`：新增 `V2Document` ORM。
- 修改 `backend/app/models/__init__.py`：导出 `V2Document`。
- 新增 `backend/alembic/versions/20260419_03_create_v2_documents.py`：创建 `v2_documents` 表。
- 新增 `backend/app/services/v2_documents.py`：提供 document 创建与读取能力。
- 修改 `backend/app/contracts/v2/media_ai.py`：新增 document 请求/响应合同。
- 修改 `backend/app/api/v2/routes/media_ai.py`：新增 `/api/v2/documents` create/get。
- 修改 `backend/tests/test_v2_media_ai_platform.py`：覆盖 schema、service、API。
- 修改 `backend/tests/test_alembic_bootstrap.py`：断言新表存在。
- 修改 `project_docs/generated/openapi-v1.json`：刷新 V2 文档接口快照。

### Task 1: V2 document schema

**Files:**
- Modify: `backend/app/models/v2_media_ai.py`
- Modify: `backend/app/models/__init__.py`
- Create: `backend/alembic/versions/20260419_03_create_v2_documents.py`
- Modify: `backend/tests/test_alembic_bootstrap.py`
- Test: `backend/tests/test_v2_media_ai_platform.py`

- [x] **Step 1: 写失败测试，固定 document 直接持有 tenant/shop/context/media 边界**

```python
def test_v2_document_schema_persists_context_boundaries(db_session) -> None:
    from app.models import V2Document

    _seed_v2_media_context(db_session)
    uploaded_asset_id = _seed_v2_uploaded_media_asset(db_session)
    now = _utc_now_naive()
    document = V2Document(
        document_id="vdoc_001",
        tenant_id="tenant_a",
        shop_id="shop_a1",
        context_session_id="vctx_001",
        media_asset_id=uploaded_asset_id,
        model_call_log_id=None,
        created_by_account_id="acct_001",
        document_type="purchase-receipt",
        extraction_status="completed",
        extracted_fields={"total_amount": 18.5},
        confidence_summary={"overall": 0.91},
        created_at=now,
        updated_at=now,
    )
    db_session.add(document)
    db_session.commit()

    persisted = db_session.get(V2Document, "vdoc_001")
    assert persisted is not None
    assert persisted.tenant_id == "tenant_a"
    assert persisted.shop_id == "shop_a1"
    assert persisted.media_asset_id == uploaded_asset_id
```

- [x] **Step 2: 运行 schema 测试，确认当前因模型/表缺失而红灯**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_media_ai_platform.py::test_v2_document_schema_persists_context_boundaries -q
```

Expected:

- `ImportError`、`AttributeError` 或 `OperationalError: no such table`。

- [x] **Step 3: 新增 ORM 与迁移**

关键字段必须包含：

- `document_id`
- `tenant_id`
- `shop_id`
- `context_session_id`
- `media_asset_id`
- `model_call_log_id`
- `created_by_account_id`
- `document_type`
- `extraction_status`
- `extracted_fields`
- `confidence_summary`
- `created_at`
- `updated_at`

- [x] **Step 4: 导出模型并补迁移断言**

在 `backend/app/models/__init__.py` 导出 `V2Document`。

在 `backend/tests/test_alembic_bootstrap.py` 中断言：

```python
assert "v2_documents" in table_names
assert {"document_id", "tenant_id", "shop_id", "media_asset_id", "document_type"} <= {
    column["name"] for column in inspector.get_columns("v2_documents")
}
```

- [x] **Step 5: 重跑 schema 与迁移测试**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_media_ai_platform.py::test_v2_document_schema_persists_context_boundaries backend/tests/test_alembic_bootstrap.py -q
```

Expected:

- 全部通过。

### Task 2: V2 document service

**Files:**
- Create: `backend/app/services/v2_documents.py`
- Modify: `backend/tests/test_v2_media_ai_platform.py`

- [x] **Step 1: 写失败测试，确认 document 创建会绑定 ready media asset 与当前上下文**

```python
def test_create_v2_document_persists_completed_receipt_result(db_session) -> None:
    from app.services.v2_documents import create_v2_document

    _seed_v2_media_context(db_session)
    uploaded_asset_id = _seed_v2_uploaded_media_asset(db_session)

    created = create_v2_document(
        db_session,
        tenant_id="tenant_a",
        shop_id="shop_a1",
        context_session_id="vctx_001",
        created_by_account_id="acct_001",
        media_asset_id=uploaded_asset_id,
        model_call_log_id=None,
        document_type="purchase-receipt",
        extraction_status="completed",
        extracted_fields={"total_amount": 18.5, "items": []},
        confidence_summary={"overall": 0.91},
    )

    assert created.document_id.startswith("vdoc_")
    assert created.media_asset_id == uploaded_asset_id
    assert created.document_type == "purchase-receipt"
    assert created.extraction_status == "completed"
```

- [x] **Step 2: 写失败测试，确认 get 只能读取当前 tenant/shop 下的 document**

```python
def test_get_v2_document_requires_current_context_scope(db_session) -> None:
    from app.services.v2_documents import create_v2_document, get_v2_document

    _seed_v2_media_context(db_session)
    uploaded_asset_id = _seed_v2_uploaded_media_asset(db_session)
    created = create_v2_document(
        db_session,
        tenant_id="tenant_a",
        shop_id="shop_a1",
        context_session_id="vctx_001",
        created_by_account_id="acct_001",
        media_asset_id=uploaded_asset_id,
        model_call_log_id=None,
        document_type="purchase-receipt",
        extraction_status="completed",
        extracted_fields={"total_amount": 18.5},
        confidence_summary={"overall": 0.91},
    )

    loaded = get_v2_document(
        db_session,
        tenant_id="tenant_a",
        shop_id="shop_a1",
        document_id=created.document_id,
    )

    assert loaded.document_id == created.document_id
    assert loaded.media_asset_id == uploaded_asset_id
```

- [x] **Step 3: 运行 service 测试，确认红灯**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_media_ai_platform.py -k "v2_document" -q
```

- [x] **Step 4: 实现最小 service**

实现：

- `create_v2_document(...)`
- `get_v2_document(...)`
- `V2DocumentValidationError`
- `V2DocumentConflictError`

关键规则：

- 仅支持当前切片所需的 `purchase-receipt`
- 仅允许 `pending` / `completed` / `failed` 三种 `extraction_status`
- 只能基于同 `tenant_id + shop_id` 下 `status=uploaded` 的 `V2MediaAsset` 创建 document
- 若传入 `model_call_log_id`，必须属于同上下文，且其 `media_asset_id` 与 document 一致

- [x] **Step 5: 重跑 service 测试**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_media_ai_platform.py -k "v2_document" -q
```

Expected:

- document service 相关测试通过。

### Task 3: V2 document API

**Files:**
- Modify: `backend/app/contracts/v2/media_ai.py`
- Modify: `backend/app/api/v2/routes/media_ai.py`
- Modify: `backend/tests/test_v2_media_ai_platform.py`
- Modify: `project_docs/generated/openapi-v1.json`

- [x] **Step 1: 写失败测试，确认 `/api/v2/documents` 仍要求 Authorization 与 X-Context-Token**

```python
def test_v2_create_document_requires_context(client, db_session) -> None:
    token, _ = _seed_v2_media_login_and_context(client, db_session)

    response = client.post(
        "/api/v2/documents",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "media_asset_id": "vmedia_missing",
            "document_type": "purchase-receipt",
            "extraction_status": "completed",
            "extracted_fields": {"total_amount": 18.5},
            "confidence_summary": {"overall": 0.91},
        },
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "context_required"
```

- [x] **Step 2: 写失败测试，确认 create/get API 都按当前 context 访问 document**

```python
def test_v2_create_and_get_document_uses_current_context(client, db_session, monkeypatch) -> None:
    token, context_token = _seed_v2_media_login_and_context(client, db_session)
    media_asset_id = _seed_v2_uploaded_media_asset_via_api(client, token, context_token, monkeypatch)

    create_response = client.post(
        "/api/v2/documents",
        headers={"Authorization": f"Bearer {token}", "X-Context-Token": context_token},
        json={
            "media_asset_id": media_asset_id,
            "document_type": "purchase-receipt",
            "extraction_status": "completed",
            "extracted_fields": {"total_amount": 18.5, "items": []},
            "confidence_summary": {"overall": 0.91},
        },
    )
    document_id = create_response.json()["data"]["document_id"]
    detail_response = client.get(
        f"/api/v2/documents/{document_id}",
        headers={"Authorization": f"Bearer {token}", "X-Context-Token": context_token},
    )

    assert create_response.status_code == 201
    assert detail_response.status_code == 200
    assert detail_response.json()["data"]["document_id"] == document_id
```

- [x] **Step 3: 实现合同与路由**

错误映射：

- invalid payload / unsupported document type -> `422 validation_error`
- media asset / model call log / document not found -> `404 ..._not_found`
- media asset not ready / model call log mismatch -> `409 document_conflict`

- [x] **Step 4: 刷新 OpenAPI 并运行目标测试**

Run:

```powershell
python backend/scripts/generate_openapi_snapshot.py
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_media_ai_platform.py backend/tests/test_openapi_contract_snapshot.py -q
```

### Task 4: 阶段验收

**Files:**
- Verify: `backend/tests/test_v2_media_ai_platform.py`
- Verify: `backend/tests/test_alembic_bootstrap.py`
- Verify: `backend/tests/test_openapi_contract_snapshot.py`

- [x] **Step 1: 运行本切片目标测试**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_media_ai_platform.py backend/tests/test_alembic_bootstrap.py backend/tests/test_openapi_contract_snapshot.py -q
```

- [x] **Step 2: 运行相关 V2 回归**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_identity_context.py backend/tests/test_v2_conversation_runtime.py backend/tests/test_v2_clarification_confirmation.py backend/tests/test_v2_media_ai_platform.py -q
```

- [x] **Step 3: 检查 git 状态并提交**

Run:

```powershell
git status --short
git add backend/app/models/v2_media_ai.py backend/app/models/__init__.py backend/alembic/versions/20260419_03_create_v2_documents.py backend/app/services/v2_documents.py backend/app/contracts/v2/media_ai.py backend/app/api/v2/routes/media_ai.py backend/tests/test_v2_media_ai_platform.py backend/tests/test_alembic_bootstrap.py project_docs/generated/openapi-v1.json docs/superpowers/plans/2026-04-19-ai-native-saas-v2-document-foundation.md
git commit -m "feat: add v2 document foundation"
```

说明：按当前协作约定，本计划默认只跑与改动范围直接相关的 backend 测试；若后续需要全量 backend 回归，再单独补跑并记录结果。
