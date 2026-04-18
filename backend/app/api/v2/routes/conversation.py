from fastapi import APIRouter, Depends, Query, status
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
    V2AnswerClarificationRequest,
    V2ClarificationData,
    V2ClarificationListData,
    V2ApproveConfirmationRequest,
    V2ConfirmationData,
    V2ConfirmationListData,
    V2CreateMessageData,
    V2CreateMessageRequest,
    V2CreateSessionRequest,
    V2MessageData,
    V2MessageListData,
    V2RequestConfirmationFromDraftRequest,
    V2SessionData,
    V2SessionListData,
    V2TaskRunData,
)
from app.db.session import get_db_session
from app.services.v2_conversation import (
    V2ConfirmationConflictError,
    V2TaskDraftNotReadyError,
    V2TaskRunTransitionError,
    answer_v2_clarification,
    approve_v2_confirmation,
    create_v2_message_and_task_run,
    create_v2_session,
    get_v2_task_draft,
    get_v2_task_run,
    list_v2_clarifications,
    list_v2_messages,
    list_v2_confirmations,
    list_v2_sessions,
    reject_v2_confirmation,
    request_v2_confirmation_from_task_draft,
)

router = APIRouter(prefix="/api/v2", tags=["v2-conversation"])


def _context_account_mismatch() -> JSONResponse:
    return JSONResponse(
        status_code=403,
        content=V2ErrorEnvelope(
            error=V2ErrorBody(code="context_account_mismatch", message="Context account mismatch")
        ).model_dump(),
    )


def _to_confirmation_data(confirmation) -> V2ConfirmationData:
    return V2ConfirmationData(
        confirmation_id=confirmation.confirmation_id,
        tenant_id=confirmation.tenant_id,
        shop_id=confirmation.shop_id,
        task_run_id=confirmation.task_run_id,
        confirmation_type=confirmation.confirmation_type,
        status=confirmation.status,
        draft_payload=confirmation.draft_payload,
        approved_by_account_id=confirmation.approved_by_account_id,
        resolution_payload=confirmation.resolution_payload,
        created_at=confirmation.created_at,
        resolved_at=confirmation.resolved_at,
    )


def _to_clarification_data(clarification) -> V2ClarificationData:
    return V2ClarificationData(
        clarification_id=clarification.clarification_id,
        tenant_id=clarification.tenant_id,
        shop_id=clarification.shop_id,
        task_run_id=clarification.task_run_id,
        status=clarification.status,
        reason_code=clarification.reason_code,
        question_text=clarification.question_text,
        requested_fields=clarification.requested_fields,
        draft_payload=clarification.draft_payload,
        answer_payload=clarification.answer_payload,
        answered_by_account_id=clarification.answered_by_account_id,
        created_at=clarification.created_at,
        answered_at=clarification.answered_at,
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

    draft = get_v2_task_draft(
        db_session,
        tenant_id=context.tenant_id,
        shop_id=context.shop_id,
        task_run_id=task_run_id,
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
            draft_payload=draft.payload_json if draft is not None else None,
            created_at=task_run.created_at,
            updated_at=task_run.updated_at,
            completed_at=task_run.completed_at,
        )
    )


@router.post(
    "/task-runs/{task_run_id}/confirmations",
    response_model=V2DataEnvelope[V2ConfirmationData],
    status_code=status.HTTP_201_CREATED,
)
def request_confirmation_from_task_draft_v2(
    task_run_id: str,
    payload: V2RequestConfirmationFromDraftRequest,
    account: V2AuthenticatedAccount = Depends(require_v2_authenticated_account),
    context: V2ExecutionContext = Depends(require_v2_execution_context),
    db_session: Session = Depends(get_db_session),
) -> V2DataEnvelope[V2ConfirmationData] | JSONResponse:
    if account.account_id != context.account_id:
        return _context_account_mismatch()

    try:
        confirmation = request_v2_confirmation_from_task_draft(
            db_session,
            tenant_id=context.tenant_id,
            shop_id=context.shop_id,
            task_run_id=task_run_id,
            confirmation_type=payload.confirmation_type,
        )
    except LookupError:
        return JSONResponse(
            status_code=404,
            content=V2ErrorEnvelope(
                error=V2ErrorBody(code="task_run_not_found", message="Task run not found")
            ).model_dump(),
        )
    except V2TaskDraftNotReadyError:
        return JSONResponse(
            status_code=409,
            content=V2ErrorEnvelope(
                error=V2ErrorBody(code="draft_not_ready", message="Task draft is not ready")
            ).model_dump(),
        )
    except (V2ConfirmationConflictError, V2TaskRunTransitionError):
        return JSONResponse(
            status_code=409,
            content=V2ErrorEnvelope(
                error=V2ErrorBody(code="task_run_not_drafted", message="Task run is not drafted")
            ).model_dump(),
        )

    return V2DataEnvelope(data=_to_confirmation_data(confirmation))


@router.get("/clarifications", response_model=V2DataEnvelope[V2ClarificationListData])
def list_clarifications_v2(
    account: V2AuthenticatedAccount = Depends(require_v2_authenticated_account),
    context: V2ExecutionContext = Depends(require_v2_execution_context),
    status_filter: str | None = Query(default="pending", alias="status"),
    limit: int = Query(default=20, ge=1, le=50),
    db_session: Session = Depends(get_db_session),
) -> V2DataEnvelope[V2ClarificationListData] | JSONResponse:
    if account.account_id != context.account_id:
        return _context_account_mismatch()

    normalized_status = status_filter.strip() if status_filter is not None and status_filter.strip() else None
    clarifications = [
        _to_clarification_data(item)
        for item in list_v2_clarifications(
            db_session,
            tenant_id=context.tenant_id,
            shop_id=context.shop_id,
            status=normalized_status,
            limit=limit,
        )
    ]
    return V2DataEnvelope(
        data=V2ClarificationListData(clarifications=clarifications, count=len(clarifications))
    )


