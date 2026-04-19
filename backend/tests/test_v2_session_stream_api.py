from datetime import UTC, datetime


def _utc_now_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _seed_v2_identity_for_runtime(db_session) -> None:
    from app.models import V2Account, V2Shop, V2ShopAccess, V2Tenant, V2TenantMembership
    from app.services.v2_identity import hash_v2_password

    now = _utc_now_naive()
    password_salt = "11" * 16
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
            name="Tenant A",
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
            name="Shop A1",
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
    db_session.commit()


def _seed_v2_login_and_context(client, db_session) -> tuple[str, str]:
    _seed_v2_identity_for_runtime(db_session)
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
    def create_upload_target(
        self,
        *,
        object_key: str,
        content_type: str,
        size_bytes: int,
    ):
        from app.services.object_storage import ObjectStorageUploadTarget

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
        return {
            "object_key": object_key,
            "size_bytes": expected_size_bytes,
            "checksum_sha256": expected_checksum_sha256,
        }


class _StubEmptyReceiptOcrGateway:
    def extract_purchase_receipt(self, media_input):
        from app.services.ocr_types import OcrExtraction

        return OcrExtraction(
            document_type="purchase-receipt",
            provider_name="stub-ocr",
            raw_text="Unreadable receipt text",
            line_items=[],
            total_amount=None,
            low_confidence_fields=["items"],
            used_fallback=False,
            raw_payload={"provider": "stub", "items": []},
        )


def _headers(token: str, context_token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "X-Context-Token": context_token,
    }


def _seed_uploaded_receipt_media_asset(db_session, *, context_session_id: str) -> str:
    from app.services.v2_media_assets import create_v2_media_asset_upload, mark_v2_media_asset_uploaded

    storage = _StubObjectStorage()
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
    return created.media_asset_id


def _create_receipt_clarification_committed_session(client, db_session, *, token: str, context_token: str):
    session_response = client.post(
        "/api/v2/sessions",
        headers=_headers(token, context_token),
        json={"session_type": "receipt", "title": "Receipt Clarification Stream"},
    )
    assert session_response.status_code == 201
    session_id = session_response.json()["data"]["session_id"]
    message_response = client.post(
        f"/api/v2/sessions/{session_id}/messages",
        headers=_headers(token, context_token),
        json={
            "message_kind": "receipt-image",
            "payload_json": {"text": "extract unclear receipt"},
            "client_request_id": "v2_stream_receipt_clarification_inventory_001",
        },
    )
    assert message_response.status_code == 201
    task_run_id = message_response.json()["data"]["task_run_id"]
    media_asset_id = _seed_uploaded_receipt_media_asset(db_session, context_session_id=context_token)
    extraction_response = client.post(
        "/api/v2/documents/receipt-extractions",
        headers=_headers(token, context_token),
        json={
            "media_asset_id": media_asset_id,
            "task_run_id": task_run_id,
            "conversation_session_id": session_id,
        },
    )
    assert extraction_response.status_code == 201
    document_id = extraction_response.json()["data"]["document_id"]
    clarifications_response = client.get(
        "/api/v2/clarifications?status=pending&limit=20",
        headers=_headers(token, context_token),
    )
    assert clarifications_response.status_code == 200
    clarification_id = clarifications_response.json()["data"]["clarifications"][0]["clarification_id"]
    answer_payload = {
        "item_name": "Sprite 330ml",
        "quantity": 2,
        "unit": "can",
        "price": 6.5,
    }
    answer_response = client.post(
        f"/api/v2/clarifications/{clarification_id}/answer",
        headers=_headers(token, context_token),
        json={"answer_payload": answer_payload},
    )
    assert answer_response.status_code == 200
    confirmation_response = client.post(
        f"/api/v2/task-runs/{task_run_id}/confirmations",
        headers=_headers(token, context_token),
        json={"confirmation_type": "inventory.stock_in"},
    )
    assert confirmation_response.status_code == 201
    confirmation_id = confirmation_response.json()["data"]["confirmation_id"]
    approve_response = client.post(
        f"/api/v2/confirmations/{confirmation_id}/approve",
        headers=_headers(token, context_token),
        json={"resolution_payload": {"fields": dict(answer_payload)}},
    )
    assert approve_response.status_code == 200
    return session_id, task_run_id, document_id, media_asset_id


def _dispatch_v2_outbox_scope(db_session) -> None:
    from app.services.v2_outbox_dispatch import dispatch_v2_outbox_events

    result = dispatch_v2_outbox_events(
        db_session,
        tenant_id="tenant_a",
        shop_id="shop_a1",
        limit=10,
    )
    db_session.commit()

    assert result.claimed_count == 1
    assert result.completed_count == 1


