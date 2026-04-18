from datetime import UTC, datetime


def _utc_now_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _seed_v2_media_context(db_session) -> None:
    from app.models import V2Account, V2AuthSession, V2ContextSession, V2Shop, V2ShopAccess, V2Tenant, V2TenantMembership
    from app.services.v2_identity import hash_v2_password

    now = _utc_now_naive()
    password_salt = "22" * 16
    db_session.add(
        V2Account(
            account_id="acct_001",
            email="owner@example.com",
            display_name="Owner",
            password_hash=hash_v2_password("dev-password", password_salt),
            password_salt=password_salt,
            status="active",
            created_at=now,
            updated_at=now,
        )
    )
    db_session.add(
        V2Tenant(
            tenant_id="tenant_a",
            name="A 商家",
            slug="tenant-a",
            status="active",
            plan_code="trial",
            owner_account_id="acct_001",
            created_at=now,
            updated_at=now,
        )
    )
    db_session.add(
        V2TenantMembership(
            membership_id="mship_tenant_a",
            tenant_id="tenant_a",
            account_id="acct_001",
            role_key="owner",
            status="active",
            joined_at=now,
            updated_at=now,
        )
    )
    db_session.add(
        V2Shop(
            shop_id="shop_a1",
            tenant_id="tenant_a",
            code="a-1",
            name="A 一号店",
            locale="zh-CN",
            timezone="Asia/Shanghai",
            status="active",
            created_at=now,
            updated_at=now,
        )
    )
    db_session.add(
        V2ShopAccess(
            shop_access_id="access_shop_a1",
            tenant_id="tenant_a",
            shop_id="shop_a1",
            membership_id="mship_tenant_a",
            access_level="write",
            status="active",
            created_at=now,
        )
    )
    db_session.add(
        V2AuthSession(
            auth_session_id="vauth_001",
            account_id="acct_001",
            access_token_hash="token_hash",
            refresh_token_hash="refresh_hash",
            status="active",
            expires_at=now.replace(year=now.year + 1),
            revoked_at=None,
            last_seen_at=now,
            created_at=now,
        )
    )
    db_session.add(
        V2ContextSession(
            context_session_id="vctx_001",
            auth_session_id="vauth_001",
            account_id="acct_001",
            tenant_id="tenant_a",
            shop_id="shop_a1",
            membership_id="mship_tenant_a",
            permission_snapshot={"role_key": "owner", "permissions": ["inventory:write", "media:write"]},
            status="active",
            expires_at=now.replace(year=now.year + 1),
            created_at=now,
        )
    )
    db_session.commit()


def _seed_v2_media_login_and_context(client, db_session) -> tuple[str, str]:
    _seed_v2_media_context(db_session)
    login_response = client.post(
        "/api/v2/auth/login",
        json={"email": "owner@example.com", "password": "dev-password"},
    )
    assert login_response.status_code == 200
    token = login_response.json()["data"]["access_token"]
    context_response = client.post(
        "/api/v2/context/select",
        headers={"Authorization": f"Bearer {token}"},
        json={"tenant_id": "tenant_a", "shop_id": "shop_a1"},
    )
    assert context_response.status_code == 200
    return token, context_response.json()["data"]["context_token"]


class _StubObjectStorage:
    def __init__(self) -> None:
        self.created_targets: list[tuple[str, str, int]] = []
        self.verified_objects: list[tuple[str, int | None, str | None]] = []

    def create_upload_target(
        self,
        *,
        object_key: str,
        content_type: str,
        size_bytes: int,
    ):
        from app.services.object_storage import ObjectStorageUploadTarget

        self.created_targets.append((object_key, content_type, size_bytes))
        return ObjectStorageUploadTarget(
            object_key=object_key,
            upload_url=f"https://upload.example/{object_key}",
            public_url=f"https://public.example/{object_key}",
        )

    def verify_uploaded_object(
        self,
        *,
        object_key: str,
        expected_size_bytes: int | None = None,
        expected_checksum_sha256: str | None = None,
    ) -> dict[str, object]:
        self.verified_objects.append((object_key, expected_size_bytes, expected_checksum_sha256))
        return {
            "object_key": object_key,
            "size_bytes": expected_size_bytes,
            "checksum_sha256": expected_checksum_sha256,
        }


def _seed_v2_uploaded_media_asset(
    db_session,
    *,
    context_session_id: str = "vctx_001",
    storage: _StubObjectStorage | None = None,
) -> str:
    from app.services.v2_media_assets import create_v2_media_asset_upload, mark_v2_media_asset_uploaded

    object_storage = storage or _StubObjectStorage()
    created = create_v2_media_asset_upload(
        db_session,
        tenant_id="tenant_a",
        shop_id="shop_a1",
        context_session_id=context_session_id,
        uploaded_by_account_id="acct_001",
        media_type="receipt-image",
        file_name="receipt.jpg",
        content_type="image/jpeg",
        size_bytes=2048,
        object_storage=object_storage,
    )
    mark_v2_media_asset_uploaded(
        db_session,
        tenant_id="tenant_a",
        shop_id="shop_a1",
        media_asset_id=created.media_asset_id,
        checksum_sha256="abc123",
        size_bytes=2048,
        object_storage=object_storage,
    )
    return created.media_asset_id


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

    persisted_asset = db_session.get(V2MediaAsset, "vmedia_001")
    persisted_log = db_session.get(V2ModelCallLog, "vcall_001")
    assert persisted_asset is not None
    assert persisted_asset.tenant_id == "tenant_a"
    assert persisted_asset.shop_id == "shop_a1"
    assert persisted_log is not None
    assert persisted_log.tenant_id == "tenant_a"
    assert persisted_log.shop_id == "shop_a1"


