from decimal import Decimal

from sqlalchemy import select

from app.api.routes import messages as message_routes
from app.db.session import get_session_factory
from app.models import AuditLog, Confirmation, InventoryEvent, InventoryItem, MediaUpload, Message, OcrDocument, TaskRun
from app.runtime.processor import process_task_run
from app.services.bootstrap import ensure_default_context
from conftest import auth_headers, login_and_get_token

def _auth_headers(client, monkeypatch=None) -> dict[str, str]:
    return auth_headers(login_and_get_token(client, monkeypatch))


def _create_runtime_pending_confirmation(
    client,
    monkeypatch,
    *,
    client_request_id: str,
) -> tuple[str, str]:
    monkeypatch.setattr(message_routes, "enqueue_runtime_task", lambda _task_run_id: True)

    create_response = client.post(
        "/api/v1/sessions/sess_default/messages",
        headers=_auth_headers(client),
        json={
            "message_type": "text",
            "text": "restock apples today",
            "media_ids": [],
            "client_request_id": client_request_id,
        },
    )
    assert create_response.status_code == 201

    task_run_id = create_response.json()["data"]["task_run_id"]
    db_session = get_session_factory()()
    try:
        result = process_task_run(db_session, task_run_id)
        confirmation = db_session.scalar(
            select(Confirmation).where(Confirmation.task_run_id == task_run_id)
        )
        assert result.status == "awaiting-confirmation"
        assert confirmation is not None
        return confirmation.confirmation_id, task_run_id
    finally:
        db_session.close()


def _create_runtime_pending_stock_out_confirmation(
    client,
    monkeypatch,
    *,
    client_request_id: str,
) -> tuple[str, str]:
    monkeypatch.setattr(message_routes, "enqueue_runtime_task", lambda _task_run_id: True)

    create_response = client.post(
        "/api/v1/sessions/sess_default/messages",
        headers=_auth_headers(client),
        json={
            "message_type": "text",
            "text": "stock out cola for walk in sale",
            "media_ids": [],
            "client_request_id": client_request_id,
        },
    )
    assert create_response.status_code == 201

    task_run_id = create_response.json()["data"]["task_run_id"]
    db_session = get_session_factory()()
    try:
        result = process_task_run(db_session, task_run_id)
        confirmation = db_session.scalar(
            select(Confirmation).where(Confirmation.task_run_id == task_run_id)
        )
        assert result.status == "awaiting-confirmation"
        assert confirmation is not None
        assert confirmation.confirmation_type == "stock-out"
        return confirmation.confirmation_id, task_run_id
    finally:
        db_session.close()


def _seed_uploaded_media(media_id: str, media_type: str) -> None:
    db_session = get_session_factory()()
    try:
        context = ensure_default_context(db_session)
        db_session.add(
            MediaUpload(
                media_id=media_id,
                shop_id=context.shop.shop_id,
                uploader_actor_type="owner",
                uploader_actor_id="owner_default",
                media_type=media_type,
                file_name=f"{media_id}.bin",
                content_type="application/octet-stream",
                size_bytes=1024,
                status="uploaded",
                upload_url=f"https://mock.example/uploads/{media_id}",
                public_url=f"https://mock.example/media/{media_id}",
                checksum_sha256="receipt-seeded-checksum",
                uploaded_at=context.session.created_at,
                created_at=context.session.created_at,
                updated_at=context.session.created_at,
            )
        )
        db_session.commit()
    finally:
        db_session.close()


def _seed_inventory_item(
    *,
    item_id: str,
    name: str,
    unit: str,
    stock: str,
    price: str,
) -> None:
    db_session = get_session_factory()()
    try:
        context = ensure_default_context(db_session)
        db_session.add(
            InventoryItem(
                item_id=item_id,
                shop_id=context.shop.shop_id,
                sku=None,
                name=name,
                category=None,
                barcode=None,
                default_unit=unit,
                current_stock=Decimal(stock),
                current_price=Decimal(price),
                low_stock_threshold=context.shop.default_low_stock_threshold,
                image_media_id=None,
                is_active=True,
                created_at=context.shop.created_at,
                updated_at=context.shop.updated_at,
            )
        )
        db_session.commit()
    finally:
        db_session.close()