@router.post(
    "/clarifications/{clarification_id}/answer",
    response_model=V2DataEnvelope[V2ClarificationData],
)
def answer_clarification_v2(
    clarification_id: str,
    payload: V2AnswerClarificationRequest,
    account: V2AuthenticatedAccount = Depends(require_v2_authenticated_account),
    context: V2ExecutionContext = Depends(require_v2_execution_context),
    db_session: Session = Depends(get_db_session),
) -> V2DataEnvelope[V2ClarificationData] | JSONResponse:
    if account.account_id != context.account_id:
        return _context_account_mismatch()

    try:
        clarification = answer_v2_clarification(
            db_session,
            tenant_id=context.tenant_id,
            shop_id=context.shop_id,
            clarification_id=clarification_id,
            answer_payload=payload.answer_payload,
            answered_by_account_id=account.account_id,
        )
    except LookupError:
        return JSONResponse(
            status_code=404,
            content=V2ErrorEnvelope(
                error=V2ErrorBody(code="clarification_not_found", message="Clarification not found")
            ).model_dump(),
        )
    except (V2ConfirmationConflictError, V2TaskRunTransitionError):
        return JSONResponse(
            status_code=409,
            content=V2ErrorEnvelope(
                error=V2ErrorBody(code="clarification_not_pending", message="Clarification is not pending")
            ).model_dump(),
        )

    return V2DataEnvelope(data=_to_clarification_data(clarification))


@router.get("/confirmations", response_model=V2DataEnvelope[V2ConfirmationListData])
def list_confirmations_v2(
    account: V2AuthenticatedAccount = Depends(require_v2_authenticated_account),
    context: V2ExecutionContext = Depends(require_v2_execution_context),
    status_filter: str | None = Query(default="pending", alias="status"),
    limit: int = Query(default=20, ge=1, le=50),
    db_session: Session = Depends(get_db_session),
) -> V2DataEnvelope[V2ConfirmationListData] | JSONResponse:
    if account.account_id != context.account_id:
        return _context_account_mismatch()

    normalized_status = status_filter.strip() if status_filter is not None and status_filter.strip() else None
    confirmations = [
        _to_confirmation_data(item)
        for item in list_v2_confirmations(
            db_session,
            tenant_id=context.tenant_id,
            shop_id=context.shop_id,
            status=normalized_status,
            limit=limit,
        )
    ]
    return V2DataEnvelope(
        data=V2ConfirmationListData(confirmations=confirmations, count=len(confirmations))
    )


@router.post(
    "/confirmations/{confirmation_id}/approve",
    response_model=V2DataEnvelope[V2ConfirmationData],
)
def approve_confirmation_v2(
    confirmation_id: str,
    payload: V2ApproveConfirmationRequest,
    account: V2AuthenticatedAccount = Depends(require_v2_authenticated_account),
    context: V2ExecutionContext = Depends(require_v2_execution_context),
    db_session: Session = Depends(get_db_session),
) -> V2DataEnvelope[V2ConfirmationData] | JSONResponse:
    if account.account_id != context.account_id:
        return _context_account_mismatch()

    try:
        confirmation = approve_v2_confirmation(
            db_session,
            tenant_id=context.tenant_id,
            shop_id=context.shop_id,
            confirmation_id=confirmation_id,
            resolution_payload=payload.resolution_payload,
            approved_by_account_id=account.account_id,
        )
    except LookupError:
        return JSONResponse(
            status_code=404,
            content=V2ErrorEnvelope(
                error=V2ErrorBody(code="confirmation_not_found", message="Confirmation not found")
            ).model_dump(),
        )
    except (V2ConfirmationConflictError, V2TaskRunTransitionError):
        return JSONResponse(
            status_code=409,
            content=V2ErrorEnvelope(
                error=V2ErrorBody(code="confirmation_not_pending", message="Confirmation is not pending")
            ).model_dump(),
        )

    return V2DataEnvelope(data=_to_confirmation_data(confirmation))


@router.post(
    "/confirmations/{confirmation_id}/reject",
    response_model=V2DataEnvelope[V2ConfirmationData],
)
def reject_confirmation_v2(
    confirmation_id: str,
    account: V2AuthenticatedAccount = Depends(require_v2_authenticated_account),
    context: V2ExecutionContext = Depends(require_v2_execution_context),
    db_session: Session = Depends(get_db_session),
) -> V2DataEnvelope[V2ConfirmationData] | JSONResponse:
    if account.account_id != context.account_id:
        return _context_account_mismatch()

    try:
        confirmation = reject_v2_confirmation(
            db_session,
            tenant_id=context.tenant_id,
            shop_id=context.shop_id,
            confirmation_id=confirmation_id,
        )
    except LookupError:
        return JSONResponse(
            status_code=404,
            content=V2ErrorEnvelope(
                error=V2ErrorBody(code="confirmation_not_found", message="Confirmation not found")
            ).model_dump(),
        )
    except (V2ConfirmationConflictError, V2TaskRunTransitionError):
        return JSONResponse(
            status_code=409,
            content=V2ErrorEnvelope(
                error=V2ErrorBody(code="confirmation_not_pending", message="Confirmation is not pending")
            ).model_dump(),
        )

    return V2DataEnvelope(data=_to_confirmation_data(confirmation))
