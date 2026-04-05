from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect, status
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps.auth import AuthenticatedContext, require_authenticated_context, resolve_authenticated_context
from app.contracts.common import DataEnvelope, ErrorBody, ErrorEnvelope
from app.contracts.session_stream import SessionStreamEventEnvelope
from app.db.session import get_db_session, get_session_factory
from app.models import SessionRecord
from app.realtime.connection_manager import get_session_stream_manager
from app.services.session_stream import list_session_events_after

router = APIRouter(tags=["session-stream"])
UNAUTHORIZED_CLOSE_CODE = 4401
SESSION_NOT_FOUND_CLOSE_CODE = 4404


def _build_unauthorized_response() -> JSONResponse:
    payload = ErrorEnvelope(
        error=ErrorBody(
            code="unauthorized",
            message="Unauthorized",
            details=[],
        )
    )
    return JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content=payload.model_dump(),
    )


@router.get(
    "/api/v1/sessions/{session_id}/stream-events",
    response_model=DataEnvelope[list[SessionStreamEventEnvelope]],
    responses={401: {"model": ErrorEnvelope, "description": "Unauthorized"}},
)
def list_stream_events(
    session_id: str,
    after_seq: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    auth: AuthenticatedContext = Depends(require_authenticated_context),
    db_session: Session = Depends(get_db_session),
) -> DataEnvelope[list[SessionStreamEventEnvelope]] | JSONResponse:
    session = db_session.scalar(
        select(SessionRecord).where(
            SessionRecord.session_id == session_id,
            SessionRecord.shop_id == auth.shop_id,
        )
    )
    if session is None:
        payload = ErrorEnvelope(
            error=ErrorBody(
                code="session_not_found",
                message="Session not found",
                details=[],
            )
        )
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content=payload.model_dump())

    return DataEnvelope(
        data=list_session_events_after(
            db_session,
            session_id=session_id,
            after_seq=after_seq,
            limit=limit,
        )
    )


async def _close_websocket(websocket: WebSocket, *, code: int) -> None:
    await websocket.accept()
    await websocket.close(code=code)


@router.websocket("/api/v1/ws/sessions/{session_id}")
async def session_stream_websocket(websocket: WebSocket, session_id: str) -> None:
    token = websocket.query_params.get("token")
    session_factory = get_session_factory()
    db_session = session_factory()
    manager = get_session_stream_manager(websocket.app)
    connected = False

    try:
        if token is None or token == "":
            await _close_websocket(websocket, code=UNAUTHORIZED_CLOSE_CODE)
            return

        auth = resolve_authenticated_context(db_session, bearer_token=token)
        if auth is None:
            await _close_websocket(websocket, code=UNAUTHORIZED_CLOSE_CODE)
            return

        session = db_session.scalar(
            select(SessionRecord).where(
                SessionRecord.session_id == session_id,
                SessionRecord.shop_id == auth.shop_id,
            )
        )
        if session is None:
            await _close_websocket(websocket, code=SESSION_NOT_FOUND_CLOSE_CODE)
            return

        after_seq_param = websocket.query_params.get("after_seq")
        if after_seq_param is None or after_seq_param == "":
            replay_after_seq = int(session.last_event_seq)
        else:
            try:
                replay_after_seq = max(0, int(after_seq_param))
            except ValueError:
                replay_after_seq = int(session.last_event_seq)

        await manager.connect(
            session_id=session_id,
            websocket=websocket,
            replay_after_seq=replay_after_seq,
            current_seq=int(session.last_event_seq),
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