def _create_runtime_pending_receipt_confirmation(
    client,
    monkeypatch,
    *,
    client_request_id: str,
) -> tuple[str, str, str]:
    monkeypatch.setattr(message_routes, "enqueue_runtime_task", lambda _task_run_id: True)
    _seed_uploaded_media("receipt_demo", "receipt-image")

    create_response = client.post(
        "/api/v1/sessions/sess_default/messages",
        headers=_auth_headers(client),
        json={
            "message_type": "receipt-image",
            "text": None,
            "media_ids": ["receipt_demo"],
            "client_request_id": client_request_id,
        },
    )
    assert create_response.status_code == 201

    task_run_id = create_response.json()["data"]["task_run_id"]
    db_session = get_session_factory()()
    try:
        result = process_task_run(db_session, task_run_id)
        confirmation = db_session.scalar(
            select(Confirmation).where(Confirmation.task_run_id == task_run_id)
        )
        ocr_document = db_session.scalar(
            select(OcrDocument).where(OcrDocument.task_run_id == task_run_id)
        )
        assert result.status == "awaiting-confirmation"
        assert confirmation is not None
        assert ocr_document is not None
        return confirmation.confirmation_id, task_run_id, ocr_document.ocr_document_id
    finally:
        db_session.close()


def test_list_confirmations_returns_runtime_created_pending_confirmations_newest_first(
    client,
    monkeypatch,
) -> None:
    older_confirmation_id, older_task_run_id = _create_runtime_pending_confirmation(
        client,
        monkeypatch,
        client_request_id="confirmations_api_list_older",
    )
    newer_confirmation_id, newer_task_run_id = _create_runtime_pending_confirmation(
        client,
        monkeypatch,
        client_request_id="confirmations_api_list_newer",
    )

    response = client.get(
        "/api/v1/confirmations?status=pending&limit=20",
        headers=_auth_headers(client),
    )

    assert response.status_code == 200
    response_json = response.json()
    payload = response_json["data"]
    assert response_json["meta"]["count"] == 2
    assert [item["confirmation_id"] for item in payload[:2]] == [
        newer_confirmation_id,
        older_confirmation_id,
    ]
    assert payload[0]["task_run_id"] == newer_task_run_id
    assert payload[0]["session_id"] == "sess_default"
    assert payload[0]["status"] == "pending"
    assert payload[1]["task_run_id"] == older_task_run_id


def test_list_confirmations_defaults_to_pending_and_excludes_approved_items(
    client,
    monkeypatch,
) -> None:
    approved_confirmation_id, _ = _create_runtime_pending_confirmation(
        client,
        monkeypatch,
        client_request_id="confirmations_api_default_status_approved",
    )
    pending_confirmation_id, pending_task_run_id = _create_runtime_pending_confirmation(
        client,
        monkeypatch,
        client_request_id="confirmations_api_default_status_pending",
    )

    approve_response = client.post(
        f"/api/v1/confirmations/{approved_confirmation_id}/approve",
        headers=_auth_headers(client),
        json={
            "fields": {
                "item_name": "Apple",
                "quantity": 2,
                "unit": "box",
                "price": 12.5,
            }
        },
    )
    response = client.get(
        "/api/v1/confirmations?limit=20",
        headers=_auth_headers(client),
    )

    assert approve_response.status_code == 200
    assert response.status_code == 200
    response_json = response.json()
    payload = response_json["data"]
    assert response_json["meta"]["count"] == 1
    assert [item["confirmation_id"] for item in payload] == [pending_confirmation_id]
    assert payload[0]["task_run_id"] == pending_task_run_id
    assert payload[0]["status"] == "pending"