def test_create_v2_media_asset_upload_persists_pending_asset_with_context(db_session) -> None:
    from app.models import V2MediaAsset
    from app.services.v2_media_assets import create_v2_media_asset_upload

    _seed_v2_media_context(db_session)
    storage = _StubObjectStorage()

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
    assert asset is not None
    assert asset.tenant_id == "tenant_a"
    assert asset.shop_id == "shop_a1"
    assert asset.context_session_id == "vctx_001"
    assert asset.status == "pending"
    assert asset.object_key.startswith("tenants/tenant_a/shops/shop_a1/media/")
    assert storage.created_targets[0][0] == asset.object_key


def test_mark_v2_media_asset_uploaded_marks_record_uploaded(db_session) -> None:
    from app.services.v2_media_assets import create_v2_media_asset_upload, mark_v2_media_asset_uploaded

    _seed_v2_media_context(db_session)
    storage = _StubObjectStorage()
    created = create_v2_media_asset_upload(
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

    completed = mark_v2_media_asset_uploaded(
        db_session,
        tenant_id="tenant_a",
        shop_id="shop_a1",
        media_asset_id=created.media_asset_id,
        checksum_sha256="abc123",
        size_bytes=2048,
        object_storage=storage,
    )

    assert completed.status == "uploaded"
    assert storage.verified_objects


def test_append_v2_model_call_log_persists_provider_observability(db_session) -> None:
    from app.services.v2_media_assets import create_v2_media_asset_upload, mark_v2_media_asset_uploaded
    from app.services.v2_model_call_logs import append_v2_model_call_log

    _seed_v2_media_context(db_session)
    storage = _StubObjectStorage()
    created = create_v2_media_asset_upload(
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
    mark_v2_media_asset_uploaded(
        db_session,
        tenant_id="tenant_a",
        shop_id="shop_a1",
        media_asset_id=created.media_asset_id,
        checksum_sha256="abc123",
        size_bytes=2048,
        object_storage=storage,
    )

    log = append_v2_model_call_log(
        db_session,
        tenant_id="tenant_a",
        shop_id="shop_a1",
        context_session_id="vctx_001",
        requested_by_account_id="acct_001",
        media_asset_id=created.media_asset_id,
        task_run_id=None,
        conversation_session_id=None,
        provider_type="ocr",
        provider_key="mock",
        model_name="mock-ocr",
        operation_type="receipt.extract",
        status="completed",
        request_payload={"media_asset_id": created.media_asset_id},
        response_payload={"total_amount": 18.5},
        error_code=None,
        latency_ms=25,
        cost_micros=0,
    )

    assert log.tenant_id == "tenant_a"
    assert log.shop_id == "shop_a1"
    assert log.status == "completed"
    assert log.media_asset_id == created.media_asset_id


def test_append_v2_model_call_log_persists_observability_metadata(db_session) -> None:
    from app.services.v2_model_call_logs import append_v2_model_call_log

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


def test_v2_create_media_asset_requires_context(client, db_session) -> None:
    token, _ = _seed_v2_media_login_and_context(client, db_session)

    response = client.post(
        "/api/v2/media-assets",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "media_type": "image",
            "file_name": "receipt.jpg",
            "content_type": "image/jpeg",
            "size_bytes": 2048,
        },
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "context_required"


def test_v2_create_document_requires_context(client, db_session) -> None:
    token, context_token = _seed_v2_media_login_and_context(client, db_session)
    media_asset_id = _seed_v2_uploaded_media_asset(db_session, context_session_id=context_token)

    response = client.post(
        "/api/v2/documents",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "media_asset_id": media_asset_id,
            "document_type": "purchase-receipt",
            "extraction_status": "completed",
            "extracted_fields": {"total_amount": 18.5},
            "confidence_summary": {"overall": 0.91},
        },
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "context_required"


def test_v2_create_and_complete_media_asset_uses_current_context(client, db_session, monkeypatch) -> None:
    import app.services.v2_media_assets as media_assets_service

    token, context_token = _seed_v2_media_login_and_context(client, db_session)
    storage = _StubObjectStorage()
    monkeypatch.setattr(media_assets_service, "get_default_object_storage", lambda: storage)

    create_response = client.post(
        "/api/v2/media-assets",
        headers={"Authorization": f"Bearer {token}", "X-Context-Token": context_token},
        json={
            "media_type": "image",
            "file_name": "receipt.jpg",
            "content_type": "image/jpeg",
            "size_bytes": 2048,
        },
    )
    media_asset_id = create_response.json()["data"]["media_asset_id"]
    complete_response = client.post(
        f"/api/v2/media-assets/{media_asset_id}/complete",
        headers={"Authorization": f"Bearer {token}", "X-Context-Token": context_token},
        json={"checksum_sha256": "abc123", "size_bytes": 2048},
    )

    assert create_response.status_code == 201
    assert create_response.json()["data"]["status"] == "pending"
    assert complete_response.status_code == 200
    assert complete_response.json()["data"] == {
        "media_asset_id": media_asset_id,
        "status": "uploaded",
    }


def test_v2_create_and_get_document_uses_current_context(client, db_session) -> None:
    token, context_token = _seed_v2_media_login_and_context(client, db_session)
    media_asset_id = _seed_v2_uploaded_media_asset(db_session, context_session_id=context_token)

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
    assert create_response.json()["data"]["document_type"] == "purchase-receipt"
    assert detail_response.status_code == 200
    assert detail_response.json()["data"]["document_id"] == document_id
    assert detail_response.json()["data"]["media_asset_id"] == media_asset_id
