import hashlib

from decimal import Decimal

from sqlalchemy import select

from app.api.routes import messages as message_routes
from app.db.session import get_session_factory
from app.models import Alert, AuditLog, Confirmation, InventoryEvent, InventoryItem, Message, OcrDocument, TaskRun
from app.runtime.processor import process_task_run
from app.runtime import router as runtime_router
from app.runtime import tools as runtime_tools
from app.services.asr_types import AsrTranscription
from app.services.bootstrap import ensure_default_context
from app.services.ocr_types import OcrExtractedLineItem, OcrExtraction
from app.services.object_storage import DEFAULT_MOCK_PUBLIC_BASE_URL, derive_media_object_key
from app.services.vision_types import VisionCandidate, VisionRecognition
from conftest import auth_headers, login_and_get_token

DEFAULT_SESSION_ID = "sess_default"


def _auth_headers(client, monkeypatch=None) -> dict[str, str]:
    return auth_headers(login_and_get_token(client, monkeypatch))


def _stub_runtime_dispatch(monkeypatch) -> None:
    monkeypatch.setattr(message_routes, "enqueue_runtime_task", lambda _task_run_id: True)


def _post_session_message(
    client,
    monkeypatch,
    *,
    client_request_id: str,
    message_type: str,
    text: str | None,
    media_ids: list[str],
) -> str:
    _stub_runtime_dispatch(monkeypatch)
    response = client.post(
        f"/api/v1/sessions/{DEFAULT_SESSION_ID}/messages",
        headers=_auth_headers(client, monkeypatch),
        json={
            "message_type": message_type,
            "text": text,
            "media_ids": media_ids,
            "client_request_id": client_request_id,
        },
    )
    assert response.status_code == 201
    return response.json()["data"]["task_run_id"]


def _process_runtime_task_run(
    task_run_id: str,
    *,
    expected_statuses: set[str] | None = None,
) -> None:
    db_session = get_session_factory()()
    try:
        result = process_task_run(db_session, task_run_id)
        allowed_statuses = expected_statuses or {"awaiting-confirmation", "completed"}
        assert result.status in allowed_statuses
    finally:
        db_session.close()


def _load_confirmation_for_task_run(task_run_id: str) -> Confirmation:
    db_session = get_session_factory()()
    try:
        confirmation = db_session.scalar(select(Confirmation).where(Confirmation.task_run_id == task_run_id))
        assert confirmation is not None
        return confirmation
    finally:
        db_session.close()


def _create_and_complete_media_upload(
    client,
    *,
    media_type: str,
    file_name: str,
    content_type: str,
) -> str:
    upload_bytes = f"uploaded bytes for {file_name}".encode("utf-8")
    size_bytes = len(upload_bytes)
    create_response = client.post(
        "/api/v1/media-uploads",
        headers=_auth_headers(client),
        json={
            "media_type": media_type,
            "file_name": file_name,
            "content_type": content_type,
            "size_bytes": size_bytes,
        },
    )
    assert create_response.status_code == 201
    upload_url = create_response.json()["data"]["upload_url"]
    media_id = create_response.json()["data"]["media_id"]
    upload_response = client.put(
        upload_url,
        content=upload_bytes,
        headers={"Content-Type": content_type},
    )
    assert upload_response.status_code == 200

    complete_response = client.post(
        f"/api/v1/media-uploads/{media_id}/complete",
        headers=_auth_headers(client),
        json={
            "checksum_sha256": hashlib.sha256(upload_bytes).hexdigest(),
            "size_bytes": size_bytes,
        },
    )
    assert complete_response.status_code == 200
    return media_id


def _expected_mock_public_url(*, media_id: str, file_name: str) -> str:
    object_key = derive_media_object_key(
        shop_id="shop_default",
        media_id=media_id,
        file_name=file_name,
    )
    return f"{DEFAULT_MOCK_PUBLIC_BASE_URL}/{object_key}"


