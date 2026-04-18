from dataclasses import dataclass
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import V2ConversationSession, V2Message, V2TaskRun
from app.services.v2_time import utc_now_naive


@dataclass(frozen=True)
class CreatedV2Session:
    session_id: str
    tenant_id: str
    shop_id: str
    session_type: str
    title: str
    status: str
    initiated_by_account_id: str


def create_v2_session(
    db_session: Session,
    *,
    tenant_id: str,
    shop_id: str,
    initiated_by_account_id: str,
    session_type: str,
    title: str,
) -> CreatedV2Session:
    now = utc_now_naive()
    session = V2ConversationSession(
        session_id=f"vsess_{uuid.uuid4().hex}"[:40],
        tenant_id=tenant_id,
        shop_id=shop_id,
        session_type=session_type,
        title=title,
        status="active",
        initiated_by_account_id=initiated_by_account_id,
        created_at=now,
        updated_at=now,
    )
    db_session.add(session)
    db_session.commit()
    return CreatedV2Session(
        session_id=session.session_id,
        tenant_id=session.tenant_id,
        shop_id=session.shop_id,
        session_type=session.session_type,
        title=session.title,
        status=session.status,
        initiated_by_account_id=session.initiated_by_account_id,
    )


def list_v2_sessions(
    db_session: Session,
    *,
    tenant_id: str,
    shop_id: str,
) -> list[V2ConversationSession]:
    return list(
        db_session.scalars(
            select(V2ConversationSession)
            .where(
                V2ConversationSession.tenant_id == tenant_id,
                V2ConversationSession.shop_id == shop_id,
            )
            .order_by(V2ConversationSession.created_at.desc(), V2ConversationSession.session_id.desc())
        )
    )


def create_v2_message_and_task_run(
    db_session: Session,
    *,
    tenant_id: str,
    shop_id: str,
    session_id: str,
    actor_id: str,
    message_kind: str,
    payload_json: dict[str, object],
    client_request_id: str | None,
) -> tuple[V2Message, V2TaskRun] | None:
    session = db_session.scalar(
        select(V2ConversationSession).where(
            V2ConversationSession.session_id == session_id,
            V2ConversationSession.tenant_id == tenant_id,
            V2ConversationSession.shop_id == shop_id,
        )
    )
    if session is None:
        return None

    now = utc_now_naive()
    message = V2Message(
        message_id=f"vmsg_{uuid.uuid4().hex}"[:40],
        tenant_id=tenant_id,
        shop_id=shop_id,
        session_id=session_id,
        actor_type="account",
        actor_id=actor_id,
        message_kind=message_kind,
        payload_json=payload_json,
        client_request_id=client_request_id,
        created_at=now,
    )
    task_run = V2TaskRun(
        task_run_id=f"vtask_{uuid.uuid4().hex}"[:40],
        tenant_id=tenant_id,
        shop_id=shop_id,
        session_id=session_id,
        source_message_id=message.message_id,
        intent_type="conversation.capture",
        status="captured",
        risk_level="unknown",
        trace_id=f"trace_{uuid.uuid4().hex}",
        result_summary=None,
        error_code=None,
        created_at=now,
        updated_at=now,
        completed_at=None,
    )
    db_session.add(message)
    db_session.add(task_run)
    db_session.commit()
    return message, task_run


def list_v2_messages(
    db_session: Session,
    *,
    tenant_id: str,
    shop_id: str,
    session_id: str,
) -> list[V2Message]:
    return list(
        db_session.scalars(
            select(V2Message)
            .where(
                V2Message.tenant_id == tenant_id,
                V2Message.shop_id == shop_id,
                V2Message.session_id == session_id,
            )
            .order_by(V2Message.created_at.asc(), V2Message.message_id.asc())
        )
    )


def get_v2_task_run(
    db_session: Session,
    *,
    tenant_id: str,
    shop_id: str,
    task_run_id: str,
) -> V2TaskRun | None:
    return db_session.scalar(
        select(V2TaskRun).where(
            V2TaskRun.task_run_id == task_run_id,
            V2TaskRun.tenant_id == tenant_id,
            V2TaskRun.shop_id == shop_id,
        )
    )
