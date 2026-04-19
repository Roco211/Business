from datetime import UTC, datetime
import time

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from conftest import load_create_app, upgrade_test_database


def _utc_now_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _create_v2_websocket_client(
    monkeypatch,
    tmp_path,
    *,
    keepalive_seconds: str = "0.01",
    pending_poll_seconds: str | None = None,
) -> TestClient:
    database_url = f"sqlite:///{(tmp_path / 'v2_ws.db').as_posix()}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("SESSION_STREAM_KEEPALIVE_SECONDS", keepalive_seconds)
    if pending_poll_seconds is not None:
        monkeypatch.setenv("SESSION_STREAM_PENDING_POLL_SECONDS", pending_poll_seconds)
    upgrade_test_database(database_url)
    return TestClient(load_create_app()())


def _seed_v2_identity_for_ws(db_session) -> None:
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


def _seed_v2_login_and_context_for_ws(client: TestClient) -> tuple[str, str]:
    from app.db.session import get_session_factory

    db_session = get_session_factory()()
    try:
        _seed_v2_identity_for_ws(db_session)
    finally:
        db_session.close()

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


def _v2_headers(token: str, context_token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "X-Context-Token": context_token,
    }


def _create_v2_ws_session(client: TestClient, *, token: str, context_token: str) -> str:
    response = client.post(
        "/api/v2/sessions",
        headers=_v2_headers(token, context_token),
        json={"session_type": "workgroup", "title": "V2 websocket test"},
    )
    assert response.status_code == 201
    return response.json()["data"]["session_id"]


def _post_v2_ws_message(
    client: TestClient,
    *,
    token: str,
    context_token: str,
    session_id: str,
    text: str,
    client_request_id: str,
) -> None:
    response = client.post(
        f"/api/v2/sessions/{session_id}/messages",
        headers=_v2_headers(token, context_token),
        json={
            "message_kind": "text",
            "payload_json": {"text": text},
            "client_request_id": client_request_id,
        },
    )
    assert response.status_code == 201


def _create_v2_stock_in_confirmed_session(
    client: TestClient,
    *,
    token: str,
    context_token: str,
) -> str:
    session_id = _create_v2_ws_session(client, token=token, context_token=context_token)
    message_response = client.post(
        f"/api/v2/sessions/{session_id}/messages",
        headers=_v2_headers(token, context_token),
        json={
            "message_kind": "text",
            "payload_json": {"text": "restock cola"},
            "client_request_id": "v2_ws_worker_001",
            "intent_type": "inventory.stock_in",
        },
    )
    assert message_response.status_code == 201
    task_run_id = message_response.json()["data"]["task_run_id"]

    draft_payload = {"item_name": "Cola", "quantity": 2, "unit": "box", "price": 18.5}
    draft_response = client.post(
        f"/api/v2/task-runs/{task_run_id}/draft",
        headers=_v2_headers(token, context_token),
        json={"draft_type": "inventory.stock_in", "draft_payload": draft_payload},
    )
    assert draft_response.status_code == 200

    confirmation_response = client.post(
        f"/api/v2/task-runs/{task_run_id}/confirmations",
        headers=_v2_headers(token, context_token),
        json={"confirmation_type": "inventory.stock_in"},
    )
    assert confirmation_response.status_code == 201
    confirmation_id = confirmation_response.json()["data"]["confirmation_id"]

    approve_response = client.post(
        f"/api/v2/confirmations/{confirmation_id}/approve",
        headers=_v2_headers(token, context_token),
        json={"resolution_payload": {"fields": draft_payload}},
    )
    assert approve_response.status_code == 200
    return session_id