def _approve_confirmation(client, *, confirmation_id: str, fields: dict[str, object]) -> dict[str, object]:
    response = client.post(
        f"/api/v1/confirmations/{confirmation_id}/approve",
        headers=_auth_headers(client),
        json={"fields": fields},
    )
    assert response.status_code == 200
    return response.json()["data"]


def _create_inventory_item_via_chat_stock_in(
    client,
    monkeypatch,
    *,
    item_name: str,
    quantity: int,
    unit: str = "box",
    price: float = 12.5,
    client_request_id: str,
    low_stock_threshold: Decimal | None = None,
) -> tuple[str, str]:
    if low_stock_threshold is not None:
        db_session = get_session_factory()()
        try:
            context = ensure_default_context(db_session)
            context.shop.default_low_stock_threshold = low_stock_threshold
            db_session.commit()
        finally:
            db_session.close()

    task_run_id = _post_session_message(
        client,
        monkeypatch,
        client_request_id=client_request_id,
        message_type="text",
        text=f"restock {item_name} today",
        media_ids=[],
    )
    _process_runtime_task_run(task_run_id)
    confirmation = _load_confirmation_for_task_run(task_run_id)
    _approve_confirmation(
        client,
        confirmation_id=confirmation.confirmation_id,
        fields={
            "item_name": item_name,
            "quantity": quantity,
            "unit": unit,
            "price": price,
        },
    )

    db_session = get_session_factory()()
    try:
        item = db_session.scalar(
            select(InventoryItem).where(
                InventoryItem.name == item_name,
                InventoryItem.is_active.is_(True),
            )
        )
        assert item is not None
        return item.item_id, task_run_id
    finally:
        db_session.close()


def _get_task_run(client, *, task_run_id: str) -> dict[str, object]:
    response = client.get(f"/api/v1/task-runs/{task_run_id}", headers=_auth_headers(client))
    assert response.status_code == 200
    return response.json()["data"]


def _get_session_messages(client) -> list[dict[str, object]]:
    response = client.get(f"/api/v1/sessions/{DEFAULT_SESSION_ID}/messages", headers=_auth_headers(client))
    assert response.status_code == 200
    return response.json()["data"]


def _get_alerts(client) -> list[dict[str, object]]:
    response = client.get("/api/v1/alerts?type=low-stock&limit=20", headers=_auth_headers(client))
    assert response.status_code == 200
    return response.json()["data"]


def _get_dashboard_summary(client) -> dict[str, object]:
    response = client.get("/api/v1/dashboard/summary", headers=_auth_headers(client))
    assert response.status_code == 200
    return response.json()["data"]


def test_acceptance_chat_stock_in_confirmation_flow(client, monkeypatch) -> None:
    task_run_id = _post_session_message(
        client,
        monkeypatch,
        client_request_id="acceptance_chat_stock_in",
        message_type="text",
        text="restock apples today",
        media_ids=[],
    )

    _process_runtime_task_run(task_run_id)
    awaiting_task_run = _get_task_run(client, task_run_id=task_run_id)
    confirmation = _load_confirmation_for_task_run(task_run_id)
    approve_payload = _approve_confirmation(
        client,
        confirmation_id=confirmation.confirmation_id,
        fields={
            "item_name": "Apple",
            "quantity": 8,
            "unit": "box",
            "price": 12.5,
        },
    )
    completed_task_run = _get_task_run(client, task_run_id=task_run_id)
    messages = _get_session_messages(client)

    db_session = get_session_factory()()
    try:
        inventory_events = db_session.scalars(select(InventoryEvent)).all()
        audit_logs = db_session.scalars(select(AuditLog)).all()
    finally:
        db_session.close()
    inventory_audit_logs = [log for log in audit_logs if log.scope == "inventory"]

    assert awaiting_task_run["status"] == "awaiting-confirmation"
    assert awaiting_task_run["task_type"] == "voice-stock-in"
    assert awaiting_task_run["confirmation_id"] == confirmation.confirmation_id
    assert approve_payload["status"] == "approved"
    assert completed_task_run["status"] == "completed"
    assert completed_task_run["task_type"] == "voice-stock-in"
    assert len(inventory_events) == 1
    assert inventory_events[0].event_type == "stock-in"
    assert len(inventory_audit_logs) == 1
    assert inventory_audit_logs[0].action == "inventory.stock_in_confirmed"
    assert any("please confirm the stock-in details" in (message["text"] or "").lower() for message in messages)
    assert any("stock-in committed" in (message["text"] or "").lower() for message in messages)


