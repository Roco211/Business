# AI 原生 SaaS V2 媒体与模型调用基础实施计划

> **给智能执行代理（agentic workers）：** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 按任务逐项实现本计划。步骤使用 checkbox（`- [ ]`）语法跟踪。

**Goal:** 建立 V2 `media_ai_platform` 的第一块可运行基础：在显式 `tenant / shop / context` 下登记媒体资产，并记录 ASR / OCR / Vision / LLM 等模型调用日志。

**Architecture:** 本切片沿用 `/api/v2` 新边界，不复用旧 `/api/v1/media-uploads` 的 `shop = tenant` 语义。`media_asset` 与 `model_call_log` 都直接携带 `tenant_id` 与 `shop_id`，API 必须要求 `Authorization + X-Context-Token`；本阶段只登记媒体与模型调用事实，不让 AI 结果直接修改库存真相。

**Tech Stack:** Python、FastAPI、Pydantic、SQLAlchemy、Alembic、pytest、对象存储 provider 抽象

---

## 文件结构

- 新增 `backend/app/models/v2_media_ai.py`：定义 `V2MediaAsset` 与 `V2ModelCallLog`。
- 修改 `backend/app/models/__init__.py`：导出新增 V2 media AI 模型。
- 新增 `backend/alembic/versions/20260419_02_create_v2_media_ai_foundation.py`：创建媒体资产与模型调用日志表。
- 新增 `backend/app/services/v2_media_assets.py`：提供媒体上传登记、完成校验与 ready 查询。
- 新增 `backend/app/services/v2_model_call_logs.py`：提供模型调用日志追加 helper。
- 新增 `backend/app/contracts/v2/media_ai.py`：定义 V2 media API 请求与响应合同。
- 新增 `backend/app/api/v2/routes/media_ai.py`：挂载 `/api/v2/media-assets`。
- 修改 `backend/app/api/v2/router.py`：纳入 media AI router。
- 修改 `backend/tests/test_alembic_bootstrap.py`：断言新增表存在。
- 新增 `backend/tests/test_v2_media_ai_platform.py`：覆盖 schema、service 与 API。

### Task 1: V2 media AI schema

**Files:**
- Create: `backend/app/models/v2_media_ai.py`
- Modify: `backend/app/models/__init__.py`
- Create: `backend/alembic/versions/20260419_02_create_v2_media_ai_foundation.py`
- Modify: `backend/tests/test_alembic_bootstrap.py`
- Test: `backend/tests/test_v2_media_ai_platform.py`

- [x] **Step 1: 写失败测试，固定 media asset 与 model call log 都直接持有 tenant/shop/context 边界**

```python
def test_v2_media_ai_schema_persists_context_boundaries(db_session) -> None:
    from app.models import V2MediaAsset, V2ModelCallLog

    _seed_v2_media_context(db_session)
    now = _utc_now_naive()
    asset = V2MediaAsset(
        media_asset_id="vmedia_001",
        tenant_id="tenant_a",
        shop_id="shop_a1",
        context_session_id="vctx_001",
        uploaded_by_account_id="acct_001",
        media_type="image",
        file_name="receipt.jpg",
        content_type="image/jpeg",
        size_bytes=2048,
        storage_provider="mock",
        object_key="tenants/tenant_a/shops/shop_a1/media/vmedia_001/receipt.jpg",
        upload_url="storage-ref://tenants/tenant_a/shops/shop_a1/media/vmedia_001/receipt.jpg",
        public_url="https://cdn.example/vmedia_001",
        status="uploaded",
        checksum_sha256="abc123",
        metadata_json={"source": "test"},
        uploaded_at=now,
        created_at=now,
        updated_at=now,
    )
    log = V2ModelCallLog(
        model_call_log_id="vcall_001",
        tenant_id="tenant_a",
        shop_id="shop_a1",
        context_session_id="vctx_001",
        requested_by_account_id="acct_001",
        media_asset_id="vmedia_001",
        task_run_id=None,
        conversation_session_id=None,
        provider_type="vision",
        provider_key="mock",
        model_name="mock-vision",
        operation_type="receipt.extract",
        status="completed",
        request_payload={"media_asset_id": "vmedia_001"},
        response_payload={"items": []},
        error_code=None,
        latency_ms=12,
        cost_micros=0,
        started_at=now,
        completed_at=now,
        created_at=now,
    )
    db_session.add_all([asset, log])
    db_session.commit()

    assert db_session.get(V2MediaAsset, "vmedia_001").tenant_id == "tenant_a"
    assert db_session.get(V2ModelCallLog, "vcall_001").shop_id == "shop_a1"
```