def test_approve_confirmation_completes_task_run_writes_runtime_message_and_projects_confirmation_id(
    client,
    monkeypatch,
) -> None:
    confirmation_id, task_run_id = _create_runtime_pending_confirmation(
        client,
        monkeypatch,
        client_request_id="confirmations_api_approve",
    )

    approve_response = client.post(
        f"/api/v1/confirmations/{confirmation_id}/approve",
        headers=_auth_headers(client),
        json={
            "fields": {
                "item_name": "Apple",
                "quantity": 3,
                "unit": "box",
                "price": 18.5,
            }
        },
    )
    task_run_response = client.get(
        f"/api/v1/task-runs/{task_run_id}",
        headers=_auth_headers(client),
    )

    db_session = get_session_factory()()
    try:
        confirmation = db_session.get(Confirmation, confirmation_id)
        task_run = db_session.get(TaskRun, task_run_id)
        inventory_items = db_session.scalars(select(InventoryItem)).all()
        inventory_events = db_session.scalars(select(InventoryEvent)).all()
        audit_logs = db_session.scalars(select(AuditLog)).all()
        runtime_messages = db_session.scalars(
            select(Message)
            .where(Message.task_run_id == task_run_id, Message.actor_type == "system")
            .order_by(Message.created_at.asc(), Message.message_id.asc())
        ).all()
    finally:
        db_session.close()

    assert approve_response.status_code == 200
    approve_payload = approve_response.json()["data"]
    assert approve_payload["confirmation_id"] == confirmation_id
    assert approve_payload["status"] == "approved"
    assert approve_payload["resolution_payload"] == {
        "fields": {
            "item_name": "Apple",
            "quantity": 3,
            "unit": "box",
            "price": 18.5,
        }
    }
    assert confirmation is not None
    assert confirmation.status == "approved"
    assert task_run is not None
    assert task_run.status == "completed"
    assert task_run.completed_at is not None
    assert len(inventory_items) == 1
    assert inventory_items[0].name == "Apple"
    assert inventory_items[0].current_stock == Decimal("3")
    assert len(inventory_events) == 1
    assert inventory_events[0].event_type == "stock-in"
    assert len(audit_logs) == 1
    assert audit_logs[0].action == "inventory.stock_in_confirmed"
    assert audit_logs[0].metadata_json["confirmation_id"] == confirmation_id
    assert len(runtime_messages) == 2
    assert runtime_messages[-1].actor_id == "runtime_system"
    assert "committed" in (runtime_messages[-1].text or "").lower()
    assert task_run_response.status_code == 200
    assert task_run_response.json()["data"]["confirmation_id"] == confirmation_id


def test_approve_receipt_confirmation_commits_all_lines_and_projects_confirmation_id(
    client,
    monkeypatch,
) -> None:
    confirmation_id, task_run_id, ocr_document_id = _create_runtime_pending_receipt_confirmation(
        client,
        monkeypatch,
        client_request_id="confirmations_api_receipt_approve",
    )

    approve_response = client.post(
        f"/api/v1/confirmations/{confirmation_id}/approve",
        headers=_auth_headers(client),
        json={
            "fields": {
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
            }
        },
    )
    task_run_response = client.get(
        f"/api/v1/task-runs/{task_run_id}",
        headers=_auth_headers(client),
    )

    db_session = get_session_factory()()
    try:
        confirmation = db_session.get(Confirmation, confirmation_id)
        task_run = db_session.get(TaskRun, task_run_id)
        inventory_items = db_session.scalars(
            select(InventoryItem).order_by(InventoryItem.name.asc())
        ).all()
        inventory_events = db_session.scalars(
            select(InventoryEvent).order_by(InventoryEvent.created_at.asc(), InventoryEvent.inventory_event_id.asc())
        ).all()
        audit_logs = db_session.scalars(
            select(AuditLog).order_by(AuditLog.created_at.asc(), AuditLog.audit_log_id.asc())
        ).all()
        runtime_messages = db_session.scalars(
            select(Message)
            .where(Message.task_run_id == task_run_id, Message.actor_type == "system")
            .order_by(Message.created_at.asc(), Message.message_id.asc())
        ).all()
    finally:
        db_session.close()

    assert approve_response.status_code == 200
    approve_payload = approve_response.json()["data"]
    assert approve_payload["confirmation_id"] == confirmation_id
    assert approve_payload["status"] == "approved"
    assert approve_payload["resolution_payload"] == {
        "fields": {
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
        }
    }
    assert confirmation is not None
    assert confirmation.status == "approved"
    assert task_run is not None
    assert task_run.status == "completed"
    assert task_run.completed_at is not None
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
    assert all(log.metadata_json["confirmation_id"] == confirmation_id for log in receipt_audit_logs)
    assert all(log.metadata_json["ocr_document_id"] == ocr_document_id for log in receipt_audit_logs)

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
    assert len(runtime_messages) == 2
    assert runtime_messages[-1].actor_id == "runtime_system"
    assert "2 line" in (runtime_messages[-1].text or "").lower()
    assert task_run_response.status_code == 200
    assert task_run_response.json()["data"]["confirmation_id"] == confirmation_id