def test_acceptance_chat_stock_in_is_blocked_when_pilot_cutover_is_closed(client, monkeypatch) -> None:
    monkeypatch.setenv("APP_RUNTIME_MODE", "trial")
    monkeypatch.setenv("TRIAL_PROVIDER_PROFILE", "pilot-v1")

    task_run_id = _post_session_message(
        client,
        monkeypatch,
        client_request_id="acceptance_chat_stock_in_cutover_closed",
        message_type="text",
        text="restock apples today",
        media_ids=[],
    )

    _process_runtime_task_run(task_run_id, expected_statuses={"failed"})
    failed_task_run = _get_task_run(client, task_run_id=task_run_id)

    db_session = get_session_factory()()
    try:
        confirmation = db_session.scalar(select(Confirmation).where(Confirmation.task_run_id == task_run_id))
        telemetry_log = db_session.scalar(
            select(AuditLog).where(
                AuditLog.task_run_id == task_run_id,
                AuditLog.scope == "pilot",
                AuditLog.action == "runtime.provider_telemetry",
            )
        )
    finally:
        db_session.close()

    assert failed_task_run["status"] == "failed"
    assert failed_task_run["error_code"] == "pilot_cutover_closed"
    assert confirmation is None
    assert telemetry_log is not None
    assert telemetry_log.metadata_json["task_type"] == "voice-stock-in"
    assert telemetry_log.metadata_json["cutover_mode"] == "closed"
    assert telemetry_log.metadata_json["guardrail_status"] == "blocked"
    assert telemetry_log.metadata_json["guardrail_reason"] == "cutover_mode_closed"
    assert telemetry_log.metadata_json["error_code"] == "pilot_cutover_closed"


