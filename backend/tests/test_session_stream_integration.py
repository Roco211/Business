from fastapi.testclient import TestClient

from app.api.routes import messages as message_routes
from conftest import load_create_app, upgrade_test_database


def _create_websocket_client(monkeypatch, tmp_path, *, keepalive_seconds: str = "0.001") -> TestClient:
    database_url = f"sqlite:///{(tmp_path / 'stream-integration.db').as_posix()}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("SESSION_STREAM_KEEPALIVE_SECONDS", keepalive_seconds)
    upgrade_test_database(database_url)
    return TestClient(load_create_app()())


def _receive_business_event(websocket):
    for _ in range(10):
        event = websocket.receive_json()
        if event["event_type"] not in {"session.ready", "stream.keepalive"}:
            return event
    raise AssertionError("Expected a business session stream event")


def test_session_stream_ws_receives_message_created_after_post_message(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(message_routes, "enqueue_runtime_task", lambda _task_run_id: True)

    with _create_websocket_client(monkeypatch, tmp_path) as client:
        bootstrap_response = client.post(
            "/api/v1/sessions/bootstrap",
            headers={"Authorization": "Bearer mock_owner_token"},
        )
        session_id = bootstrap_response.json()["data"]["session_id"]

        with client.websocket_connect(
            f"/api/v1/ws/sessions/{session_id}?token=mock_owner_token"
        ) as websocket:
            ready_event = websocket.receive_json()
            create_response = client.post(
                f"/api/v1/sessions/{session_id}/messages",
                headers={"Authorization": "Bearer mock_owner_token"},
                json={
                    "message_type": "text",
                    "text": "restock cola",
                    "media_ids": [],
                    "client_request_id": "ws_message_created",
                },
            )
            business_event = _receive_business_event(websocket)

    assert ready_event["event_type"] == "session.ready"
    assert create_response.status_code == 201
    assert business_event["event_type"] == "message.created"
    assert business_event["session_id"] == session_id
    assert business_event["seq"] == 1
    assert business_event["data"]["preview_text"] == "restock cola"
