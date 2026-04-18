from functools import partial

from anyio import from_thread
from fastapi import Request
from sqlalchemy.orm import Session

from app.db.session import get_session_factory
from app.realtime.connection_manager import get_session_stream_manager
from app.services.v2_conversation import get_v2_session, get_v2_task_run
from app.services.v2_session_stream import list_v2_session_events_after


def resolve_v2_session_cursor(
    db_session: Session,
    *,
    tenant_id: str,
    shop_id: str,
    session_id: str,
) -> tuple[str, int] | None:
    session = get_v2_session(
        db_session,
        tenant_id=tenant_id,
        shop_id=shop_id,
        session_id=session_id,
    )
    if session is None:
        return None
    return session.session_id, int(session.last_event_seq)


def resolve_v2_task_run_session_cursor(
    db_session: Session,
    *,
    tenant_id: str,
    shop_id: str,
    task_run_id: str,
) -> tuple[str, int] | None:
    task_run = get_v2_task_run(
        db_session,
        tenant_id=tenant_id,
        shop_id=shop_id,
        task_run_id=task_run_id,
    )
    if task_run is None:
        return None
    return resolve_v2_session_cursor(
        db_session,
        tenant_id=tenant_id,
        shop_id=shop_id,
        session_id=task_run.session_id,
    )


def publish_v2_stream_events_best_effort(
    request: Request,
    *,
    tenant_id: str,
    shop_id: str,
    session_id: str,
    after_seq: int,
) -> None:
    session_factory = get_session_factory()
    publish_session = session_factory()
    try:
        events = list_v2_session_events_after(
            publish_session,
            tenant_id=tenant_id,
            shop_id=shop_id,
            session_id=session_id,
            after_seq=after_seq,
        )
    finally:
        publish_session.close()

    if not events:
        return

    manager = get_session_stream_manager(request.app)
    for event in events:
        try:
            from_thread.run(partial(manager.publish, session_id=session_id, event=event))
        except Exception:
            return