def test_acceptance_receipt_batch_stock_in_flow(client, monkeypatch) -> None:
    media_id = _create_and_complete_media_upload(
        client,
        media_type="receipt-image",
        file_name="receipt-demo.jpg",
        content_type="image/jpeg",
    )
    task_run_id = _post_session_message(
        client,
        monkeypatch,
        client_request_id="acceptance_receipt_batch_stock_in",
        message_type="receipt-image",
        text=None,
        media_ids=[media_id],
    )

    _process_runtime_task_run(task_run_id)
    awaiting_task_run = _get_task_run(client, task_run_id=task_run_id)
    confirmation = _load_confirmation_for_task_run(task_run_id)
    approve_payload = _approve_confirmation(
        client,
        confirmation_id=confirmation.confirmation_id,
        fields={
            "items": [
                {
                    "line_id": "line_1",
                    "item_name": "Red Bull 250ml",
                    "quantity": 3,
                    "unit": "can",
                    "price": 41.0,
                },
                {
                    "line_id": "line_2",
                    "item_name": "Coca Cola 500ml",
                    "quantity": 2,
                    "unit": "bottle",
                    "price": 12.0,
                },
            ]
        },
    )

    db_session = get_session_factory()()
    try:
        ocr_document = db_session.scalar(select(OcrDocument).where(OcrDocument.task_run_id == task_run_id))
        inventory_items = db_session.scalars(select(InventoryItem).order_by(InventoryItem.name.asc())).all()
        inventory_events = db_session.scalars(select(InventoryEvent).order_by(InventoryEvent.inventory_event_id.asc())).all()
        audit_logs = db_session.scalars(select(AuditLog).order_by(AuditLog.audit_log_id.asc())).all()
    finally:
        db_session.close()

    assert awaiting_task_run["status"] == "awaiting-confirmation"
    assert awaiting_task_run["task_type"] == "receipt-ocr"
    assert approve_payload["status"] == "approved"
    assert ocr_document is not None
    assert ocr_document.status == "completed"
    assert len(inventory_items) == 2
    assert [item.name for item in inventory_items] == ["Coca Cola 500ml", "Red Bull 250ml"]
    assert len(inventory_events) == 2
    assert all(event.event_type == "stock-in" for event in inventory_events)
    relevant_audit_logs = [log for log in audit_logs if log.task_run_id == task_run_id]
    receipt_audit_logs = [
        log
        for log in relevant_audit_logs
        if log.action == "inventory.receipt_stock_in_confirmed"
    ]
    assert len(receipt_audit_logs) == 2
    assert all(
        log.metadata_json["confirmation_id"] == confirmation.confirmation_id
        for log in receipt_audit_logs
    )
    assert all(
        log.metadata_json["ocr_document_id"] == ocr_document.ocr_document_id
        for log in receipt_audit_logs
    )

    # Phase 16A: runtime records pilot telemetry for provider calls during receipt OCR processing.
    telemetry_log = next(
        (
            log
            for log in relevant_audit_logs
            if log.scope == "pilot" and log.action == "runtime.provider_telemetry"
        ),
        None,
    )
    assert telemetry_log is not None
    assert telemetry_log.actor_type == "system"
    assert telemetry_log.actor_id == "runtime_system"
    assert telemetry_log.metadata_json["task_type"] == "receipt-ocr"
    assert telemetry_log.metadata_json["capability"] == "ocr"
    assert telemetry_log.metadata_json["outcome"] == "awaiting-confirmation"
    assert telemetry_log.metadata_json["error_code"] is None
    assert "trial_provider_profile" in telemetry_log.metadata_json


def test_acceptance_upload_backed_receipt_flow_uses_ocr_gateway_source_of_truth(
    client,
    monkeypatch,
) -> None:
    from app.services import ocr_documents

    file_name = "receipt-gateway-demo.jpg"
    media_id = _create_and_complete_media_upload(
        client,
        media_type="receipt-image",
        file_name=file_name,
        content_type="image/jpeg",
    )
    expected_public_url = _expected_mock_public_url(media_id=media_id, file_name=file_name)

    class _UploadedOcrGateway:
        def extract_purchase_receipt(self, media_input):
            assert media_input.media_id == media_id
            assert media_input.public_url == expected_public_url
            return OcrExtraction(
                document_type="purchase-receipt",
                provider_name="stub-ocr",
                raw_text="Sprite 500ml x 2",
                line_items=[
                    OcrExtractedLineItem(
                        item_name="Sprite 500ml",
                        quantity=2.0,
                        unit="bottle",
                        price=7.5,
                    )
                ],
                total_amount=15.0,
                low_confidence_fields=["items[0].price"],
                used_fallback=False,
                raw_payload={"provider": "stub-ocr"},
            )

    monkeypatch.setattr(ocr_documents, "get_default_ocr_gateway", lambda: _UploadedOcrGateway())

    task_run_id = _post_session_message(
        client,
        monkeypatch,
        client_request_id="acceptance_upload_backed_receipt_gateway",
        message_type="receipt-image",
        text=None,
        media_ids=[media_id],
    )

    _process_runtime_task_run(task_run_id)
    awaiting_task_run = _get_task_run(client, task_run_id=task_run_id)
    confirmation = _load_confirmation_for_task_run(task_run_id)

    db_session = get_session_factory()()
    try:
        ocr_document = db_session.scalar(select(OcrDocument).where(OcrDocument.task_run_id == task_run_id))
    finally:
        db_session.close()

    assert awaiting_task_run["status"] == "awaiting-confirmation"
    assert awaiting_task_run["task_type"] == "receipt-ocr"
    assert confirmation.fields["provider_name"] == "stub-ocr"
    assert confirmation.fields["total_amount"] == 15.0
    assert confirmation.fields["low_confidence_fields"] == ["items[0].price"]
    assert confirmation.fields["draft_items"] == [
        {
            "line_id": "line_1",
            "item_id": None,
            "item_name": "Sprite 500ml",
            "quantity": 2.0,
            "unit": "bottle",
            "price": 7.5,
        }
    ]
    assert ocr_document is not None
    assert ocr_document.provider_name == "stub-ocr"
    assert ocr_document.low_confidence_fields == ["items[0].price"]


