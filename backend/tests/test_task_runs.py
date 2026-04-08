from app.api.routes import messages as message_routes
from app.db.session import get_session_factory
from app.runtime.processor import process_task_run
from conftest import auth_headers, login_and_get_token


def _auth_headers(client, monkeypatch=None) -> dict[str, str]:
    return auth_headers(login_and_get_token(client, monkeypatch))


def test_get_task_run_requires_authorization(client) -> None:
    response = client.get("/api/v1/task-runs/task_missing")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


def test_get_task_run_returns_runtime_state_shape(client, monkeypatch) -> None:
    monkeypatch.setattr(message_routes, "enqueue_runtime_task", lambda _task_run_id: True)

    create_response = client.post(
        "/api/v1/sessions/sess_default/messages",
        headers=_auth_headers(client),
        json={
            "message_type": "text",
            "text": "poll task state",
            "media_ids": [],
            "client_request_id": "task_run_route_001",
        },
    )
    task_run_id = create_response.json()["data"]["task_run_id"]

    response = client.get(
        f"/api/v1/task-runs/{task_run_id}",
        headers=_auth_headers(client),
    )

    assert create_response.status_code == 201
    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["task_run_id"] == task_run_id
    assert payload["session_id"] == "sess_default"
    assert payload["source_message_id"].startswith("msg_")
    assert payload["task_type"] == "pending-classification"
    assert payload["status"] == "created"
    assert payload["assigned_employee_id"] is None
    assert payload["result_summary"] is None
    assert payload["error_code"] is None
    assert payload["error_message"] is None
    assert payload["confirmation_id"] is None
    assert payload["created_at"] is not None
    assert payload["updated_at"] is not None
    assert payload["completed_at"] is None


def test_get_task_run_projects_pending_confirmation_id(client, monkeypatch) -> None:
    monkeypatch.setattr(message_routes, "enqueue_runtime_task", lambda _task_run_id: True)

    create_response = client.post(
        "/api/v1/sessions/sess_default/messages",
        headers=_auth_headers(client),
        json={
            "message_type": "text",
            "text": "restock apples today",
            "media_ids": [],
            "client_request_id": "task_run_route_pending_confirmation_001",
        },
    )
    task_run_id = create_response.json()["data"]["task_run_id"]

    db_session = get_session_factory()()
    try:
        process_result = process_task_run(db_session, task_run_id)
    finally:
        db_session.close()

    response = client.get(
        f"/api/v1/task-runs/{task_run_id}",
        headers=_auth_headers(client),
    )

    assert create_response.status_code == 201
    assert process_result.status == "awaiting-confirmation"
    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["task_run_id"] == task_run_id
    assert payload["status"] == "awaiting-confirmation"
    assert payload["confirmation_id"].startswith("conf_")


def test_get_task_run_returns_not_found_for_unknown_task(client) -> None:
    response = client.get(
        "/api/v1/task-runs/task_missing",
        headers=_auth_headers(client),
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "task_run_not_found"