def _create_v2_receipt_derived_stock_in_confirmed_session(
    client: TestClient,
    *,
    token: str,
    context_token: str,
) -> tuple[str, str]:
    session_id = _create_v2_ws_session(client, token=token, context_token=context_token)
    message_response = client.post(
        f"/api/v2/sessions/{session_id}/messages",
        headers=_v2_headers(token, context_token),
        json={
            "message_kind": "text",
            "payload_json": {"text": "restock receipt cola"},
            "client_request_id": "v2_ws_receipt_inventory_001",
            "intent_type": "inventory.stock_in",
        },
    )
    assert message_response.status_code == 201
    task_run_id = message_response.json()["data"]["task_run_id"]

    receipt_draft_payload = {
        "item_name": "Receipt Cola",
        "quantity": 2,
        "unit": "box",
        "price": 18.5,
        "source_type": "receipt-document",
        "source_document_id": "vdoc_receipt_001",
        "source_media_asset_id": "vmedia_receipt_001",
    }
    draft_response = client.post(
        f"/api/v2/task-runs/{task_run_id}/draft",
        headers=_v2_headers(token, context_token),
        json={
            "draft_type": "inventory.stock_in",
            "draft_payload": receipt_draft_payload,
        },
    )
    assert draft_response.status_code == 200

    confirmation_response = client.post(
        f"/api/v2/task-runs/{task_run_id}/confirmations",
        headers=_v2_headers(token, context_token),
        json={"confirmation_type": "inventory.stock_in"},
    )
    assert confirmation_response.status_code == 201
    confirmation_id = confirmation_response.json()["data"]["confirmation_id"]

    approve_response = client.post(
        f"/api/v2/confirmations/{confirmation_id}/approve",
        headers=_v2_headers(token, context_token),
        json={
            "resolution_payload": {
                "fields": {
                    "item_name": "Receipt Cola",
                    "quantity": 2,
                    "unit": "box",
                    "price": 18.5,
                }
            }
        },
    )
    assert approve_response.status_code == 200
    return session_id, task_run_id


def _dispatch_v2_outbox_scope() -> None:
    from app.db.session import get_session_factory
    from app.services.v2_outbox_dispatch import dispatch_v2_outbox_events

    dispatch_session = get_session_factory()()
    try:
        result = dispatch_v2_outbox_events(
            dispatch_session,
            tenant_id="tenant_a",
            shop_id="shop_a1",
            limit=10,
        )
        dispatch_session.commit()
    finally:
        dispatch_session.close()

    assert result.claimed_count == 1
    assert result.completed_count == 1


class _StubWsObjectStorage:
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


class _StubWsReceiptOcrGateway:
    def extract_purchase_receipt(self, media_input):
        from app.services.ocr_types import OcrExtractedLineItem, OcrExtraction

        return OcrExtraction(
            document_type="purchase-receipt",
            provider_name="stub-ocr",
            raw_text="Red Bull 250ml x 2",
            line_items=[
                OcrExtractedLineItem(
                    item_name="Red Bull 250ml",
                    quantity=2.0,
                    unit="can",
                    price=6.5,
                )
            ],
            total_amount=13.0,
            low_confidence_fields=[],
            used_fallback=False,
            raw_payload={"provider": "stub"},
        )


class _StubWsEmptyReceiptOcrGateway:
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


def _seed_v2_uploaded_receipt_media_asset_for_ws(*, context_session_id: str) -> str:
    from app.db.session import get_session_factory
    from app.services.v2_media_assets import create_v2_media_asset_upload, mark_v2_media_asset_uploaded

    db_session = get_session_factory()()
    storage = _StubWsObjectStorage()
    try:
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
    finally:
        db_session.close()


def test_v2_session_stream_ws_rejects_invalid_token(monkeypatch, tmp_path) -> None:
    with _create_v2_websocket_client(monkeypatch, tmp_path) as client:
        with client.websocket_connect(
            "/api/v2/ws/sessions/vsess_missing?token=bad_token&context_token=bad_context"
        ) as websocket:
            with pytest.raises(WebSocketDisconnect) as disconnect:
                websocket.receive_json()

    assert disconnect.value.code == 4401


def test_v2_session_stream_ws_rejects_missing_context_token(monkeypatch, tmp_path) -> None:
    with _create_v2_websocket_client(monkeypatch, tmp_path) as client:
        token, context_token = _seed_v2_login_and_context_for_ws(client)
        session_id = _create_v2_ws_session(client, token=token, context_token=context_token)

        with client.websocket_connect(f"/api/v2/ws/sessions/{session_id}?token={token}") as websocket:
            with pytest.raises(WebSocketDisconnect) as disconnect:
                websocket.receive_json()

    assert disconnect.value.code == 4401


def test_v2_session_stream_ws_rejects_session_outside_context(monkeypatch, tmp_path) -> None:
    with _create_v2_websocket_client(monkeypatch, tmp_path) as client:
        token, context_token = _seed_v2_login_and_context_for_ws(client)

        with client.websocket_connect(
            f"/api/v2/ws/sessions/vsess_missing?token={token}&context_token={context_token}"
        ) as websocket:
            with pytest.raises(WebSocketDisconnect) as disconnect:
                websocket.receive_json()

    assert disconnect.value.code == 4404