def test_acceptance_upload_backed_voice_query_flow(client, monkeypatch) -> None:
    file_name = "voice-query-demo.m4a"
    media_id = _create_and_complete_media_upload(
        client,
        media_type="audio",
        file_name=file_name,
        content_type="audio/m4a",
    )
    expected_public_url = _expected_mock_public_url(media_id=media_id, file_name=file_name)

    class _UploadedVoiceGateway:
        def transcribe(self, media_input):
            assert media_input.media_ids == [media_id]
            assert media_input.media_urls == [expected_public_url]
            assert media_input.text_hint is None
            return AsrTranscription(text="check stock left for cola", provider="mock", confidence=0.97)

    monkeypatch.setattr(runtime_tools, "get_default_asr_gateway", lambda: _UploadedVoiceGateway())

    task_run_id = _post_session_message(
        client,
        monkeypatch,
        client_request_id="acceptance_upload_backed_voice_query",
        message_type="voice",
        text=None,
        media_ids=[media_id],
    )

    _process_runtime_task_run(task_run_id)
    completed_task_run = _get_task_run(client, task_run_id=task_run_id)
    messages = _get_session_messages(client)

    assert completed_task_run["status"] == "completed"
    assert completed_task_run["task_type"] == "voice-stock-query"
    assert completed_task_run["confirmation_id"] is None
    assert any(
        message["message_type"] == "voice"
        and message["task_run_id"] == task_run_id
        and message["media_ids"] == [media_id]
        for message in messages
    )
    assert any(
        message["task_run_id"] == task_run_id
        and "stock query accepted" in (message["text"] or "").lower()
        for message in messages
    )


def test_acceptance_upload_backed_photo_query_flow_uses_vision_gateway_source_of_truth(
    client,
    monkeypatch,
) -> None:
    from app.runtime import processor as runtime_processor

    file_name = "shelf-demo.jpg"
    media_id = _create_and_complete_media_upload(
        client,
        media_type="image",
        file_name=file_name,
        content_type="image/jpeg",
    )
    expected_public_url = _expected_mock_public_url(media_id=media_id, file_name=file_name)

    def _legacy_bomb(*_args, **_kwargs):
        raise AssertionError("legacy photo recognition path should not be used for photo queries")

    monkeypatch.setattr(runtime_processor, "recognize_and_query_inventory", _legacy_bomb, raising=False)
    monkeypatch.setattr(runtime_router, "recognize_image", _legacy_bomb, raising=False)
    monkeypatch.setattr(runtime_router, "classify_image_task", _legacy_bomb, raising=False)

    class _UploadedVisionGateway:
        def recognize_product(self, media_input):
            assert media_input.media_id == media_id
            assert media_input.public_url == expected_public_url
            return VisionRecognition(
                provider_name="stub-vision",
                candidates=[VisionCandidate(item_name="Fanta 330ml", confidence=0.91, packaging_hint="can")],
                used_fallback=False,
                raw_payload={"provider": "stub"},
            )

    monkeypatch.setattr(runtime_router, "get_default_vision_gateway", lambda: _UploadedVisionGateway())

    task_run_id = _post_session_message(
        client,
        monkeypatch,
        client_request_id="acceptance_upload_backed_photo_query",
        message_type="image",
        text="check shelf stock for fanta",
        media_ids=[media_id],
    )

    _process_runtime_task_run(task_run_id)
    completed_task_run = _get_task_run(client, task_run_id=task_run_id)
    messages = _get_session_messages(client)

    assert completed_task_run["status"] == "completed"
    assert completed_task_run["task_type"] == "photo-stock-query"
    assert completed_task_run["confirmation_id"] is None
    assert "fanta 330ml" in (completed_task_run["result_summary"] or "").lower()
    assert any(
        message["message_type"] == "image"
        and message["task_run_id"] == task_run_id
        and message["media_ids"] == [media_id]
        for message in messages
    )
    assert any(
        message["task_run_id"] == task_run_id
        and "photo query recognized fanta 330ml" in (message["text"] or "").lower()
        for message in messages
    )


