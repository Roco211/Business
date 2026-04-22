from datetime import datetime, timezone
UTC = timezone.utc
from importlib import import_module

import pytest
from sqlalchemy import text

from app.core.ids import new_prefixed_id
from app.models import SessionRecord
from app.services.bootstrap import ensure_default_context


def _load_session_stream_service():
    try:
        return import_module("app.services.session_stream")
    except ModuleNotFoundError as exc:  # pragma: no cover - red phase helper
        pytest.fail(f"session stream service module missing: {exc}")


def _create_second_session(db_session, *, shop_id: str) -> SessionRecord:
    now = datetime.now(UTC).replace(tzinfo=None)
    session = SessionRecord(
        session_id=new_prefixed_id("sess"),
        shop_id=shop_id,
        session_type="workgroup",
        title="Second workgroup",
        participants=["owner_default", "xiaoya"],
        last_event_seq=0,
        last_message_at=None,
        created_at=now,
        updated_at=now,
    )
    db_session.add(session)
    db_session.commit()
    return session


def test_append_session_event_persists_payload_and_updates_session_seq(db_session) -> None:
    service = _load_session_stream_service()
    context = ensure_default_context(db_session)

    appended = service.append_session_event(
        db_session,
        session_id=context.session.session_id,
        event_type="message.created",
        task_run_id="task_demo_001",
        message_id="msg_demo_001",
        data={
            "message_type": "text",
            "preview_text": "restock water",
        },
    )
    db_session.commit()

    row = db_session.execute(
        text(
            """
            SELECT event_id, session_id, seq, event_type, task_run_id, message_id, payload
            FROM session_stream_events
            WHERE event_id = :event_id
            """
        ),
        {"event_id": appended.event_id},
    ).mappings().one()
    refreshed_session = db_session.get(SessionRecord, context.session.session_id)

    assert appended.seq == 1
    assert row["session_id"] == context.session.session_id
    assert row["seq"] == 1
    assert row["event_type"] == "message.created"
    assert row["task_run_id"] == "task_demo_001"
    assert row["message_id"] == "msg_demo_001"
    assert "restock water" in str(row["payload"])
    assert refreshed_session is not None
    assert refreshed_session.last_event_seq == 1


def test_append_session_event_allocates_sequence_per_session(db_session) -> None:
    service = _load_session_stream_service()
    context = ensure_default_context(db_session)
    second_session = _create_second_session(db_session, shop_id=context.shop.shop_id)

    first = service.append_session_event(
        db_session,
        session_id=context.session.session_id,
        event_type="task.updated",
        task_run_id="task_demo_002",
        message_id=None,
        data={"status": "processing"},
    )
    second = service.append_session_event(
        db_session,
        session_id=context.session.session_id,
        event_type="task.updated",
        task_run_id="task_demo_002",
        message_id=None,
        data={"status": "completed"},
    )
    third = service.append_session_event(
        db_session,
        session_id=second_session.session_id,
        event_type="message.created",
        task_run_id=None,
        message_id="msg_demo_002",
        data={"message_type": "text"},
    )
    db_session.commit()

    refreshed_first_session = db_session.get(SessionRecord, context.session.session_id)
    refreshed_second_session = db_session.get(SessionRecord, second_session.session_id)

    assert first.seq == 1
    assert second.seq == 2
    assert third.seq == 1
    assert refreshed_first_session is not None
    assert refreshed_first_session.last_event_seq == 2
    assert refreshed_second_session is not None
    assert refreshed_second_session.last_event_seq == 1


def test_append_session_event_rejects_missing_session(db_session) -> None:
    service = _load_session_stream_service()

    with pytest.raises(LookupError):
        service.append_session_event(
            db_session,
            session_id="sess_missing",
            event_type="message.created",
            task_run_id=None,
            message_id="msg_missing",
            data={"message_type": "text"},
        )