def test_approve_stock_out_confirmation_commits_inventory_event_and_projects_confirmation_id(
    client,
    monkeypatch,
) -> None:
    _seed_inventory_item(
        item_id="item_stock_out_confirmation_api",
        name="Cola",
        unit="box",
        stock="6",
        price="18.5",
    )
    confirmation_id, task_run_id = _create_runtime_pending_stock_out_confirmation(
        client,
        monkeypatch,
        client_request_id="confirmations_api_stock_out_approve",
    )

    approve_response = client.post(
        f"/api/v1/confirmations/{confirmation_id}/approve",
        headers=_auth_headers(client),
        json={
            "fields": {
                "item_name": "Cola",
                "stock_out_quantity": 2,
                "reason": "Walk-in sale",
            }
        },
    )
    task_run_response = client.get(
        f"/api/v1/task-runs/{task_run_id}",
        headers=_auth_headers(client),
    )

    db_session = get_session_factory()()
    try:
        confirmation = db_session.get(Confirmation, confirmation_id)
        task_run = db_session.get(TaskRun, task_run_id)
        inventory_item = db_session.get(InventoryItem, "item_stock_out_confirmation_api")
        inventory_events = db_session.scalars(select(InventoryEvent)).all()
        audit_logs = db_session.scalars(select(AuditLog)).all()
        runtime_messages = db_session.scalars(
            select(Message)
            .where(Message.task_run_id == task_run_id, Message.actor_type == "system")
            .order_by(Message.created_at.asc(), Message.message_id.asc())
        ).all()
    finally:
        db_session.close()

    assert approve_response.status_code == 200
    approve_payload = approve_response.json()["data"]
    assert approve_payload["confirmation_id"] == confirmation_id
    assert approve_payload["status"] == "approved"
    assert approve_payload["resolution_payload"] == {
        "fields": {
            "item_name": "Cola",
            "stock_out_quantity": 2,
            "reason": "Walk-in sale",
        }
    }
    assert confirmation is not None
    assert confirmation.status == "approved"
    assert task_run is not None
    assert task_run.status == "completed"
    assert task_run.completed_at is not None
    assert inventory_item is not None
    assert inventory_item.current_stock == Decimal("4")
    assert len(inventory_events) == 1
    assert inventory_events[0].event_type == "stock-out"
    assert inventory_events[0].quantity_delta == Decimal("-2")
    assert len(audit_logs) == 1
    assert audit_logs[0].action == "inventory.stock_out_submitted"
    assert audit_logs[0].metadata_json["confirmation_id"] == confirmation_id
    assert len(runtime_messages) == 2
    assert "stock-out committed" in (runtime_messages[-1].text or "").lower()
    assert task_run_response.status_code == 200
    assert task_run_response.json()["data"]["confirmation_id"] == confirmation_id


