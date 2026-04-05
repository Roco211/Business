import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from conftest import load_create_app, upgrade_test_database


def _create_websocket_client(monkeypatch, tmp_path, *, keepalive_seconds: str = "0.01") -> TestClient:
    database_url = f"sqlite:///{(tmp_path / 'ws.db').as_posix()}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("SESSION_STREAM_KEEPALIVE_SECONDS", keepalive_seconds)
    upgrade_test_database(database_url)
    return TestClient(load_create_app()())


def test_session_stream_ws_rejects_invalid_token(monkeypatch, tmp_path) -> None:
    with _create_websocket_client(monkeypatch, tmp_path) as client:
        with client.websocket_connect("/api/v1/ws/sessions/sess_default?token=bad_token") as websocket:
            with pytest.raises(WebSocketDisconnect) as disconnect:
                websocket.receive_json()

    assert disconnect.value.code == 4401


def test_session_stream_ws_rejects_missing_session(monkeypatch, tmp_path) -> None:
    with _create_websocket_client(monkeypatch, tmp_path) as client:
        with client.websocket_connect("/api/v1/ws/sessions/sess_missing?token=mock_owner_token") as websocket:
            with pytest.raises(WebSocketDisconnect) as disconnect:
                websocket.receive_json()

    assert disconnect.value.code == 4404


def test_session_stream_ws_sends_ready_and_keepalive(monkeypatch, tmp_path) -> None:
    with _create_websocket_client(monkeypatch, tmp_path, keepalive_seconds="0.001") as client:
        bootstrap_response = client.post(
            "/api/v1/sessions/bootstrap",
            headers={"Authorization": "Bearer mock_owner_token"},
        )
        session_id = bootstrap_response.json()["data"]["session_id"]

        with client.websocket_connect(
            f"/api/v1/ws/sessions/{session_id}?token=mock_owner_token"
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
