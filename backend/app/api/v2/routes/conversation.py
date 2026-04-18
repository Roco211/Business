from functools import partial

from anyio import from_thread
from fastapi import APIRouter, Depends, Query, Request, WebSocket, WebSocketDisconnect, status
from fastapi.responses import JSONResponse
from sqlalchemy import select
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
    V2CreateTaskDraftRequest,
    V2MessageData,
    V2MessageListData,
    V2RequestConfirmationFromDraftRequest,
    V2SessionData,
    V2SessionListData,
    V2SessionStreamReplayData,
    V2TaskRunData,
)
from app.db.session import get_db_session, get_session_factory
from app.models import V2Clarification, V2Confirmation, V2ContextSession
from app.realtime.connection_manager import get_session_stream_manager
from app.services.v2_conversation import (
    V2ConfirmationConflictError,
    V2ConfirmationTypeMismatchError,
    V2TaskDraftTypeMismatchError,
    V2TaskDraftNotReadyError,
    V2TaskRunTransitionError,
    V2UnsupportedDraftTypeError,
    V2UnsupportedIntentTypeError,
    answer_v2_clarification,
    approve_v2_confirmation,
    create_v2_message_and_task_run,
    create_v2_session,
    get_v2_session,
    get_v2_task_draft,
    get_v2_task_run,
    list_v2_clarifications,
    list_v2_messages,
    list_v2_confirmations,
    list_v2_sessions,
    reject_v2_confirmation,
    request_v2_confirmation_from_task_draft,
    upsert_v2_task_draft,
)
from app.services.v2_identity import resolve_v2_auth_session
from app.services.v2_inventory import (
    V2InventoryItemNotFoundError,
    V2InventoryPayloadValidationError,
    V2InventoryStockOutConflictError,
    V2InventoryStockOutItemNotFoundError,
    V2InventoryStockOutValidationError,
    V2InventoryUnitMismatchError,
)
from app.services.v2_session_stream import list_v2_session_events_after
from app.services.v2_time import utc_now_naive

router = APIRouter(prefix="/api/v2", tags=["v2-conversation"])
UNAUTHORIZED_CLOSE_CODE = 4401
SESSION_NOT_FOUND_CLOSE_CODE = 4404


def _context_account_mismatch() -> JSONResponse:
    return JSONResponse(
        status_code=403,
        content=V2ErrorEnvelope(
            error=V2ErrorBody(code="context_account_mismatch", message="Context account mismatch")
        ).model_dump(),
    )


def _resolve_active_v2_context_session(
    db_session: Session,
    *,
    context_token: str,
) -> V2ContextSession | None:
    return db_session.scalar(
        select(V2ContextSession).where(
            V2ContextSession.context_session_id == context_token,
            V2ContextSession.status == "active",
            V2ContextSession.expires_at > utc_now_naive(),
        )
    )


async def _close_websocket(websocket: WebSocket, *, code: int) -> None:
    await websocket.accept()
    await websocket.close(code=code)


def _is_v2_websocket_auth_still_valid(
    *,
    session_factory,
    bearer_token: str,
    context_token: str,
    expected_account_id: str,
    expected_tenant_id: str,
    expected_shop_id: str,
) -> bool:
    db_session = session_factory()
    try:
        refreshed_auth = resolve_v2_auth_session(db_session, bearer_token=bearer_token)
        if refreshed_auth is None or refreshed_auth.account_id != expected_account_id:
            return False

        refreshed_context = _resolve_active_v2_context_session(
            db_session,
            context_token=context_token,
        )
        if refreshed_context is None:
            return False

        return (
            refreshed_context.account_id == expected_account_id
            and refreshed_context.tenant_id == expected_tenant_id
            and refreshed_context.shop_id == expected_shop_id
        )
    finally:
        db_session.close()


