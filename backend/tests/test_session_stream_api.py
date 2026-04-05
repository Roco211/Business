from fastapi.testclient import TestClient

from app.services import session_stream as session_stream_service
from app.services.bootstrap import ensure_default_context
from conftest import load_create_app


def test_session_stream_events_api_replays_events_after_seq_and_requires_auth(db_session) -> None:
    context = ensure_default_context(db_session)
    first_event = session_stream_service.append_session_event(
        db_session,
        session_id=context.session.session_id,
        event_type="message.created",
        task_run_id="task_demo_001",
        message_id="msg_demo_001",
        data={"preview_text": "restock cola"},
    )
    second_event = session_stream_service.append_session_event(
        db_session,
        session_id=context.session.session_id,
        event_type="task.updated",
        task_run_id="task_demo_001",
        message_id=None,
        data={"status": "completed"},
    )
    db_session.commit()

    with TestClient(load_create_app()()) as client:
        unauthorized_response = client.get(
            f"/api/v1/sessions/{context.session.session_id}/stream-events?after_seq=0&limit=10"
        )
        response = client.get(
            f"/api/v1/sessions/{context.session.session_id}/stream-events?after_seq={first_event.seq}&limit=10",
            headers={"Authorization": "Bearer mock_owner_token"},
        )

    assert unauthorized_response.status_code == 401
    assert response.status_code == 200
    assert response.json()["data"] == [
        {
            "event_id": second_event.event_id,
            "seq": second_event.seq,
            "event_type": "task.updated",
            "session_id": context.session.session_id,
            "task_run_id": "task_demo_001",
            "message_id": None,
            "occurred_at": second_event.occurred_at.isoformat(),
            "data": {"status": "completed"},
        }
    ]