- [x] **Step 2: 运行 schema 测试，确认当前因模型缺失而红灯**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_media_ai_platform.py::test_v2_media_ai_schema_persists_context_boundaries -q
```

Expected:

- `ImportError`、`AttributeError` 或 `OperationalError: no such table`。

- [x] **Step 3: 新增 ORM 与迁移**

关键字段必须包含：

- `tenant_id`
- `shop_id`
- `context_session_id`
- `uploaded_by_account_id` / `requested_by_account_id`
- `media_asset_id`
- provider / model / operation / status
- request / response / error / latency / cost

- [x] **Step 4: 导出模型并补迁移断言**

在 `backend/app/models/__init__.py` 导出 `V2MediaAsset` 与 `V2ModelCallLog`。

在 `backend/tests/test_alembic_bootstrap.py` 中断言：

```python
assert "v2_media_assets" in table_names
assert "v2_model_call_logs" in table_names
```

- [x] **Step 5: 重跑 schema 与迁移测试**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_media_ai_platform.py::test_v2_media_ai_schema_persists_context_boundaries backend/tests/test_alembic_bootstrap.py -q
```

Expected:

- 全部通过。

### Task 2: V2 media asset service

**Files:**
- Create: `backend/app/services/v2_media_assets.py`
- Test: `backend/tests/test_v2_media_ai_platform.py`

- [x] **Step 1: 写失败测试，确认创建媒体资产使用 tenant/shop/context 并生成 tenant-first 对象 key**

```python
def test_create_v2_media_asset_upload_persists_pending_asset_with_context(db_session) -> None:
    storage = _StubObjectStorage()
    _seed_v2_media_context(db_session)

    result = create_v2_media_asset_upload(
        db_session,
        tenant_id="tenant_a",
        shop_id="shop_a1",
        context_session_id="vctx_001",
        uploaded_by_account_id="acct_001",
        media_type="image",
        file_name="receipt.jpg",
        content_type="image/jpeg",
        size_bytes=2048,
        object_storage=storage,
    )

    asset = db_session.get(V2MediaAsset, result.media_asset_id)
    assert asset.tenant_id == "tenant_a"
    assert asset.shop_id == "shop_a1"
    assert asset.status == "pending"
    assert asset.object_key.startswith("tenants/tenant_a/shops/shop_a1/media/")
```

- [x] **Step 2: 运行 service 测试，确认红灯**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_media_ai_platform.py::test_create_v2_media_asset_upload_persists_pending_asset_with_context -q
```

- [x] **Step 3: 实现最小 service**

实现：

- `create_v2_media_asset_upload(...)`
- `mark_v2_media_asset_uploaded(...)`
- `get_ready_v2_media_asset(...)`
- `derive_v2_media_object_key(...)`

- [x] **Step 4: 写并运行完成上传测试**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_media_ai_platform.py -k "media_asset" -q
```

Expected:

- 媒体资产相关测试通过。

### Task 3: V2 model call log service

**Files:**
- Create: `backend/app/services/v2_model_call_logs.py`
- Test: `backend/tests/test_v2_media_ai_platform.py`

- [x] **Step 1: 写失败测试，确认模型调用日志只能在显式上下文下追加**