def _resolve_v2_session_cursor(
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


def _resolve_v2_task_run_session_cursor(
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
    return _resolve_v2_session_cursor(
        db_session,
        tenant_id=tenant_id,
        shop_id=shop_id,
        session_id=task_run.session_id,
    )


def _resolve_v2_clarification_session_cursor(
    db_session: Session,
    *,
    tenant_id: str,
    shop_id: str,
    clarification_id: str,
) -> tuple[str, int] | None:
    clarification = db_session.scalar(
        select(V2Clarification).where(
            V2Clarification.clarification_id == clarification_id,
            V2Clarification.tenant_id == tenant_id,
            V2Clarification.shop_id == shop_id,
        )
    )
    if clarification is None:
        return None
    return _resolve_v2_task_run_session_cursor(
        db_session,
        tenant_id=tenant_id,
        shop_id=shop_id,
        task_run_id=clarification.task_run_id,
    )


def _resolve_v2_confirmation_session_cursor(
    db_session: Session,
    *,
    tenant_id: str,
    shop_id: str,
    confirmation_id: str,
) -> tuple[str, int] | None:
    confirmation = db_session.scalar(
        select(V2Confirmation).where(
            V2Confirmation.confirmation_id == confirmation_id,
            V2Confirmation.tenant_id == tenant_id,
            V2Confirmation.shop_id == shop_id,
        )
    )
    if confirmation is None:
        return None
    return _resolve_v2_task_run_session_cursor(
        db_session,
        tenant_id=tenant_id,
        shop_id=shop_id,
        task_run_id=confirmation.task_run_id,
    )


def _publish_v2_stream_events_best_effort(
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


def _to_task_run_data(task_run, draft) -> V2TaskRunData:
    return V2TaskRunData(
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


@router.get("/sessions/{session_id}/stream-events", response_model=V2DataEnvelope[V2SessionStreamReplayData])
def list_session_stream_events_v2(
    session_id: str,
    after_seq: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    account: V2AuthenticatedAccount = Depends(require_v2_authenticated_account),
    context: V2ExecutionContext = Depends(require_v2_execution_context),
    db_session: Session = Depends(get_db_session),
) -> V2DataEnvelope[V2SessionStreamReplayData] | JSONResponse:
    if account.account_id != context.account_id:
        return _context_account_mismatch()

    session = get_v2_session(
        db_session,
        tenant_id=context.tenant_id,
        shop_id=context.shop_id,
        session_id=session_id,
    )
    if session is None:
        return JSONResponse(
            status_code=404,
            content=V2ErrorEnvelope(
                error=V2ErrorBody(code="session_not_found", message="Session not found")
            ).model_dump(),
        )

    events = list_v2_session_events_after(
        db_session,
        tenant_id=context.tenant_id,
        shop_id=context.shop_id,
        session_id=session_id,
        after_seq=after_seq,
        limit=limit,
    )
    return V2DataEnvelope(
        data=V2SessionStreamReplayData(
            session_id=session_id,
            count=len(events),
            last_event_seq=int(session.last_event_seq),
            events=events,
        )
    )


@router.websocket("/ws/sessions/{session_id}")
async def session_stream_websocket_v2(websocket: WebSocket, session_id: str) -> None:
    token = websocket.query_params.get("token")
    context_token = websocket.query_params.get("context_token")
    session_factory = get_session_factory()
    db_session = session_factory()
    manager = get_session_stream_manager(websocket.app)
    connected = False

    try:
        if not token or not context_token:
            await _close_websocket(websocket, code=UNAUTHORIZED_CLOSE_CODE)
            return

        auth = resolve_v2_auth_session(db_session, bearer_token=token)
        if auth is None:
            await _close_websocket(websocket, code=UNAUTHORIZED_CLOSE_CODE)
            return

        context_session = _resolve_active_v2_context_session(
            db_session,
            context_token=context_token,
        )
        if context_session is None or context_session.account_id != auth.account_id:
            await _close_websocket(websocket, code=UNAUTHORIZED_CLOSE_CODE)
            return

        conversation_session = get_v2_session(
            db_session,
            tenant_id=context_session.tenant_id,
            shop_id=context_session.shop_id,
            session_id=session_id,
        )
        if conversation_session is None:
            await _close_websocket(websocket, code=SESSION_NOT_FOUND_CLOSE_CODE)
            return

        after_seq_param = websocket.query_params.get("after_seq")
        if after_seq_param is None or after_seq_param == "":
            replay_after_seq = int(conversation_session.last_event_seq)
        else:
            try:
                replay_after_seq = max(0, int(after_seq_param))
            except ValueError:
                replay_after_seq = int(conversation_session.last_event_seq)

        def _load_v2_pending_events(pending_db_session, pending_session_id: str, after_seq: int):
            return list_v2_session_events_after(
                pending_db_session,
                tenant_id=context_session.tenant_id,
                shop_id=context_session.shop_id,
                session_id=pending_session_id,
                after_seq=after_seq,
            )

        await manager.connect(
            session_id=session_id,
            websocket=websocket,
            replay_after_seq=replay_after_seq,
            current_seq=int(conversation_session.last_event_seq),
            pending_event_loader=_load_v2_pending_events,
            auth_is_valid=lambda: _is_v2_websocket_auth_still_valid(
                session_factory=session_factory,
                bearer_token=token,
                context_token=context_token,
                expected_account_id=auth.account_id,
                expected_tenant_id=context_session.tenant_id,
                expected_shop_id=context_session.shop_id,
            ),
            unauthorized_close_code=UNAUTHORIZED_CLOSE_CODE,
        )
        connected = True

        while True:
            message = await websocket.receive()
            if message["type"] == "websocket.disconnect":
                break
    except WebSocketDisconnect:
        pass
    finally:
        db_session.close()
        if connected:
            await manager.disconnect(session_id=session_id, websocket=websocket)


@router.post(
    "/sessions/{session_id}/messages",
    response_model=V2DataEnvelope[V2CreateMessageData],
    status_code=status.HTTP_201_CREATED,
)
def post_message_v2(
    session_id: str,
    payload: V2CreateMessageRequest,
    request: Request,
    account: V2AuthenticatedAccount = Depends(require_v2_authenticated_account),
    context: V2ExecutionContext = Depends(require_v2_execution_context),
    db_session: Session = Depends(get_db_session),
) -> V2DataEnvelope[V2CreateMessageData] | JSONResponse:
    if account.account_id != context.account_id:
        return _context_account_mismatch()

    session_cursor = _resolve_v2_session_cursor(
        db_session,
        tenant_id=context.tenant_id,
        shop_id=context.shop_id,
        session_id=session_id,
    )

    try:
        created = create_v2_message_and_task_run(
            db_session,
            tenant_id=context.tenant_id,
            shop_id=context.shop_id,
            session_id=session_id,
            actor_id=account.account_id,
            message_kind=payload.message_kind,
            payload_json=payload.payload_json,
            client_request_id=payload.client_request_id,
            intent_type=payload.intent_type,
        )
    except V2UnsupportedIntentTypeError as exc:
        return JSONResponse(
            status_code=422,
            content=V2ErrorEnvelope(
                error=V2ErrorBody(code="validation_error", message=str(exc))
            ).model_dump(),
        )
    if created is None:
        return JSONResponse(
            status_code=404,
            content=V2ErrorEnvelope(
                error=V2ErrorBody(code="session_not_found", message="Session not found")
            ).model_dump(),
        )

    message, task_run = created
    if session_cursor is not None:
        _, after_seq = session_cursor
        _publish_v2_stream_events_best_effort(
            request,
            tenant_id=context.tenant_id,
            shop_id=context.shop_id,
            session_id=session_id,
            after_seq=after_seq,
        )
    return V2DataEnvelope(
        data=V2CreateMessageData(
            message_id=message.message_id,
            task_run_id=task_run.task_run_id,
            intent_type=task_run.intent_type,
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
    return V2DataEnvelope(data=_to_task_run_data(task_run, draft))


@router.post("/task-runs/{task_run_id}/draft", response_model=V2DataEnvelope[V2TaskRunData])
def create_task_draft_v2(
    task_run_id: str,
    payload: V2CreateTaskDraftRequest,
    request: Request,
    account: V2AuthenticatedAccount = Depends(require_v2_authenticated_account),
    context: V2ExecutionContext = Depends(require_v2_execution_context),
    db_session: Session = Depends(get_db_session),
) -> V2DataEnvelope[V2TaskRunData] | JSONResponse:
    if account.account_id != context.account_id:
        return _context_account_mismatch()

    task_run_cursor = _resolve_v2_task_run_session_cursor(
        db_session,
        tenant_id=context.tenant_id,
        shop_id=context.shop_id,
        task_run_id=task_run_id,
    )

    try:
        task_run = upsert_v2_task_draft(
            db_session,
            tenant_id=context.tenant_id,
            shop_id=context.shop_id,
            task_run_id=task_run_id,
            draft_type=payload.draft_type,
            draft_payload=payload.draft_payload,
            created_by_account_id=account.account_id,
        )
    except LookupError:
        return JSONResponse(
            status_code=404,
            content=V2ErrorEnvelope(
                error=V2ErrorBody(code="task_run_not_found", message="Task run not found")
            ).model_dump(),
        )
    except V2UnsupportedDraftTypeError as exc:
        return JSONResponse(
            status_code=422,
            content=V2ErrorEnvelope(
                error=V2ErrorBody(code="validation_error", message=str(exc))
            ).model_dump(),
        )
    except (V2InventoryPayloadValidationError, V2InventoryStockOutValidationError) as exc:
        return JSONResponse(
            status_code=422,
            content=V2ErrorEnvelope(
                error=V2ErrorBody(code="validation_error", message=str(exc))
            ).model_dump(),
        )
    except V2TaskDraftTypeMismatchError:
        return JSONResponse(
            status_code=409,
            content=V2ErrorEnvelope(
                error=V2ErrorBody(code="draft_type_mismatch", message="Task draft type does not match task intent")
            ).model_dump(),
        )
    except V2TaskRunTransitionError:
        return JSONResponse(
            status_code=409,
            content=V2ErrorEnvelope(
                error=V2ErrorBody(code="task_run_not_draftable", message="Task run cannot accept draft updates")
            ).model_dump(),
        )

    draft = get_v2_task_draft(
        db_session,
        tenant_id=context.tenant_id,
        shop_id=context.shop_id,
        task_run_id=task_run_id,
    )
    if task_run_cursor is not None:
        session_id_for_publish, after_seq = task_run_cursor
        _publish_v2_stream_events_best_effort(
            request,
            tenant_id=context.tenant_id,
            shop_id=context.shop_id,
            session_id=session_id_for_publish,
            after_seq=after_seq,
        )
    return V2DataEnvelope(data=_to_task_run_data(task_run, draft))


@router.post(
    "/task-runs/{task_run_id}/confirmations",
    response_model=V2DataEnvelope[V2ConfirmationData],
    status_code=status.HTTP_201_CREATED,
)
def request_confirmation_from_task_draft_v2(
    task_run_id: str,
    payload: V2RequestConfirmationFromDraftRequest,
    request: Request,
    account: V2AuthenticatedAccount = Depends(require_v2_authenticated_account),
    context: V2ExecutionContext = Depends(require_v2_execution_context),
    db_session: Session = Depends(get_db_session),
) -> V2DataEnvelope[V2ConfirmationData] | JSONResponse:
    if account.account_id != context.account_id:
        return _context_account_mismatch()

    task_run_cursor = _resolve_v2_task_run_session_cursor(
        db_session,
        tenant_id=context.tenant_id,
        shop_id=context.shop_id,
        task_run_id=task_run_id,
    )

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
    except V2ConfirmationTypeMismatchError:
        return JSONResponse(
            status_code=409,
            content=V2ErrorEnvelope(
                error=V2ErrorBody(
                    code="confirmation_type_mismatch",
                    message="Confirmation type does not match task draft type",
                )
            ).model_dump(),
        )
    except (V2ConfirmationConflictError, V2TaskRunTransitionError):
        return JSONResponse(
            status_code=409,
            content=V2ErrorEnvelope(
                error=V2ErrorBody(code="task_run_not_drafted", message="Task run is not drafted")
            ).model_dump(),
        )

    if task_run_cursor is not None:
        session_id_for_publish, after_seq = task_run_cursor
        _publish_v2_stream_events_best_effort(
            request,
            tenant_id=context.tenant_id,
            shop_id=context.shop_id,
            session_id=session_id_for_publish,
            after_seq=after_seq,
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
    request: Request,
    account: V2AuthenticatedAccount = Depends(require_v2_authenticated_account),
    context: V2ExecutionContext = Depends(require_v2_execution_context),
    db_session: Session = Depends(get_db_session),
) -> V2DataEnvelope[V2ClarificationData] | JSONResponse:
    if account.account_id != context.account_id:
        return _context_account_mismatch()

    clarification_cursor = _resolve_v2_clarification_session_cursor(
        db_session,
        tenant_id=context.tenant_id,
        shop_id=context.shop_id,
        clarification_id=clarification_id,
    )

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

    if clarification_cursor is not None:
        session_id_for_publish, after_seq = clarification_cursor
        _publish_v2_stream_events_best_effort(
            request,
            tenant_id=context.tenant_id,
            shop_id=context.shop_id,
            session_id=session_id_for_publish,
            after_seq=after_seq,
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
    request: Request,
    account: V2AuthenticatedAccount = Depends(require_v2_authenticated_account),
    context: V2ExecutionContext = Depends(require_v2_execution_context),
    db_session: Session = Depends(get_db_session),
) -> V2DataEnvelope[V2ConfirmationData] | JSONResponse:
    if account.account_id != context.account_id:
        return _context_account_mismatch()

    confirmation_cursor = _resolve_v2_confirmation_session_cursor(
        db_session,
        tenant_id=context.tenant_id,
        shop_id=context.shop_id,
        confirmation_id=confirmation_id,
    )

    try:
        confirmation = approve_v2_confirmation(
            db_session,
            tenant_id=context.tenant_id,
            shop_id=context.shop_id,
            confirmation_id=confirmation_id,
            resolution_payload=payload.resolution_payload,
            approved_by_account_id=account.account_id,
        )
    except (V2InventoryItemNotFoundError, V2InventoryStockOutItemNotFoundError):
        return JSONResponse(
            status_code=404,
            content=V2ErrorEnvelope(
                error=V2ErrorBody(code="inventory_item_not_found", message="Inventory item not found")
            ).model_dump(),
        )
    except V2InventoryStockOutConflictError:
        return JSONResponse(
            status_code=409,
            content=V2ErrorEnvelope(
                error=V2ErrorBody(code="inventory_conflict", message="Inventory stock-out conflicts with current stock")
            ).model_dump(),
        )
    except (
        V2InventoryPayloadValidationError,
        V2InventoryUnitMismatchError,
        V2InventoryStockOutValidationError,
    ) as exc:
        return JSONResponse(
            status_code=422,
            content=V2ErrorEnvelope(
                error=V2ErrorBody(code="validation_error", message=str(exc))
            ).model_dump(),
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

    if confirmation_cursor is not None:
        session_id_for_publish, after_seq = confirmation_cursor
        _publish_v2_stream_events_best_effort(
            request,
            tenant_id=context.tenant_id,
            shop_id=context.shop_id,
            session_id=session_id_for_publish,
            after_seq=after_seq,
        )
    return V2DataEnvelope(data=_to_confirmation_data(confirmation))


@router.post(
    "/confirmations/{confirmation_id}/reject",
    response_model=V2DataEnvelope[V2ConfirmationData],
)
def reject_confirmation_v2(
    confirmation_id: str,
    request: Request,
    account: V2AuthenticatedAccount = Depends(require_v2_authenticated_account),
    context: V2ExecutionContext = Depends(require_v2_execution_context),
    db_session: Session = Depends(get_db_session),
) -> V2DataEnvelope[V2ConfirmationData] | JSONResponse:
    if account.account_id != context.account_id:
        return _context_account_mismatch()

    confirmation_cursor = _resolve_v2_confirmation_session_cursor(
        db_session,
        tenant_id=context.tenant_id,
        shop_id=context.shop_id,
        confirmation_id=confirmation_id,
    )

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

    if confirmation_cursor is not None:
        session_id_for_publish, after_seq = confirmation_cursor
        _publish_v2_stream_events_best_effort(
            request,
            tenant_id=context.tenant_id,
            shop_id=context.shop_id,
            session_id=session_id_for_publish,
            after_seq=after_seq,
        )
    return V2DataEnvelope(data=_to_confirmation_data(confirmation))
