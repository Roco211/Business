from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api.deps.v2_context import (
    V2AuthenticatedAccount,
    V2ExecutionContext,
    require_v2_authenticated_account,
    require_v2_execution_context,
)
from app.contracts.v2.common import V2DataEnvelope, V2ErrorBody, V2ErrorEnvelope
from app.contracts.v2.conversation import (
    V2CreateMessageData,
    V2CreateMessageRequest,
    V2CreateSessionRequest,
    V2MessageData,
    V2MessageListData,
    V2SessionData,
    V2SessionListData,
    V2TaskRunData,
)
from app.db.session import get_db_session
from app.services.v2_conversation import (
    create_v2_message_and_task_run,
    create_v2_session,
    get_v2_task_run,
    list_v2_messages,
    list_v2_sessions,
)

router = APIRouter(prefix="/api/v2", tags=["v2-conversation"])


def _context_account_mismatch() -> JSONResponse:
    return JSONResponse(
        status_code=403,
        content=V2ErrorEnvelope(
            error=V2ErrorBody(code="context_account_mismatch", message="Context account mismatch")
        ).model_dump(),
    )


@router.post("/sessions", response_model=V2DataEnvelope[V2SessionData], status_code=status.HTTP_201_CREATED)
def create_session_v2(
    payload: V2CreateSessionRequest,
    account: V2AuthenticatedAccount = Depends(require_v2_authenticated_account),
    context: V2ExecutionContext = Depends(require_v2_execution_context),
    db_session: Session = Depends(get_db_session),
) -> V2DataEnvelope[V2SessionData] | JSONResponse:
    if account.account_id != context.account_id:
        return _context_account_mismatch()

    created = create_v2_session(
        db_session,
        tenant_id=context.tenant_id,
        shop_id=context.shop_id,
        initiated_by_account_id=context.account_id,
        session_type=payload.session_type,
        title=payload.title,
    )
    return V2DataEnvelope(data=V2SessionData(**created.__dict__))


@router.get("/sessions", response_model=V2DataEnvelope[V2SessionListData])
def list_sessions_v2(
    account: V2AuthenticatedAccount = Depends(require_v2_authenticated_account),
    context: V2ExecutionContext = Depends(require_v2_execution_context),
    db_session: Session = Depends(get_db_session),
) -> V2DataEnvelope[V2SessionListData] | JSONResponse:
    if account.account_id != context.account_id:
        return _context_account_mismatch()

    sessions = [
        V2SessionData(
            session_id=item.session_id,
            tenant_id=item.tenant_id,
            shop_id=item.shop_id,
            session_type=item.session_type,
            title=item.title,
            status=item.status,
            initiated_by_account_id=item.initiated_by_account_id,
        )
        for item in list_v2_sessions(
            db_session,
            tenant_id=context.tenant_id,
            shop_id=context.shop_id,
        )
    ]
    return V2DataEnvelope(data=V2SessionListData(sessions=sessions))


@router.post(
    "/sessions/{session_id}/messages",
    response_model=V2DataEnvelope[V2CreateMessageData],
    status_code=status.HTTP_201_CREATED,
)
def post_message_v2(
    session_id: str,
    payload: V2CreateMessageRequest,
    account: V2AuthenticatedAccount = Depends(require_v2_authenticated_account),
    context: V2ExecutionContext = Depends(require_v2_execution_context),
    db_session: Session = Depends(get_db_session),
) -> V2DataEnvelope[V2CreateMessageData] | JSONResponse:
    if account.account_id != context.account_id:
        return _context_account_mismatch()

    created = create_v2_message_and_task_run(
        db_session,
        tenant_id=context.tenant_id,
        shop_id=context.shop_id,
        session_id=session_id,
        actor_id=account.account_id,
        message_kind=payload.message_kind,
        payload_json=payload.payload_json,
        client_request_id=payload.client_request_id,
    )
    if created is None:
        return JSONResponse(
            status_code=404,
            content=V2ErrorEnvelope(
                error=V2ErrorBody(code="session_not_found", message="Session not found")
            ).model_dump(),
        )

    message, task_run = created
    return V2DataEnvelope(
        data=V2CreateMessageData(
            message_id=message.message_id,
            task_run_id=task_run.task_run_id,
            status=task_run.status,
        )
    )


@router.get("/sessions/{session_id}/messages", response_model=V2DataEnvelope[V2MessageListData])
def list_messages_v2(
    session_id: str,
    account: V2AuthenticatedAccount = Depends(require_v2_authenticated_account),
    context: V2ExecutionContext = Depends(require_v2_execution_context),
    db_session: Session = Depends(get_db_session),
) -> V2DataEnvelope[V2MessageListData] | JSONResponse:
    if account.account_id != context.account_id:
        return _context_account_mismatch()

    messages = [
        V2MessageData(
            message_id=item.message_id,
            tenant_id=item.tenant_id,
            shop_id=item.shop_id,
            session_id=item.session_id,
            actor_type=item.actor_type,
            actor_id=item.actor_id,
            message_kind=item.message_kind,
            payload_json=item.payload_json,
            client_request_id=item.client_request_id,
            created_at=item.created_at,
        )
        for item in list_v2_messages(
            db_session,
            tenant_id=context.tenant_id,
            shop_id=context.shop_id,
            session_id=session_id,
        )
    ]
    return V2DataEnvelope(data=V2MessageListData(messages=messages))


@router.get("/task-runs/{task_run_id}", response_model=V2DataEnvelope[V2TaskRunData])
def get_task_run_v2(
    task_run_id: str,
    account: V2AuthenticatedAccount = Depends(require_v2_authenticated_account),
    context: V2ExecutionContext = Depends(require_v2_execution_context),
    db_session: Session = Depends(get_db_session),
) -> V2DataEnvelope[V2TaskRunData] | JSONResponse:
    if account.account_id != context.account_id:
        return _context_account_mismatch()

    task_run = get_v2_task_run(
        db_session,
        tenant_id=context.tenant_id,
        shop_id=context.shop_id,
        task_run_id=task_run_id,
    )
    if task_run is None:
        return JSONResponse(
            status_code=404,
            content=V2ErrorEnvelope(
                error=V2ErrorBody(code="task_run_not_found", message="Task run not found")
            ).model_dump(),
        )

    return V2DataEnvelope(
        data=V2TaskRunData(
            task_run_id=task_run.task_run_id,
            tenant_id=task_run.tenant_id,
            shop_id=task_run.shop_id,
            session_id=task_run.session_id,
            source_message_id=task_run.source_message_id,
            intent_type=task_run.intent_type,
            status=task_run.status,
            risk_level=task_run.risk_level,
            trace_id=task_run.trace_id,
            result_summary=task_run.result_summary,
            error_code=task_run.error_code,
            created_at=task_run.created_at,
            updated_at=task_run.updated_at,
            completed_at=task_run.completed_at,
        )
    )