def test_v2_session_stream_ws_sends_ready_and_keepalive(monkeypatch, tmp_path) -> None:
    with _create_v2_websocket_client(monkeypatch, tmp_path, keepalive_seconds="0.001") as client:
        token, context_token = _seed_v2_login_and_context_for_ws(client)
        session_id = _create_v2_ws_session(client, token=token, context_token=context_token)

        with client.websocket_connect(
            f"/api/v2/ws/sessions/{session_id}?token={token}&context_token={context_token}"
        ) as websocket:
            ready_event = websocket.receive_json()
            keepalive_event = websocket.receive_json()

    assert ready_event["event_type"] == "session.ready"
    assert ready_event["session_id"] == session_id
    assert ready_event["seq"] == 0
    assert ready_event["event_id"]
    assert ready_event["occurred_at"]

    assert keepalive_event["event_type"] == "stream.keepalive"
    assert keepalive_event["session_id"] == session_id
    assert keepalive_event["seq"] == 0
    assert keepalive_event["event_id"]
    assert keepalive_event["occurred_at"]


def test_v2_session_stream_ws_replays_events_after_requested_seq(monkeypatch, tmp_path) -> None:
    with _create_v2_websocket_client(monkeypatch, tmp_path, keepalive_seconds="1") as client:
        token, context_token = _seed_v2_login_and_context_for_ws(client)
        session_id = _create_v2_ws_session(client, token=token, context_token=context_token)
        _post_v2_ws_message(
            client,
            token=token,
            context_token=context_token,
            session_id=session_id,
            text="one",
            client_request_id="v2_ws_001",
        )
        _post_v2_ws_message(
            client,
            token=token,
            context_token=context_token,
            session_id=session_id,
            text="two",
            client_request_id="v2_ws_002",
        )

        with client.websocket_connect(
            f"/api/v2/ws/sessions/{session_id}?token={token}&context_token={context_token}&after_seq=2"
        ) as websocket:
            ready_event = websocket.receive_json()
            replayed_event = websocket.receive_json()

    assert ready_event["event_type"] == "session.ready"
    assert ready_event["session_id"] == session_id
    assert ready_event["seq"] == 4

    assert replayed_event["event_type"] == "message.created"
    assert replayed_event["session_id"] == session_id
    assert replayed_event["seq"] == 3
    assert replayed_event["data"]["preview_text"] == "two"


