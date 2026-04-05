from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps.auth import AuthenticatedContext, require_authenticated_context
from app.contracts.common import DataEnvelope, ErrorBody, ErrorEnvelope
from app.contracts.message import (
    CreateSessionMessageData,
    CreateSessionMessageRequest,
    SessionMessageItem,
    SessionMessagesMeta,
    SessionMessagesResponse,
)
from app.db.session import get_db_session
from app.models import SessionRecord, TaskRun
from app.services.bootstrap import ensure_default_context
from app.services.media_uploads import MediaUploadNotReadyError
from app.services.messages import (
    IdempotencyConflictError,
    MessageValidationError,
    SessionNotFoundError,
    create_message,
    list_messages,
)
from app.services.runtime_dispatch import enqueue_runtime_task
from app.services.task_runs import CREATED_STATUS, PENDING_CLASSIFICATION_TASK_TYPE

router = APIRouter(prefix="/api/v1/sessions", tags=["messages"])
DISPATCH_FAILED_ERROR_CODE = "dispatch_failed"
DISPATCH_FAILED_ERROR_MESSAGE = "Runtime dispatch failed; retry the same request to re-enqueue."


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _unauthorized() -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content=ErrorEnvelope(
            error=ErrorBody(code="unauthorized", message="Unauthorized", details=[])
        ).model_dump(),
    )


def _error_response(status_code: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=ErrorEnvelope(
            error=ErrorBody(code=code, message=message, details=[])
        ).model_dump(),
    )


def _is_initial_runtime_task_state(db_session: Session, task_run_id: str) -> bool:
    task_run = db_session.get(TaskRun, task_run_id)
    if task_run is None:
        return False

    return (
        task_run.status == CREATED_STATUS
        and task_run.task_type == PENDING_CLASSIFICATION_TASK_TYPE
    )


def _record_dispatch_attempt(db_session: Session, task_run_id: str, *, dispatched: bool) -> None:
    task_run = db_session.get(TaskRun, task_run_id)
    if task_run is None:
        return

    changed = False
    if dispatched:
        if task_run.error_code == DISPATCH_FAILED_ERROR_CODE:
            task_run.error_code = None
            task_run.error_message = None
            changed = True
    elif (
        task_run.error_code != DISPATCH_FAILED_ERROR_CODE
        or task_run.error_message != DISPATCH_FAILED_ERROR_MESSAGE
    ):
        task_run.error_code = DISPATCH_FAILED_ERROR_CODE
        task_run.error_message = DISPATCH_FAILED_ERROR_MESSAGE
        changed = True

    if changed:
        task_run.updated_at = _now()
        db_session.commit()
        return


def _load_shop_session(
    db_session: Session,
    *,
    session_id: str,
    shop_id: str,
) -> SessionRecord | None:
    session = db_session.scalar(
        select(SessionRecord).where(
            SessionRecord.session_id == session_id,
            SessionRecord.shop_id == shop_id,
        )
    )
    if session is not None:
        return session

    context = ensure_default_context(db_session)
    if context.session.session_id == session_id and context.shop.shop_id == shop_id:
        return context.session
    return None


@router.get("/{session_id}/messages", response_model=SessionMessagesResponse)
def get_session_messages(
    session_id: str,
    auth: AuthenticatedContext = Depends(require_authenticated_context),
    limit: int = Query(default=20, ge=1, le=50),
    cursor: str | None = Query(default=None),
    db_session: Session = Depends(get_db_session),
) -> SessionMessagesResponse | JSONResponse:
    if _load_shop_session(db_session, session_id=session_id, shop_id=auth.shop_id) is None:
        return _error_response(status.HTTP_404_NOT_FOUND, "session_not_found", "Session not found")

    try:
        page = list_messages(
            db_session,
            session_id=session_id,
            limit=limit,
            cursor=cursor,
        )
    except SessionNotFoundError:
        return _error_response(status.HTTP_404_NOT_FOUND, "session_not_found", "Session not found")

    return SessionMessagesResponse(
        data=[
            SessionMessageItem(
                message_id=item.message_id,
                session_id=item.session_id,
                actor_type=item.actor_type,
                actor_id=item.actor_id,
                message_type=item.message_type,
                text=item.text,
                media_ids=item.media_ids,
                task_run_id=item.task_run_id,
                created_at=item.created_at,
            )
            for item in page.items
        ],
        meta=SessionMessagesMeta(next_cursor=page.next_cursor),
    )


@router.post(
    "/{session_id}/messages",
    response_model=DataEnvelope[CreateSessionMessageData],
)
def post_session_message(
    session_id: str,
    payload: CreateSessionMessageRequest,
    auth: AuthenticatedContext = Depends(require_authenticated_context),
    db_session: Session = Depends(get_db_session),
) -> DataEnvelope[CreateSessionMessageData] | JSONResponse:
    if _load_shop_session(db_session, session_id=session_id, shop_id=auth.shop_id) is None:
        return _error_response(status.HTTP_404_NOT_FOUND, "session_not_found", "Session not found")

    try:
        result = create_message(
            db_session,
            session_id=session_id,
            actor_type="owner",
            actor_id=auth.actor_id,
            message_type=payload.message_type,
            text=payload.text,
            media_ids=payload.media_ids,
            client_request_id=payload.client_request_id,
        )
    except SessionNotFoundError:
        return _error_response(status.HTTP_404_NOT_FOUND, "session_not_found", "Session not found")
    except IdempotencyConflictError:
        return _error_response(
            status.HTTP_409_CONFLICT,
            "idempotency_conflict",
            "Request payload conflicts with prior submission",
        )
    except MediaUploadNotReadyError:
        return _error_response(
            status.HTTP_409_CONFLICT,
            "media_not_ready",
            "Media upload is not ready",
        )
    except MessageValidationError as exc:
        return _error_response(status.HTTP_422_UNPROCESSABLE_ENTITY, "validation_error", str(exc))

    payload_model = DataEnvelope(
        data=CreateSessionMessageData(
            message_id=result.message_id,
            task_run_id=result.task_run_id,
            status="created",
        )
    )
    if result.replayed:
        if _is_initial_runtime_task_state(db_session, result.task_run_id):
            dispatched = enqueue_runtime_task(result.task_run_id)
            _record_dispatch_attempt(db_session, result.task_run_id, dispatched=dispatched)
        return payload_model

    dispatched = enqueue_runtime_task(result.task_run_id)
    _record_dispatch_attempt(db_session, result.task_run_id, dispatched=dispatched)
    return JSONResponse(
        status_code=status.HTTP_201_CREATED,
        content=payload_model.model_dump(mode="json"),
    )
