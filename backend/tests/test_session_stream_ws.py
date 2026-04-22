from datetime import datetime, timezone
UTC = timezone.utc

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from starlette.websockets import WebSocketDisconnect

from conftest import auth_headers, load_create_app, login_and_get_token, upgrade_test_database


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
        token = login_and_get_token(client, monkeypatch)
        with client.websocket_connect(f"/api/v1/ws/sessions/sess_missing?token={token}") as websocket:
            with pytest.raises(WebSocketDisconnect) as disconnect:
                websocket.receive_json()

    assert disconnect.value.code == 4404


def test_session_stream_ws_sends_ready_and_keepalive(monkeypatch, tmp_path) -> None:
    with _create_websocket_client(monkeypatch, tmp_path, keepalive_seconds="0.001") as client:
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


def test_session_stream_ws_replays_events_after_requested_seq(monkeypatch, tmp_path) -> None:
    from app.services import session_stream as session_stream_service
    from app.services.bootstrap import ensure_default_context
    from app.db.session import get_session_factory

    with _create_websocket_client(monkeypatch, tmp_path, keepalive_seconds="1") as client:
        token = login_and_get_token(client, monkeypatch)
        db_session = get_session_factory()()
        try:
            context = ensure_default_context(db_session)
            session_stream_service.append_session_event(
                db_session,
                session_id=context.session.session_id,
                event_type="message.created",
                task_run_id="task_demo_001",
                message_id="msg_demo_001",
                data={"preview_text": "restock cola"},
            )
            replay_event = session_stream_service.append_session_event(
                db_session,
                session_id=context.session.session_id,
                event_type="task.updated",
                task_run_id="task_demo_001",
                message_id=None,
                data={"status": "completed"},
            )
            db_session.commit()
        finally:
            db_session.close()

        with client.websocket_connect(
            f"/api/v1/ws/sessions/{context.session.session_id}?token={token}&after_seq=1"
        ) as websocket:
            ready_event = websocket.receive_json()
            replayed_event = websocket.receive_json()

    assert ready_event["event_type"] == "session.ready"
    assert replayed_event["event_type"] == "task.updated"
    assert replayed_event["seq"] == replay_event.seq
    assert replayed_event["data"]["status"] == "completed"


def test_session_stream_ws_accepts_real_login_token(monkeypatch, tmp_path) -> None:
    with _create_websocket_client(monkeypatch, tmp_path, keepalive_seconds="0.001") as client:
        token = login_and_get_token(client, monkeypatch)
        bootstrap_response = client.post(
            "/api/v1/sessions/bootstrap",
            headers=auth_headers(token),
        )
        session_id = bootstrap_response.json()["data"]["session_id"]

        with client.websocket_connect(f"/api/v1/ws/sessions/{session_id}?token={token}") as websocket:
            ready_event = websocket.receive_json()

    assert ready_event["event_type"] == "session.ready"


def test_session_stream_ws_closes_when_auth_session_is_revoked(monkeypatch, tmp_path) -> None:
    from app.db.session import get_session_factory
    from app.models import AuthSession
    from app.services.auth_sessions import hash_session_token

    with _create_websocket_client(monkeypatch, tmp_path, keepalive_seconds="0.001") as client:
        token = login_and_get_token(client, monkeypatch)
        bootstrap_response = client.post(
            "/api/v1/sessions/bootstrap",
            headers=auth_headers(token),
        )
        session_id = bootstrap_response.json()["data"]["session_id"]

        with client.websocket_connect(f"/api/v1/ws/sessions/{session_id}?token={token}") as websocket:
            ready_event = websocket.receive_json()
            assert ready_event["event_type"] == "session.ready"

            db_session = get_session_factory()()
            try:
                auth_session = db_session.scalar(
                    select(AuthSession).where(
                        AuthSession.session_token_hash == hash_session_token(token),
                    )
                )
                assert auth_session is not None
                now = datetime.now(UTC).replace(tzinfo=None)
                auth_session.revoked_at = now
                auth_session.updated_at = now
                db_session.commit()
            finally:
                db_session.close()

            disconnect = None
            for _ in range(25):
                try:
                    websocket.receive_json()
                except WebSocketDisconnect as exc:
                    disconnect = exc
                    break

    assert disconnect is not None
    assert disconnect.code == 4401