def test_v2_session_stream_ws_closes_when_auth_session_is_revoked(monkeypatch, tmp_path) -> None:
    with _create_v2_websocket_client(monkeypatch, tmp_path, keepalive_seconds="0.001") as client:
        token, context_token = _seed_v2_login_and_context_for_ws(client)
        session_id = _create_v2_ws_session(client, token=token, context_token=context_token)

        with client.websocket_connect(
            f"/api/v2/ws/sessions/{session_id}?token={token}&context_token={context_token}"
        ) as websocket:
            ready_event = websocket.receive_json()
            assert ready_event["event_type"] == "session.ready"

            logout_response = client.post(
                "/api/v2/auth/logout",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert logout_response.status_code == 200

            disconnect = None
            for _ in range(25):
                try:
                    websocket.receive_json()
                except WebSocketDisconnect as exc:
                    disconnect = exc
                    break

    assert disconnect is not None
    assert disconnect.code == 4401


def test_v2_session_stream_ws_pushes_new_events_without_waiting_for_keepalive(
    monkeypatch, tmp_path
) -> None:
    with _create_v2_websocket_client(monkeypatch, tmp_path, keepalive_seconds="5") as client:
        token, context_token = _seed_v2_login_and_context_for_ws(client)
        session_id = _create_v2_ws_session(client, token=token, context_token=context_token)

        with client.websocket_connect(
            f"/api/v2/ws/sessions/{session_id}?token={token}&context_token={context_token}"
        ) as websocket:
            ready_event = websocket.receive_json()
            assert ready_event["event_type"] == "session.ready"

            started = time.perf_counter()
            _post_v2_ws_message(
                client,
                token=token,
                context_token=context_token,
                session_id=session_id,
                text="fanout now",
                client_request_id="v2_ws_live_001",
            )
            first_event = websocket.receive_json()
            second_event = websocket.receive_json()
            elapsed = time.perf_counter() - started

    assert elapsed < 1.0
    assert [first_event["event_type"], second_event["event_type"]] == [
        "message.created",
        "task.updated",
    ]
    assert first_event["data"]["preview_text"] == "fanout now"
    assert second_event["data"]["status"] == "captured"


def test_v2_session_stream_ws_delivers_worker_inventory_update_before_keepalive(
    monkeypatch, tmp_path
) -> None:
    with _create_v2_websocket_client(
        monkeypatch,
        tmp_path,
        keepalive_seconds="5",
        pending_poll_seconds="0.05",
    ) as client:
        token, context_token = _seed_v2_login_and_context_for_ws(client)
        session_id = _create_v2_stock_in_confirmed_session(
            client,
            token=token,
            context_token=context_token,
        )

        with client.websocket_connect(
            f"/api/v2/ws/sessions/{session_id}?token={token}&context_token={context_token}"
        ) as websocket:
            ready_event = websocket.receive_json()
            assert ready_event["event_type"] == "session.ready"

            started = time.perf_counter()
            _dispatch_v2_outbox_scope()
            inventory_event = websocket.receive_json()
            elapsed = time.perf_counter() - started

    assert elapsed < 1.0
    assert inventory_event["event_type"] == "inventory.updated"
    assert inventory_event["session_id"] == session_id
    assert inventory_event["data"]["event_type"] == "stock_in"
    assert inventory_event["data"]["quantity_after"] == "2"


def test_v2_session_stream_ws_delivers_receipt_inventory_update_provenance_before_keepalive(
    monkeypatch, tmp_path
) -> None:
    with _create_v2_websocket_client(
        monkeypatch,
        tmp_path,
        keepalive_seconds="5",
        pending_poll_seconds="0.05",
    ) as client:
        token, context_token = _seed_v2_login_and_context_for_ws(client)
        session_id, task_run_id = _create_v2_receipt_derived_stock_in_confirmed_session(
            client,
            token=token,
            context_token=context_token,
        )

        with client.websocket_connect(
            f"/api/v2/ws/sessions/{session_id}?token={token}&context_token={context_token}"
        ) as websocket:
            ready_event = websocket.receive_json()
            assert ready_event["event_type"] == "session.ready"

            started = time.perf_counter()
            _dispatch_v2_outbox_scope()
            inventory_event = websocket.receive_json()
            elapsed = time.perf_counter() - started

    assert elapsed < 1.0
    assert inventory_event["event_type"] == "inventory.updated"
    assert inventory_event["session_id"] == session_id
    assert inventory_event["task_run_id"] == task_run_id
    assert inventory_event["data"]["event_type"] == "stock_in"
    assert inventory_event["data"]["quantity_after"] == "2"
    assert inventory_event["data"]["source_type"] == "receipt-document"
    assert inventory_event["data"]["source_document_id"] == "vdoc_receipt_001"
    assert inventory_event["data"]["source_media_asset_id"] == "vmedia_receipt_001"
    assert inventory_event["data"]["ledger_source_type"] == "task_run"
    assert inventory_event["data"]["ledger_source_id"] == task_run_id


def test_v2_session_stream_ws_pushes_receipt_extraction_progression_without_waiting_for_keepalive(
    monkeypatch, tmp_path
) -> None:
    import app.services.v2_receipt_documents as receipt_documents_service

    with _create_v2_websocket_client(
        monkeypatch,
        tmp_path,
        keepalive_seconds="5",
        pending_poll_seconds="0.5",
    ) as client:
        token, context_token = _seed_v2_login_and_context_for_ws(client)
        session_id = _create_v2_ws_session(client, token=token, context_token=context_token)
        message_response = client.post(
            f"/api/v2/sessions/{session_id}/messages",
            headers=_v2_headers(token, context_token),
            json={
                "message_kind": "receipt-image",
                "payload_json": {"text": "extract receipt"},
                "client_request_id": "v2_ws_receipt_extract_001",
            },
        )
        assert message_response.status_code == 201
        task_run_id = message_response.json()["data"]["task_run_id"]
        media_asset_id = _seed_v2_uploaded_receipt_media_asset_for_ws(context_session_id=context_token)
        monkeypatch.setattr(receipt_documents_service, "get_default_ocr_gateway", lambda: _StubWsReceiptOcrGateway())

        with client.websocket_connect(
            f"/api/v2/ws/sessions/{session_id}?token={token}&context_token={context_token}"
        ) as websocket:
            ready_event = websocket.receive_json()
            assert ready_event["event_type"] == "session.ready"

            started = time.perf_counter()
            extraction_response = client.post(
                "/api/v2/documents/receipt-extractions",
                headers=_v2_headers(token, context_token),
                json={
                    "media_asset_id": media_asset_id,
                    "task_run_id": task_run_id,
                    "conversation_session_id": session_id,
                },
            )
            first_event = websocket.receive_json()
            second_event = websocket.receive_json()
            third_event = websocket.receive_json()
            elapsed = time.perf_counter() - started

    assert extraction_response.status_code == 201
    assert elapsed < 0.4
    assert [first_event["event_type"], second_event["event_type"], third_event["event_type"]] == [
        "task.updated",
        "task.updated",
        "message.created",
    ]
    assert [first_event["data"]["status"], second_event["data"]["status"]] == [
        "drafted",
        "awaiting_confirmation",
    ]
    assert third_event["task_run_id"] == task_run_id
    assert third_event["data"]["message_kind"] == "system_result"
    assert third_event["data"]["preview_text"] == "Receipt stock-in draft is ready for confirmation."
    assert third_event["data"]["payload_json"]["task_run_id"] == task_run_id
    assert third_event["data"]["payload_json"]["confirmation_id"]
    assert third_event["data"]["payload_json"]["confirmation_type"] == "inventory.stock_in"
    assert third_event["data"]["payload_json"]["task_run_status"] == "awaiting_confirmation"
    assert third_event["data"]["payload_json"]["source_type"] == "receipt-document"
    assert third_event["data"]["payload_json"]["source_document_id"] == extraction_response.json()["data"]["document_id"]
    assert third_event["data"]["payload_json"]["source_media_asset_id"] == media_asset_id


def test_v2_session_stream_ws_pushes_receipt_extraction_clarification_without_waiting_for_keepalive(
    monkeypatch, tmp_path
) -> None:
    import app.services.v2_receipt_documents as receipt_documents_service

    with _create_v2_websocket_client(
        monkeypatch,
        tmp_path,
        keepalive_seconds="5",
        pending_poll_seconds="0.5",
    ) as client:
        token, context_token = _seed_v2_login_and_context_for_ws(client)
        session_id = _create_v2_ws_session(client, token=token, context_token=context_token)
        message_response = client.post(
            f"/api/v2/sessions/{session_id}/messages",
            headers=_v2_headers(token, context_token),
            json={
                "message_kind": "receipt-image",
                "payload_json": {"text": "extract unclear receipt"},
                "client_request_id": "v2_ws_receipt_extract_clarification_001",
            },
        )
        assert message_response.status_code == 201
        task_run_id = message_response.json()["data"]["task_run_id"]
        media_asset_id = _seed_v2_uploaded_receipt_media_asset_for_ws(context_session_id=context_token)
        monkeypatch.setattr(
            receipt_documents_service,
            "get_default_ocr_gateway",
            lambda: _StubWsEmptyReceiptOcrGateway(),
        )

        with client.websocket_connect(
            f"/api/v2/ws/sessions/{session_id}?token={token}&context_token={context_token}"
        ) as websocket:
            ready_event = websocket.receive_json()
            assert ready_event["event_type"] == "session.ready"

            started = time.perf_counter()
            extraction_response = client.post(
                "/api/v2/documents/receipt-extractions",
                headers=_v2_headers(token, context_token),
                json={
                    "media_asset_id": media_asset_id,
                    "task_run_id": task_run_id,
                    "conversation_session_id": session_id,
                },
            )
            task_event = websocket.receive_json()
            elapsed = time.perf_counter() - started

    assert extraction_response.status_code == 201
    assert extraction_response.json()["data"]["extracted_fields"]["items"] == []
    assert elapsed < 0.4
    assert task_event["event_type"] == "task.updated"
    assert task_event["task_run_id"] == task_run_id
    assert task_event["data"]["status"] == "needs_clarification"
    assert task_event["data"]["intent_type"] == "document.receipt.extract"