```python
def test_append_v2_model_call_log_persists_provider_observability(db_session) -> None:
    _seed_v2_uploaded_media_asset(db_session)

    log = append_v2_model_call_log(
        db_session,
        tenant_id="tenant_a",
        shop_id="shop_a1",
        context_session_id="vctx_001",
        requested_by_account_id="acct_001",
        media_asset_id="vmedia_ready",
        provider_type="ocr",
        provider_key="mock",
        model_name="mock-ocr",
        operation_type="receipt.extract",
        status="completed",
        request_payload={"media_asset_id": "vmedia_ready"},
        response_payload={"total": 18.5},
        error_code=None,
        latency_ms=25,
        cost_micros=0,
    )

    assert log.tenant_id == "tenant_a"
    assert log.shop_id == "shop_a1"
    assert log.status == "completed"
```

- [x] **Step 2: 实现日志 helper 并重跑测试**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_media_ai_platform.py -k "model_call" -q
```

### Task 4: V2 media asset API

**Files:**
- Create: `backend/app/contracts/v2/media_ai.py`
- Create: `backend/app/api/v2/routes/media_ai.py`
- Modify: `backend/app/api/v2/router.py`
- Modify: `project_docs/generated/openapi-v1.json`
- Test: `backend/tests/test_v2_media_ai_platform.py`

- [x] **Step 1: 写失败测试，确认 `/api/v2/media-assets` 要求 Authorization 与 X-Context-Token**

```python
def test_v2_create_media_asset_requires_context(client, db_session) -> None:
    token, _ = _seed_v2_media_login_and_context(client, db_session)

    response = client.post(
        "/api/v2/media-assets",
        headers={"Authorization": f"Bearer {token}"},
        json={"media_type": "image", "file_name": "receipt.jpg", "content_type": "image/jpeg", "size_bytes": 2048},
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "context_required"
```

- [x] **Step 2: 写失败测试，确认 create / complete API 都按当前 context 落库**

```python
def test_v2_create_and_complete_media_asset_uses_current_context(client, db_session) -> None:
    token, context_token = _seed_v2_media_login_and_context(client, db_session)

    create_response = client.post(
        "/api/v2/media-assets",
        headers={"Authorization": f"Bearer {token}", "X-Context-Token": context_token},
        json={"media_type": "image", "file_name": "receipt.jpg", "content_type": "image/jpeg", "size_bytes": 13},
    )
    media_asset_id = create_response.json()["data"]["media_asset_id"]
    complete_response = client.post(
        f"/api/v2/media-assets/{media_asset_id}/complete",
        headers={"Authorization": f"Bearer {token}", "X-Context-Token": context_token},
        json={"checksum_sha256": "abc123", "size_bytes": 13},
    )

    assert create_response.status_code == 201
    assert complete_response.status_code == 200
```

- [x] **Step 3: 实现合同与路由**

错误映射：

- unsupported media type / invalid payload -> `422 validation_error`
- asset not found -> `404 media_asset_not_found`
- not ready / verification failure -> `409 media_asset_conflict`
- storage unavailable -> `503 media_storage_unavailable`

- [x] **Step 4: 刷新 OpenAPI 并运行目标测试**

Run:

```powershell
python backend/scripts/generate_openapi_snapshot.py
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_v2_media_ai_platform.py backend/tests/test_openapi_contract_snapshot.py -q
```

### Task 5: 阶段验收

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

- [ ] **Step 3: 完整 backend 测试**

说明：根据当前协作约定，此步骤不是每轮必跑项；仅在需要做全量回归时执行，并在执行后单独记录结果。

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests -q
```

- [ ] **Step 4: 检查 git 状态并提交**

Run:

```powershell
git status --short
git add backend/app/models/v2_media_ai.py backend/app/services/v2_media_assets.py backend/app/services/v2_model_call_logs.py backend/app/contracts/v2/media_ai.py backend/app/api/v2/routes/media_ai.py backend/app/api/v2/router.py backend/alembic/versions/20260419_02_create_v2_media_ai_foundation.py backend/tests/test_v2_media_ai_platform.py backend/tests/test_alembic_bootstrap.py project_docs/generated/openapi-v1.json docs/superpowers/plans/2026-04-19-ai-native-saas-v2-media-ai-foundation.md
git commit -m "feat: add v2 media ai foundation"
```