def test_acceptance_upload_backed_photo_stock_in_remains_confirmation_first(
    client,
    monkeypatch,
) -> None:
    file_name = "stock-in-demo.jpg"
    media_id = _create_and_complete_media_upload(
        client,
        media_type="image",
        file_name=file_name,
        content_type="image/jpeg",
    )
    expected_public_url = _expected_mock_public_url(media_id=media_id, file_name=file_name)

    class _UploadedVisionGateway:
        def recognize_product(self, media_input):
            assert media_input.media_id == media_id
            assert media_input.public_url == expected_public_url
            return VisionRecognition(
                provider_name="stub-vision",
                candidates=[VisionCandidate(item_name="Sprite 500ml", confidence=0.62, packaging_hint="bottle")],
                used_fallback=False,
                raw_payload={"provider": "stub"},
            )

    monkeypatch.setattr(runtime_router, "get_default_vision_gateway", lambda: _UploadedVisionGateway())

    task_run_id = _post_session_message(
        client,
        monkeypatch,
        client_request_id="acceptance_upload_backed_photo_stock_in",
        message_type="image",
        text="restock sprite bottles",
        media_ids=[media_id],
    )

    _process_runtime_task_run(task_run_id)
    awaiting_task_run = _get_task_run(client, task_run_id=task_run_id)
    confirmation = _load_confirmation_for_task_run(task_run_id)
    messages = _get_session_messages(client)

    assert awaiting_task_run["status"] == "awaiting-confirmation"
    assert awaiting_task_run["task_type"] == "photo-stock-in"
    assert awaiting_task_run["confirmation_id"] == confirmation.confirmation_id
    assert confirmation.fields["draft_fields"]["item_name"] == "Sprite 500ml"
    assert confirmation.fields["draft_fields"]["unit"] == "bottle"
    assert confirmation.fields["draft_fields"]["quantity"] is None
    assert confirmation.fields["draft_fields"]["price"] is None
    assert confirmation.fields["image_media_id"] == media_id
    assert confirmation.fields["provider_name"] == "stub-vision"
    assert confirmation.fields["recognized_confidence"] == 0.62
    assert any(
        message["task_run_id"] == task_run_id
        and "please confirm the stock-in details" in (message["text"] or "").lower()
        for message in messages
    )


