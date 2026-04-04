import pytest

from app.api.routes import messages as message_routes


@pytest.fixture(autouse=True)
def _stub_runtime_dispatch(monkeypatch) -> None:
    monkeypatch.setattr(message_routes, "enqueue_runtime_task", lambda _task_run_id: True)


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
        headers={"Authorization": "Bearer mock_owner_token"},
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
        headers={"Authorization": "Bearer mock_owner_token"},
        json={
            "message_type": "text",
            "text": "dispatch fresh create",
            "media_ids": [],
            "client_request_id": "route_dispatch_001",
        },
    )

    assert response.status_code == 201
    assert dispatched_task_run_ids == [response.json()["data"]["task_run_id"]]


def test_create_message_returns_same_ids_on_idempotent_retry(client) -> None:
    headers = {"Authorization": "Bearer mock_owner_token"}
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


def test_create_message_does_not_dispatch_again_on_idempotent_retry(client, monkeypatch) -> None:
    dispatched_task_run_ids: list[str] = []

    def fake_enqueue_runtime_task(task_run_id: str) -> bool:
        dispatched_task_run_ids.append(task_run_id)
        return True

    monkeypatch.setattr(message_routes, "enqueue_runtime_task", fake_enqueue_runtime_task)

    headers = {"Authorization": "Bearer mock_owner_token"}
    body = {
        "message_type": "text",
        "text": "duplicate dispatch submit",
        "media_ids": [],
        "client_request_id": "route_dispatch_retry_001",
    }

    first = client.post("/api/v1/sessions/sess_default/messages", headers=headers, json=body)
    second = client.post("/api/v1/sessions/sess_default/messages", headers=headers, json=body)

    assert first.status_code == 201
    assert second.status_code == 200
    assert dispatched_task_run_ids == [first.json()["data"]["task_run_id"]]


def test_create_message_returns_conflict_for_payload_drift(client) -> None:
    headers = {"Authorization": "Bearer mock_owner_token"}

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
        headers={"Authorization": "Bearer mock_owner_token"},
        json={
            "message_type": "text",
            "text": "missing",
            "media_ids": [],
            "client_request_id": "route_missing_session",
        },
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "session_not_found"


def test_list_messages_returns_newest_first_with_next_cursor(client) -> None:
    headers = {"Authorization": "Bearer mock_owner_token"}
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
