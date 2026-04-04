from fastapi import APIRouter, Depends, Header, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.contracts.common import DataEnvelope, ErrorBody, ErrorEnvelope
from app.contracts.message import (
    CreateSessionMessageData,
    CreateSessionMessageRequest,
    SessionMessageItem,
    SessionMessagesMeta,
    SessionMessagesResponse,
)
from app.db.session import get_db_session
from app.services.bootstrap import ensure_default_context
from app.services.messages import (
    IdempotencyConflictError,
    MessageValidationError,
    SessionNotFoundError,
    create_message,
    list_messages,
)

router = APIRouter(prefix="/api/v1/sessions", tags=["messages"])


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


@router.get("/{session_id}/messages", response_model=SessionMessagesResponse)
def get_session_messages(
    session_id: str,
    authorization: str | None = Header(default=None),
    limit: int = Query(default=20, ge=1, le=50),
    cursor: str | None = Query(default=None),
    db_session: Session = Depends(get_db_session),
) -> SessionMessagesResponse | JSONResponse:
    if authorization != "Bearer mock_owner_token":
        return _unauthorized()

    ensure_default_context(db_session)

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
    authorization: str | None = Header(default=None),
    db_session: Session = Depends(get_db_session),
) -> DataEnvelope[CreateSessionMessageData] | JSONResponse:
    if authorization != "Bearer mock_owner_token":
        return _unauthorized()

    ensure_default_context(db_session)

    try:
        result = create_message(
            db_session,
            session_id=session_id,
            actor_type="owner",
            actor_id="owner_default",
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
        return payload_model

    return JSONResponse(
        status_code=status.HTTP_201_CREATED,
        content=payload_model.model_dump(mode="json"),
    )