def test_acceptance_manual_stock_out_opens_low_stock_alert_and_dashboard_reflects_it(
    client,
    monkeypatch,
) -> None:
    item_id, _ = _create_inventory_item_via_chat_stock_in(
        client,
        monkeypatch,
        item_name="Cola",
        quantity=8,
        client_request_id="acceptance_manual_stock_out_seed",
        low_stock_threshold=Decimal("5"),
    )

    stock_out_response = client.post(
        "/api/v1/inventory-events/stock-out",
        headers=_auth_headers(client),
        json={
            "item_id": item_id,
            "expected_quantity": 8,
            "stock_out_quantity": 4,
            "reason": "Walk-in sale",
        },
    )
    alerts = _get_alerts(client)
    dashboard = _get_dashboard_summary(client)

    db_session = get_session_factory()()
    try:
        item = db_session.get(InventoryItem, item_id)
        stock_out_events = db_session.scalars(
            select(InventoryEvent).where(InventoryEvent.item_id == item_id, InventoryEvent.event_type == "stock-out")
        ).all()
    finally:
        db_session.close()

    assert stock_out_response.status_code == 200
    assert item is not None
    assert item.current_stock == Decimal("4")
    assert len(stock_out_events) == 1
    assert len(alerts) == 1
    assert alerts[0]["item_id"] == item_id
    assert alerts[0]["status"] == "open"
    assert alerts[0]["stock"] == "4.000"
    assert dashboard["open_low_stock_alert_count"] == 1
    assert dashboard["today_stock_in_count"] == 1


def test_acceptance_chat_stock_out_confirmation_flow(client, monkeypatch) -> None:
    item_id, _ = _create_inventory_item_via_chat_stock_in(
        client,
        monkeypatch,
        item_name="Cola",
        quantity=6,
        client_request_id="acceptance_chat_stock_out_seed",
    )
    task_run_id = _post_session_message(
        client,
        monkeypatch,
        client_request_id="acceptance_chat_stock_out",
        message_type="text",
        text="stock out cola for walk in sale",
        media_ids=[],
    )

    _process_runtime_task_run(task_run_id)
    awaiting_task_run = _get_task_run(client, task_run_id=task_run_id)
    confirmation = _load_confirmation_for_task_run(task_run_id)
    approve_payload = _approve_confirmation(
        client,
        confirmation_id=confirmation.confirmation_id,
        fields={
            "item_name": "Cola",
            "stock_out_quantity": 2,
            "reason": "Walk-in sale",
        },
    )
    completed_task_run = _get_task_run(client, task_run_id=task_run_id)
    messages = _get_session_messages(client)

    db_session = get_session_factory()()
    try:
        item = db_session.get(InventoryItem, item_id)
        stock_out_event = db_session.scalar(
            select(InventoryEvent).where(
                InventoryEvent.task_run_id == task_run_id,
                InventoryEvent.event_type == "stock-out",
            )
        )
        audit_log = db_session.scalar(
            select(AuditLog).where(
                AuditLog.task_run_id == task_run_id,
                AuditLog.scope == "inventory",
                AuditLog.action == "inventory.stock_out_submitted",
            )
        )
    finally:
        db_session.close()

    assert awaiting_task_run["status"] == "awaiting-confirmation"
    assert awaiting_task_run["task_type"] == "voice-stock-out"
    assert awaiting_task_run["confirmation_id"] == confirmation.confirmation_id
    assert confirmation.confirmation_type == "stock-out"
    assert approve_payload["status"] == "approved"
    assert completed_task_run["status"] == "completed"
    assert completed_task_run["task_type"] == "voice-stock-out"
    assert item is not None
    assert item.current_stock == Decimal("4")
    assert stock_out_event is not None
    assert stock_out_event.event_type == "stock-out"
    assert audit_log is not None
    assert audit_log.action == "inventory.stock_out_submitted"
    assert any("please confirm the stock-out details" in (message["text"] or "").lower() for message in messages)
    assert any("stock-out committed" in (message["text"] or "").lower() for message in messages)


