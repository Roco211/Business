from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.db.session import get_session_factory
from app.models import SessionRecord
from app.realtime.connection_manager import get_session_stream_manager

router = APIRouter(tags=["session-stream"])
UNAUTHORIZED_CLOSE_CODE = 4401
SESSION_NOT_FOUND_CLOSE_CODE = 4404


async def _close_websocket(websocket: WebSocket, *, code: int) -> None:
    await websocket.accept()
    await websocket.close(code=code)


@router.websocket("/api/v1/ws/sessions/{session_id}")
async def session_stream_websocket(websocket: WebSocket, session_id: str) -> None:
    token = websocket.query_params.get("token")
    if token != "mock_owner_token":
        await _close_websocket(websocket, code=UNAUTHORIZED_CLOSE_CODE)
        return

    session_factory = get_session_factory()
    db_session = session_factory()
    manager = get_session_stream_manager(websocket.app)
    connected = False

    try:
        session = db_session.get(SessionRecord, session_id)
        if session is None:
            await _close_websocket(websocket, code=SESSION_NOT_FOUND_CLOSE_CODE)
            return

        await manager.connect(
            session_id=session_id,
            websocket=websocket,
            last_seq=int(session.last_event_seq),
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