def test_v2_session_stream_api_replays_message_and_task_events(client, db_session) -> None:
    token, context_token = _seed_v2_login_and_context(client, db_session)
    session_response = client.post(
        "/api/v2/sessions",
        headers={"Authorization": f"Bearer {token}", "X-Context-Token": context_token},
        json={"session_type": "workgroup", "title": "Stream test"},
    )
    session_id = session_response.json()["data"]["session_id"]

    message_response = client.post(
        f"/api/v2/sessions/{session_id}/messages",
        headers={"Authorization": f"Bearer {token}", "X-Context-Token": context_token},
        json={
            "message_kind": "text",
            "payload_json": {"text": "restock cola"},
            "client_request_id": "v2_stream_001",
        },
    )

    unauthorized = client.get(f"/api/v2/sessions/{session_id}/stream-events?after_seq=0")
    response = client.get(
        f"/api/v2/sessions/{session_id}/stream-events?after_seq=0",
        headers={"Authorization": f"Bearer {token}", "X-Context-Token": context_token},
    )

    assert message_response.status_code == 201
    assert unauthorized.status_code == 401
    assert response.status_code == 200
    assert response.json()["data"]["session_id"] == session_id
    assert response.json()["data"]["count"] == 2
    assert response.json()["data"]["last_event_seq"] == 2
    assert [event["event_type"] for event in response.json()["data"]["events"]] == [
        "message.created",
        "task.updated",
    ]


def test_v2_session_stream_api_respects_after_seq_limit_and_session_scope(client, db_session) -> None:
    token, context_token = _seed_v2_login_and_context(client, db_session)
    session_response = client.post(
        "/api/v2/sessions",
        headers={"Authorization": f"Bearer {token}", "X-Context-Token": context_token},
        json={"session_type": "workgroup", "title": "Scoped stream"},
    )
    session_id = session_response.json()["data"]["session_id"]

    client.post(
        f"/api/v2/sessions/{session_id}/messages",
        headers={"Authorization": f"Bearer {token}", "X-Context-Token": context_token},
        json={
            "message_kind": "text",
            "payload_json": {"text": "one"},
            "client_request_id": "v2_stream_limit_1",
        },
    )
    client.post(
        f"/api/v2/sessions/{session_id}/messages",
        headers={"Authorization": f"Bearer {token}", "X-Context-Token": context_token},
        json={
            "message_kind": "text",
            "payload_json": {"text": "two"},
            "client_request_id": "v2_stream_limit_2",
        },
    )

    replay_response = client.get(
        f"/api/v2/sessions/{session_id}/stream-events?after_seq=2&limit=2",
        headers={"Authorization": f"Bearer {token}", "X-Context-Token": context_token},
    )
    missing_response = client.get(
        "/api/v2/sessions/vsess_missing/stream-events?after_seq=0",
        headers={"Authorization": f"Bearer {token}", "X-Context-Token": context_token},
    )

    assert replay_response.status_code == 200
    assert replay_response.json()["data"]["count"] == 2
    assert [event["seq"] for event in replay_response.json()["data"]["events"]] == [3, 4]
    assert missing_response.status_code == 404
    assert missing_response.json()["error"]["code"] == "session_not_found"


def test_v2_session_stream_api_replays_receipt_clarification_inventory_update_provenance(
    client, db_session, monkeypatch
) -> None:
    import app.services.v2_receipt_documents as receipt_documents_service

    token, context_token = _seed_v2_login_and_context(client, db_session)
    monkeypatch.setattr(
        receipt_documents_service,
        "get_default_ocr_gateway",
        lambda: _StubEmptyReceiptOcrGateway(),
    )
    session_id, task_run_id, document_id, media_asset_id = _create_receipt_clarification_committed_session(
        client,
        db_session,
        token=token,
        context_token=context_token,
    )

    _dispatch_v2_outbox_scope(db_session)
    replay_response = client.get(
        f"/api/v2/sessions/{session_id}/stream-events?after_seq=0&limit=20",
        headers=_headers(token, context_token),
    )

    assert replay_response.status_code == 200
    events = replay_response.json()["data"]["events"]
    inventory_events = [event for event in events if event["event_type"] == "inventory.updated"]
    assert len(inventory_events) == 1
    inventory_event = inventory_events[0]
    assert inventory_event["session_id"] == session_id
    assert inventory_event["task_run_id"] == task_run_id
    assert inventory_event["data"]["event_type"] == "stock_in"
    assert inventory_event["data"]["quantity_after"] == "2"
    assert inventory_event["data"]["source_type"] == "receipt-document"
    assert inventory_event["data"]["source_id"] == document_id
    assert inventory_event["data"]["source_document_id"] == document_id
    assert inventory_event["data"]["source_media_asset_id"] == media_asset_id
    assert inventory_event["data"]["ledger_source_type"] == "task_run"
    assert inventory_event["data"]["ledger_source_id"] == task_run_id
