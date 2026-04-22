from datetime import datetime, timezone
UTC = timezone.utc
import importlib

import pytest


def _utc_now_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _load_v2_session_stream_service():
    try:
        return importlib.import_module("app.services.v2_session_stream")
    except ModuleNotFoundError as exc:  # pragma: no cover - red stage only
        pytest.fail(f"app.services.v2_session_stream is not implemented yet: {exc}")


def _seed_v2_stream_context(db_session) -> None:
    from app.models import V2Account, V2ConversationSession, V2Shop, V2Tenant

    now = _utc_now_naive()
    db_session.add(
        V2Account(
            account_id="acct_001",
            email="owner@example.com",
            display_name="Owner",
            password_hash="hash",
            password_salt="salt",
            status="active",
            created_at=now,
            updated_at=now,
        )
    )
    db_session.add(
        V2Tenant(
            tenant_id="tenant_a",
            name="Tenant A",
            slug="tenant-a",
            status="active",
            plan_code="trial",
            owner_account_id="acct_001",
            created_at=now,
            updated_at=now,
        )
    )
    db_session.add(
        V2Shop(
            shop_id="shop_a1",
            tenant_id="tenant_a",
            code="a-1",
            name="Shop A1",
            locale="zh-CN",
            timezone="Asia/Shanghai",
            status="active",
            created_at=now,
            updated_at=now,
        )
    )
    db_session.add(
        V2ConversationSession(
            session_id="vsess_001",
            tenant_id="tenant_a",
            shop_id="shop_a1",
            session_type="workgroup",
            title="Workgroup",
            status="active",
            initiated_by_account_id="acct_001",
            created_at=now,
            updated_at=now,
        )
    )
    db_session.commit()


def test_append_v2_session_event_assigns_incrementing_seq_and_lists_after_cursor(db_session) -> None:
    stream_service = _load_v2_session_stream_service()
    _seed_v2_stream_context(db_session)

    first = stream_service.append_v2_session_event(
        db_session,
        tenant_id="tenant_a",
        shop_id="shop_a1",
        session_id="vsess_001",
        event_type="message.created",
        task_run_id="vtask_001",
        message_id="vmsg_001",
        data={"preview_text": "restock cola"},
    )
    second = stream_service.append_v2_session_event(
        db_session,
        tenant_id="tenant_a",
        shop_id="shop_a1",
        session_id="vsess_001",
        event_type="task.updated",
        task_run_id="vtask_001",
        message_id="vmsg_001",
        data={"status": "captured"},
    )
    db_session.commit()

    replay = stream_service.list_v2_session_events_after(
        db_session,
        tenant_id="tenant_a",
        shop_id="shop_a1",
        session_id="vsess_001",
        after_seq=first.seq,
    )

    assert first.seq == 1
    assert second.seq == 2
    assert [event.event_type for event in replay] == ["task.updated"]
    assert replay[0].event_id == second.event_id
    assert replay[0].data == {"status": "captured"}


def test_list_v2_session_events_after_clamps_limit_and_updates_session_cursor(db_session) -> None:
    from app.models import V2ConversationSession

    stream_service = _load_v2_session_stream_service()
    _seed_v2_stream_context(db_session)

    for index in range(3):
        stream_service.append_v2_session_event(
            db_session,
            tenant_id="tenant_a",
            shop_id="shop_a1",
            session_id="vsess_001",
            event_type="task.updated",
            task_run_id=f"vtask_{index}",
            message_id=None,
            data={"index": index},
        )
    db_session.commit()

    session = db_session.get(V2ConversationSession, "vsess_001")
    replay = stream_service.list_v2_session_events_after(
        db_session,
        tenant_id="tenant_a",
        shop_id="shop_a1",
        session_id="vsess_001",
        after_seq=0,
        limit=999,
    )

    assert session is not None
    assert session.last_event_seq == 3
    assert [event.seq for event in replay] == [1, 2, 3]
