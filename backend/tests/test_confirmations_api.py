from sqlalchemy import select

from app.api.routes import messages as message_routes
from app.db.session import get_session_factory
from app.models import Confirmation, Message, TaskRun
from app.runtime.processor import process_task_run


AUTH_HEADERS = {"Authorization": "Bearer mock_owner_token"}


def _create_runtime_pending_confirmation(
    client,
    monkeypatch,
    *,
    client_request_id: str,
) -> tuple[str, str]:
    monkeypatch.setattr(message_routes, "enqueue_runtime_task", lambda _task_run_id: True)

    create_response = client.post(
        "/api/v1/sessions/sess_default/messages",
        headers=AUTH_HEADERS,
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
        headers=AUTH_HEADERS,
    )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert [item["confirmation_id"] for item in payload[:2]] == [
        newer_confirmation_id,
        older_confirmation_id,
    ]
    assert payload[0]["task_run_id"] == newer_task_run_id
    assert payload[0]["session_id"] == "sess_default"
    assert payload[0]["status"] == "pending"
    assert payload[1]["task_run_id"] == older_task_run_id


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
        headers=AUTH_HEADERS,
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
        headers=AUTH_HEADERS,
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
    assert len(runtime_messages) == 2
    assert runtime_messages[-1].actor_id == "runtime_system"
    assert "approved" in (runtime_messages[-1].text or "").lower()
    assert task_run_response.status_code == 200
    assert task_run_response.json()["data"]["confirmation_id"] == confirmation_id


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
        headers=AUTH_HEADERS,
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
        headers=AUTH_HEADERS,
        json={"fields": {}},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
