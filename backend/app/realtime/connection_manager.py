import asyncio
from collections import defaultdict
from contextlib import suppress
from datetime import UTC, datetime
from typing import Callable

from fastapi import FastAPI, WebSocket

from app.contracts.session_stream import SessionStreamEventEnvelope
from app.core.ids import new_prefixed_id
from app.services.session_stream import list_session_events_after


class SessionStreamConnectionManager:
    def __init__(
        self,
        *,
        keepalive_interval_seconds: float,
        session_factory: Callable[[], object],
    ) -> None:
        self.keepalive_interval_seconds = keepalive_interval_seconds
        self.session_factory = session_factory
        self._connections: dict[str, set[WebSocket]] = defaultdict(set)
        self._keepalive_tasks: dict[int, asyncio.Task[None]] = {}
        self._last_seq_by_connection: dict[int, int] = {}
        self._lock = asyncio.Lock()

    async def connect(
        self,
        *,
        session_id: str,
        websocket: WebSocket,
        replay_after_seq: int,
        current_seq: int,
    ) -> None:
        await websocket.accept()
        async with self._lock:
            self._connections[session_id].add(websocket)
            self._last_seq_by_connection[id(websocket)] = replay_after_seq
            self._keepalive_tasks[id(websocket)] = asyncio.create_task(
                self._keepalive_loop(session_id=session_id, websocket=websocket),
                name=f"session-stream-keepalive-{session_id}",
            )
        await self._send_event(
            websocket,
            self._build_ephemeral_event(
                session_id=session_id,
                event_type="session.ready",
                seq=current_seq,
            ),
        )
        await self._flush_pending_events(session_id=session_id, websocket=websocket)

    async def disconnect(self, *, session_id: str, websocket: WebSocket) -> None:
        async with self._lock:
            connections = self._connections.get(session_id)
            if connections is not None:
                connections.discard(websocket)
                if not connections:
                    self._connections.pop(session_id, None)

            keepalive_task = self._keepalive_tasks.pop(id(websocket), None)
            self._last_seq_by_connection.pop(id(websocket), None)
        if keepalive_task is not None:
            keepalive_task.cancel()
            with suppress(asyncio.CancelledError):
                await keepalive_task

    async def publish(self, *, session_id: str, event: SessionStreamEventEnvelope) -> None:
        async with self._lock:
            recipients = list(self._connections.get(session_id, set()))

        stale_connections: list[WebSocket] = []
        for websocket in recipients:
            async with self._lock:
                last_seq = self._last_seq_by_connection.get(id(websocket))
            if last_seq is None or event.seq <= last_seq:
                continue
            try:
                await self._send_event(websocket, event)
                async with self._lock:
                    if id(websocket) in self._last_seq_by_connection:
                        self._last_seq_by_connection[id(websocket)] = max(
                            self._last_seq_by_connection[id(websocket)],
                            event.seq,
                        )
            except Exception:
                stale_connections.append(websocket)

        for websocket in stale_connections:
            await self.disconnect(session_id=session_id, websocket=websocket)

    async def _keepalive_loop(self, *, session_id: str, websocket: WebSocket) -> None:
        while True:
            await asyncio.sleep(self.keepalive_interval_seconds)
            await self._flush_pending_events(session_id=session_id, websocket=websocket)
            async with self._lock:
                seq = self._last_seq_by_connection.get(id(websocket), 0)
            await self._send_event(
                websocket,
                self._build_ephemeral_event(
                    session_id=session_id,
                    event_type="stream.keepalive",
                    seq=seq,
                ),
            )

    async def _flush_pending_events(self, *, session_id: str, websocket: WebSocket) -> None:
        async with self._lock:
            after_seq = self._last_seq_by_connection.get(id(websocket))
        if after_seq is None:
            return

        db_session = self.session_factory()
        try:
            pending_events = list_session_events_after(
                db_session,
                session_id=session_id,
                after_seq=after_seq,
            )
        finally:
            db_session.close()

        for event in pending_events:
            async with self._lock:
                current_seq = self._last_seq_by_connection.get(id(websocket))
            if current_seq is None or event.seq <= current_seq:
                continue
            await self._send_event(websocket, event)
            async with self._lock:
                if id(websocket) in self._last_seq_by_connection:
                    self._last_seq_by_connection[id(websocket)] = max(
                        self._last_seq_by_connection[id(websocket)],
                        event.seq,
                    )

    async def _send_event(self, websocket: WebSocket, event: SessionStreamEventEnvelope) -> None:
        await websocket.send_json(event.model_dump(mode="json"))

    def _build_ephemeral_event(
        self,
        *,
        session_id: str,
        event_type: str,
        seq: int,
    ) -> SessionStreamEventEnvelope:
        return SessionStreamEventEnvelope(
            event_id=new_prefixed_id("ws_evt"),
            seq=seq,
            event_type=event_type,
            session_id=session_id,
            task_run_id=None,
            message_id=None,
            occurred_at=datetime.now(UTC).replace(tzinfo=None),
            data={},
        )


def get_session_stream_manager(app: FastAPI) -> SessionStreamConnectionManager:
    return app.state.session_stream_manager  # type: ignore[no-any-return]