def test_approve_stock_out_confirmation_returns_validation_error_for_insufficient_stock(
    client,
    monkeypatch,
) -> None:
    _seed_inventory_item(
        item_id="item_stock_out_confirmation_insufficient",
        name="Cola",
        unit="box",
        stock="1",
        price="18.5",
    )
    confirmation_id, _ = _create_runtime_pending_stock_out_confirmation(
        client,
        monkeypatch,
        client_request_id="confirmations_api_stock_out_insufficient",
    )

    response = client.post(
        f"/api/v1/confirmations/{confirmation_id}/approve",
        headers=_auth_headers(client),
        json={
            "fields": {
                "item_name": "Cola",
                "stock_out_quantity": 3,
                "reason": "Walk-in sale",
            }
        },
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "confirmation_fields_invalid"


def test_reject_confirmation_rejects_task_run_and_writes_runtime_message(
    client,
    monkeypatch,
) -> None:
    confirmation_id, task_run_id = _create_runtime_pending_confirmation(
        client,
        monkeypatch,
        client_request_id="confirmations_api_reject",
    )

    reject_response = client.post(
        f"/api/v1/confirmations/{confirmation_id}/reject",
        headers=_auth_headers(client),
    )

    db_session = get_session_factory()()
    try:
        confirmation = db_session.get(Confirmation, confirmation_id)
        task_run = db_session.get(TaskRun, task_run_id)
        runtime_messages = db_session.scalars(
            select(Message)
            .where(Message.task_run_id == task_run_id, Message.actor_type == "system")
            .order_by(Message.created_at.asc(), Message.message_id.asc())
        ).all()
    finally:
        db_session.close()

    assert reject_response.status_code == 200
    reject_payload = reject_response.json()["data"]
    assert reject_payload["confirmation_id"] == confirmation_id
    assert reject_payload["status"] == "rejected"
    assert reject_payload["resolution_payload"] is None
    assert confirmation is not None
    assert confirmation.status == "rejected"
    assert task_run is not None
    assert task_run.status == "rejected"
    assert task_run.completed_at is not None
    assert len(runtime_messages) == 2
    assert runtime_messages[-1].actor_id == "runtime_system"
    assert "reject" in (runtime_messages[-1].text or "").lower()


def test_list_confirmations_requires_authorization(client) -> None:
    response = client.get("/api/v1/confirmations?status=pending&limit=20")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


def test_approve_confirmation_requires_non_empty_fields(client, monkeypatch) -> None:
    confirmation_id, _ = _create_runtime_pending_confirmation(
        client,
        monkeypatch,
        client_request_id="confirmations_api_validation",
    )

    response = client.post(
        f"/api/v1/confirmations/{confirmation_id}/approve",
        headers=_auth_headers(client),
        json={"fields": {}},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "confirmation_fields_invalid"


def test_approve_receipt_confirmation_requires_non_empty_items(client, monkeypatch) -> None:
    confirmation_id, _, _ = _create_runtime_pending_receipt_confirmation(
        client,
        monkeypatch,
        client_request_id="confirmations_api_receipt_validation",
    )

    response = client.post(
        f"/api/v1/confirmations/{confirmation_id}/approve",
        headers=_auth_headers(client),
        json={"fields": {"items": []}},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "confirmation_fields_invalid"


def test_approve_confirmation_returns_404_for_unknown_item_id(client, monkeypatch) -> None:
    confirmation_id, _ = _create_runtime_pending_confirmation(
        client,
        monkeypatch,
        client_request_id="confirmations_api_missing_item",
    )

    response = client.post(
        f"/api/v1/confirmations/{confirmation_id}/approve",
        headers=_auth_headers(client),
        json={
            "fields": {
                "item_id": "item_missing",
                "quantity": 2,
                "unit": "box",
                "price": 18.5,
            }
        },
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "inventory_item_not_found"


def test_approve_confirmation_returns_409_for_unit_mismatch(client, monkeypatch) -> None:
    confirmation_id, _ = _create_runtime_pending_confirmation(
        client,
        monkeypatch,
        client_request_id="confirmations_api_unit_mismatch",
    )

    db_session = get_session_factory()()
    try:
        context = ensure_default_context(db_session)
        db_session.add(
            InventoryItem(
                item_id="item_unit_mismatch_api",
                shop_id=context.shop.shop_id,
                sku=None,
                name="Apple",
                category=None,
                barcode=None,
                default_unit="box",
                current_stock=Decimal("5"),
                current_price=Decimal("10"),
                low_stock_threshold=context.shop.default_low_stock_threshold,
                image_media_id=None,
                is_active=True,
                created_at=context.shop.created_at,
                updated_at=context.shop.updated_at,
            )
        )
        db_session.commit()
    finally:
        db_session.close()

    response = client.post(
        f"/api/v1/confirmations/{confirmation_id}/approve",
        headers=_auth_headers(client),
        json={
            "fields": {
                "item_name": "Apple",
                "quantity": 2,
                "unit": "bottle",
                "price": 18.5,
            }
        },
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "inventory_unit_mismatch"
