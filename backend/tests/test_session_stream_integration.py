from fastapi.testclient import TestClient
from time import monotonic

from app.api.routes import messages as message_routes
from conftest import auth_headers, load_create_app, login_and_get_token, upgrade_test_database


def _create_websocket_client(monkeypatch, tmp_path, *, keepalive_seconds: str = "0.001") -> TestClient:
    database_url = f"sqlite:///{(tmp_path / 'stream-integration.db').as_posix()}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("SESSION_STREAM_KEEPALIVE_SECONDS", keepalive_seconds)
    upgrade_test_database(database_url)
    return TestClient(load_create_app()())


def _receive_business_event(websocket, *, timeout_seconds: float = 2.0):
    deadline = monotonic() + timeout_seconds
    while monotonic() < deadline:
        event = websocket.receive_json()
        if event["event_type"] not in {"session.ready", "stream.keepalive"}:
            return event
    raise AssertionError(
        f"Expected a business session stream event within {timeout_seconds} seconds"
    )


def _auth_headers(client, monkeypatch=None) -> dict[str, str]:
    return auth_headers(login_and_get_token(client, monkeypatch))


def test_receive_business_event_waits_past_many_keepalives() -> None:
    class _FakeWebSocket:
        def __init__(self, events: list[dict[str, object]]) -> None:
            self._events = list(events)

        def receive_json(self) -> dict[str, object]:
            if not self._events:
                raise AssertionError("No more websocket messages")
            return self._events.pop(0)

    keepalive_events = [{"event_type": "stream.keepalive"} for _ in range(12)]
    business_event = {"event_type": "message.created", "data": {"preview_text": "restock cola"}}
    websocket = _FakeWebSocket([*keepalive_events, business_event])

    received = _receive_business_event(websocket)

    assert received["event_type"] == "message.created"


def test_session_stream_ws_receives_message_created_after_post_message(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(message_routes, "enqueue_runtime_task", lambda _task_run_id: True)

    with _create_websocket_client(monkeypatch, tmp_path) as client:
        token = login_and_get_token(client, monkeypatch)
        bootstrap_response = client.post(
            "/api/v1/sessions/bootstrap",
            headers=auth_headers(token),
        )
        session_id = bootstrap_response.json()["data"]["session_id"]

        with client.websocket_connect(
            f"/api/v1/ws/sessions/{session_id}?token={token}"
        ) as websocket:
            ready_event = websocket.receive_json()
            create_response = client.post(
                f"/api/v1/sessions/{session_id}/messages",
                headers=auth_headers(token),
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


def test_session_stream_ws_replays_same_backlog_to_independent_subscribers(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(message_routes, "enqueue_runtime_task", lambda _task_run_id: True)

    with _create_websocket_client(monkeypatch, tmp_path) as client:
        token = login_and_get_token(client, monkeypatch)
        bootstrap_response = client.post(
            "/api/v1/sessions/bootstrap",
            headers=auth_headers(token),
        )
        session_id = bootstrap_response.json()["data"]["session_id"]

        create_response = client.post(
            f"/api/v1/sessions/{session_id}/messages",
            headers=auth_headers(token),
            json={
                "message_type": "text",
                "text": "restock cola",
                "media_ids": [],
                "client_request_id": "ws_independent_replay",
            },
        )

        with client.websocket_connect(
            f"/api/v1/ws/sessions/{session_id}?token={token}&after_seq=0"
        ) as first_websocket:
            first_websocket.receive_json()
            first_replayed_event = _receive_business_event(first_websocket)

        with client.websocket_connect(
            f"/api/v1/ws/sessions/{session_id}?token={token}&after_seq=0"
        ) as second_websocket:
            second_websocket.receive_json()
            second_replayed_event = _receive_business_event(second_websocket)

    assert create_response.status_code == 201
    assert first_replayed_event["event_type"] == "message.created"
    assert second_replayed_event["event_type"] == "message.created"
    assert first_replayed_event["seq"] == second_replayed_event["seq"] == 1
