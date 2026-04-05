from datetime import datetime

import pytest

from app.api.routes import messages as message_routes
from app.db.session import get_session_factory
from app.models import TaskRun
from conftest import auth_headers, login_and_get_token


@pytest.fixture(autouse=True)
def _stub_runtime_dispatch(monkeypatch) -> None:
    monkeypatch.setattr(message_routes, "enqueue_runtime_task", lambda _task_run_id: True)


def _auth_headers(client, monkeypatch=None) -> dict[str, str]:
    return auth_headers(login_and_get_token(client, monkeypatch))


def test_create_message_requires_authorization(client) -> None:
    response = client.post(
        "/api/v1/sessions/sess_default/messages",
        json={
            "message_type": "text",
            "text": "unauthorized",
            "media_ids": [],
            "client_request_id": "route_unauthorized",
        },
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


def test_create_message_returns_message_and_task_ids(client) -> None:
    response = client.post(
        "/api/v1/sessions/sess_default/messages",
        headers=_auth_headers(client),
        json={
            "message_type": "text",
            "text": "restock cola",
            "media_ids": [],
            "client_request_id": "route_create_001",
        },
    )

    assert response.status_code == 201
    payload = response.json()["data"]
    assert payload["message_id"].startswith("msg_")
    assert payload["task_run_id"].startswith("task_")
    assert payload["status"] == "created"


def test_create_message_dispatches_runtime_once_for_fresh_create(client, monkeypatch) -> None:
    dispatched_task_run_ids: list[str] = []

    def fake_enqueue_runtime_task(task_run_id: str) -> bool:
        dispatched_task_run_ids.append(task_run_id)
        return True

    monkeypatch.setattr(message_routes, "enqueue_runtime_task", fake_enqueue_runtime_task)

    response = client.post(
        "/api/v1/sessions/sess_default/messages",
        headers=_auth_headers(client),
        json={
            "message_type": "text",
            "text": "dispatch fresh create",
            "media_ids": [],
            "client_request_id": "route_dispatch_001",
        },
    )

    assert response.status_code == 201
    assert dispatched_task_run_ids == [response.json()["data"]["task_run_id"]]


def test_create_message_marks_task_run_when_initial_dispatch_fails(client, monkeypatch) -> None:
    def fake_enqueue_runtime_task(_task_run_id: str) -> bool:
        return False

    monkeypatch.setattr(message_routes, "enqueue_runtime_task", fake_enqueue_runtime_task)

    response = client.post(
        "/api/v1/sessions/sess_default/messages",
        headers=_auth_headers(client),
        json={
            "message_type": "text",
            "text": "dispatch failure",
            "media_ids": [],
            "client_request_id": "route_dispatch_failed_001",
        },
    )
    task_run_id = response.json()["data"]["task_run_id"]
    task_run_response = client.get(
        f"/api/v1/task-runs/{task_run_id}",
        headers=_auth_headers(client),
    )

    assert response.status_code == 201
    assert task_run_response.status_code == 200
    payload = task_run_response.json()["data"]
    assert payload["task_run_id"] == task_run_id
    assert payload["status"] == "created"
    assert payload["task_type"] == "pending-classification"
    assert payload["error_code"] == "dispatch_failed"
    assert payload["error_message"] == "Runtime dispatch failed; retry the same request to re-enqueue."


def test_create_message_returns_same_ids_on_idempotent_retry(client) -> None:
    headers = _auth_headers(client)
    body = {
        "message_type": "text",
        "text": "duplicate submit",
        "media_ids": [],
        "client_request_id": "route_retry_001",
    }

    first = client.post("/api/v1/sessions/sess_default/messages", headers=headers, json=body)
    second = client.post("/api/v1/sessions/sess_default/messages", headers=headers, json=body)

    assert first.status_code == 201
    assert second.status_code == 200
    assert first.json()["data"]["message_id"] == second.json()["data"]["message_id"]
    assert first.json()["data"]["task_run_id"] == second.json()["data"]["task_run_id"]


def test_create_message_retries_dispatch_on_pending_idempotent_retry(client, monkeypatch) -> None:
    dispatched_task_run_ids: list[str] = []
    dispatch_results = iter([False, True])
    dispatch_failure_time = datetime(2026, 4, 4, 12, 0, 1)
    dispatch_recovery_time = datetime(2026, 4, 4, 12, 0, 2)
    marker_times = iter([dispatch_failure_time, dispatch_recovery_time])

    def fake_enqueue_runtime_task(task_run_id: str) -> bool:
        dispatched_task_run_ids.append(task_run_id)
        return next(dispatch_results)

    monkeypatch.setattr(message_routes, "enqueue_runtime_task", fake_enqueue_runtime_task)
    monkeypatch.setattr(message_routes, "_now", lambda: next(marker_times))

    headers = _auth_headers(client)
    body = {
        "message_type": "text",
        "text": "duplicate dispatch submit",
        "media_ids": [],
        "client_request_id": "route_dispatch_retry_001",
    }

    first = client.post("/api/v1/sessions/sess_default/messages", headers=headers, json=body)
    task_run_id = first.json()["data"]["task_run_id"]
    failed_task_run_response = client.get(
        f"/api/v1/task-runs/{task_run_id}",
        headers=headers,
    )
    second = client.post("/api/v1/sessions/sess_default/messages", headers=headers, json=body)
    recovered_task_run_response = client.get(
        f"/api/v1/task-runs/{task_run_id}",
        headers=headers,
    )

    assert first.status_code == 201
    assert second.status_code == 200
    assert first.json()["data"]["message_id"] == second.json()["data"]["message_id"]
    assert task_run_id == second.json()["data"]["task_run_id"]
    assert failed_task_run_response.status_code == 200
    assert failed_task_run_response.json()["data"]["error_code"] == "dispatch_failed"
    assert (
        failed_task_run_response.json()["data"]["error_message"]
        == "Runtime dispatch failed; retry the same request to re-enqueue."
    )
    assert failed_task_run_response.json()["data"]["updated_at"] == dispatch_failure_time.isoformat()
    assert dispatched_task_run_ids == [
        task_run_id,
        task_run_id,
    ]
    assert recovered_task_run_response.status_code == 200
    assert recovered_task_run_response.json()["data"]["error_code"] is None
    assert recovered_task_run_response.json()["data"]["error_message"] is None
    assert recovered_task_run_response.json()["data"]["updated_at"] == dispatch_recovery_time.isoformat()


def test_create_message_does_not_redispatch_replay_after_task_run_advances(client, monkeypatch) -> None:
    dispatched_task_run_ids: list[str] = []

    def fake_enqueue_runtime_task(task_run_id: str) -> bool:
        dispatched_task_run_ids.append(task_run_id)
        return True

    monkeypatch.setattr(message_routes, "enqueue_runtime_task", fake_enqueue_runtime_task)

    headers = _auth_headers(client)
    body = {
        "message_type": "text",
        "text": "duplicate dispatch submit",
        "media_ids": [],
        "client_request_id": "route_dispatch_retry_advanced_001",
    }

    first = client.post("/api/v1/sessions/sess_default/messages", headers=headers, json=body)
    task_run_id = first.json()["data"]["task_run_id"]

    db_session = get_session_factory()()
    try:
        task_run = db_session.get(TaskRun, task_run_id)
        assert task_run is not None
        task_run.status = "processing"
        db_session.commit()
    finally:
        db_session.close()

    second = client.post("/api/v1/sessions/sess_default/messages", headers=headers, json=body)

    assert first.status_code == 201
    assert second.status_code == 200
    assert dispatched_task_run_ids == [task_run_id]


def test_create_message_returns_conflict_for_payload_drift(client) -> None:
    headers = _auth_headers(client)

    first = client.post(
        "/api/v1/sessions/sess_default/messages",
        headers=headers,
        json={
            "message_type": "text",
            "text": "first",
            "media_ids": [],
            "client_request_id": "route_conflict_001",
        },
    )
    second = client.post(
        "/api/v1/sessions/sess_default/messages",
        headers=headers,
        json={
            "message_type": "text",
            "text": "second",
            "media_ids": [],
            "client_request_id": "route_conflict_001",
        },
    )

    assert first.status_code == 201
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "idempotency_conflict"


def test_create_message_returns_404_for_unknown_session(client) -> None:
    response = client.post(
        "/api/v1/sessions/sess_missing/messages",
        headers=_auth_headers(client),
        json={
            "message_type": "text",
            "text": "missing",
            "media_ids": [],
            "client_request_id": "route_missing_session",
        },
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "session_not_found"


def test_create_message_rejects_media_that_is_not_uploaded(client) -> None:
    upload_response = client.post(
        "/api/v1/media-uploads",
        headers=_auth_headers(client),
        json={
            "media_type": "audio",
            "file_name": "voice.m4a",
            "content_type": "audio/m4a",
            "size_bytes": 1024,
        },
    )
    media_id = upload_response.json()["data"]["media_id"]

    response = client.post(
        "/api/v1/sessions/sess_default/messages",
        headers=_auth_headers(client),
        json={
            "message_type": "voice",
            "text": "restock apples today",
            "media_ids": [media_id],
            "client_request_id": "route_media_not_ready",
        },
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "media_not_ready"


def test_list_messages_returns_newest_first_with_next_cursor(client) -> None:
    headers = _auth_headers(client)
    client.post(
        "/api/v1/sessions/sess_default/messages",
        headers=headers,
        json={"message_type": "text", "text": "one", "media_ids": [], "client_request_id": "route_page_1"},
    )
    client.post(
        "/api/v1/sessions/sess_default/messages",
        headers=headers,
        json={"message_type": "text", "text": "two", "media_ids": [], "client_request_id": "route_page_2"},
    )

    first_page = client.get(
        "/api/v1/sessions/sess_default/messages?limit=1",
        headers=headers,
    )

    assert first_page.status_code == 200
    assert first_page.json()["data"][0]["text"] == "two"
    assert first_page.json()["meta"]["next_cursor"] is not None