def test_acceptance_correction_recovery_clears_low_stock_alert(client, monkeypatch) -> None:
    item_id, _ = _create_inventory_item_via_chat_stock_in(
        client,
        monkeypatch,
        item_name="Cola",
        quantity=8,
        client_request_id="acceptance_correction_seed",
        low_stock_threshold=Decimal("5"),
    )
    stock_out_response = client.post(
        "/api/v1/inventory-events/stock-out",
        headers=_auth_headers(client),
        json={
            "item_id": item_id,
            "expected_quantity": 8,
            "stock_out_quantity": 4,
            "reason": "Walk-in sale",
        },
    )
    assert stock_out_response.status_code == 200
    open_alerts = _get_alerts(client)
    assert len(open_alerts) == 1

    correction_response = client.post(
        "/api/v1/inventory-events/corrections",
        headers=_auth_headers(client),
        json={
            "item_id": item_id,
            "expected_quantity": 4,
            "corrected_quantity": 7,
            "reason": "Physical recount after shelf refill",
        },
    )
    alerts_after_correction = _get_alerts(client)

    db_session = get_session_factory()()
    try:
        item = db_session.get(InventoryItem, item_id)
        correction_event = db_session.scalar(
            select(InventoryEvent).where(
                InventoryEvent.item_id == item_id,
                InventoryEvent.event_type == "correction",
            )
        )
        correction_audit = db_session.scalar(
            select(AuditLog).where(
                AuditLog.target_id == item_id,
                AuditLog.action == "inventory.correction_submitted",
            )
        )
        open_alert_records = db_session.scalars(
            select(Alert).where(Alert.item_id == item_id, Alert.status == "open")
        ).all()
    finally:
        db_session.close()

    assert correction_response.status_code == 200
    assert item is not None
    assert item.current_stock == Decimal("7")
    assert correction_event is not None
    assert correction_event.event_type == "correction"
    assert correction_audit is not None
    assert correction_audit.action == "inventory.correction_submitted"
    assert alerts_after_correction == []
    assert open_alert_records == []


def test_acceptance_low_confidence_threshold_change_alters_voice_runtime_outcome(
    client,
    monkeypatch,
) -> None:
    file_name = "threshold-demo.m4a"
    media_id = _create_and_complete_media_upload(
        client,
        media_type="audio",
        file_name=file_name,
        content_type="audio/m4a",
    )
    expected_public_url = _expected_mock_public_url(media_id=media_id, file_name=file_name)

    class _FixedConfidenceGateway:
        def transcribe(self, media_input):
            assert media_input.media_ids == [media_id]
            assert media_input.media_urls == [expected_public_url]
            return AsrTranscription(
                text="check stock left for cola",
                provider="stub-asr",
                confidence=0.83,
            )

    monkeypatch.setattr(runtime_tools, "get_default_asr_gateway", lambda: _FixedConfidenceGateway())

    db_session = get_session_factory()()
    try:
        context = ensure_default_context(db_session)
        context.shop.low_confidence_threshold = Decimal("0.8000")
        db_session.commit()
    finally:
        db_session.close()

    first_task_run_id = _post_session_message(
        client,
        monkeypatch,
        client_request_id="acceptance_threshold_low_allows",
        message_type="voice",
        text=None,
        media_ids=[media_id],
    )
    _process_runtime_task_run(first_task_run_id)
    first_task_run = _get_task_run(client, task_run_id=first_task_run_id)
    assert first_task_run["status"] == "completed"
    assert first_task_run["task_type"] == "voice-stock-query"

    db_session = get_session_factory()()
    try:
        context = ensure_default_context(db_session)
        context.shop.low_confidence_threshold = Decimal("0.9000")
        db_session.commit()
    finally:
        db_session.close()

    second_task_run_id = _post_session_message(
        client,
        monkeypatch,
        client_request_id="acceptance_threshold_high_blocks",
        message_type="voice",
        text=None,
        media_ids=[media_id],
    )
    db_session = get_session_factory()()
    try:
        second_result = process_task_run(db_session, second_task_run_id)
    finally:
        db_session.close()
    assert second_result.status == "failed"
    assert second_result.error_code == "asr_low_confidence"

    second_task_run = _get_task_run(client, task_run_id=second_task_run_id)

    assert second_task_run["status"] == "failed"
    assert second_task_run["error_code"] == "asr_low_confidence"
    assert "below threshold" in (second_task_run["error_message"] or "").lower()
