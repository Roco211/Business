import asyncio
from collections import defaultdict
from contextlib import suppress
from datetime import datetime, timezone
UTC = timezone.utc
from typing import Any, Callable

from fastapi import FastAPI, WebSocket

from app.contracts.session_stream import SessionStreamEventEnvelope
from app.core.ids import new_prefixed_id
from app.services.session_stream import list_session_events_after

PendingEventLoader = Callable[[object, str, int], list[Any]]


def _default_pending_event_loader(
    db_session: object,
    session_id: str,
    after_seq: int,
) -> list[SessionStreamEventEnvelope]:
    return list_session_events_after(
        db_session,
        session_id=session_id,
        after_seq=after_seq,
    )


class SessionStreamConnectionManager:
    def __init__(
        self,
        *,
        keepalive_interval_seconds: float,
        pending_poll_interval_seconds: float | None = None,
        session_factory: Callable[[], object],
        pending_event_loader: PendingEventLoader | None = None,
    ) -> None:
        self.keepalive_interval_seconds = keepalive_interval_seconds
        self.pending_poll_interval_seconds = (
            pending_poll_interval_seconds
            if pending_poll_interval_seconds is not None
            else keepalive_interval_seconds
        )
        self.session_factory = session_factory
        self.pending_event_loader = pending_event_loader or _default_pending_event_loader
        self._connections: dict[str, set[WebSocket]] = defaultdict(set)
        self._keepalive_tasks: dict[int, asyncio.Task[None]] = {}
        self._last_seq_by_connection: dict[int, int] = {}
        self._auth_validators: dict[int, Callable[[], bool] | None] = {}
        self._unauthorized_close_codes: dict[int, int] = {}
        self._pending_event_loaders: dict[int, PendingEventLoader] = {}
        self._lock = asyncio.Lock()

    async def connect(
        self,
        *,
        session_id: str,
        websocket: WebSocket,
        replay_after_seq: int,
        current_seq: int,
        auth_is_valid: Callable[[], bool] | None = None,
        unauthorized_close_code: int = 4401,
        pending_event_loader: PendingEventLoader | None = None,
    ) -> None:
        await websocket.accept()
        async with self._lock:
            self._connections[session_id].add(websocket)
            self._last_seq_by_connection[id(websocket)] = replay_after_seq
            self._auth_validators[id(websocket)] = auth_is_valid
            self._unauthorized_close_codes[id(websocket)] = unauthorized_close_code
            self._pending_event_loaders[id(websocket)] = pending_event_loader or self.pending_event_loader
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
            self._auth_validators.pop(id(websocket), None)
            self._unauthorized_close_codes.pop(id(websocket), None)
            self._pending_event_loaders.pop(id(websocket), None)
        if keepalive_task is not None:
            keepalive_task.cancel()
            with suppress(asyncio.CancelledError):
                await keepalive_task

    async def publish(self, *, session_id: str, event: SessionStreamEventEnvelope) -> None:
        async with self._lock:
            recipients = list(self._connections.get(session_id, set()))

        stale_connections: list[WebSocket] = []
        for websocket in recipients:
            if not await self._revalidate_auth_session(websocket=websocket):
                stale_connections.append(websocket)
                continue

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
        loop = asyncio.get_running_loop()
        next_keepalive_at = loop.time() + self.keepalive_interval_seconds
        sleep_interval_seconds = min(
            self.keepalive_interval_seconds,
            self.pending_poll_interval_seconds,
        )

        while True:
            await asyncio.sleep(sleep_interval_seconds)
            if not await self._flush_pending_events(session_id=session_id, websocket=websocket):
                return
            if loop.time() < next_keepalive_at:
                continue
            if not await self._revalidate_auth_session(websocket=websocket):
                return
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
            next_keepalive_at = loop.time() + self.keepalive_interval_seconds

    async def _flush_pending_events(self, *, session_id: str, websocket: WebSocket) -> bool:
        if not await self._revalidate_auth_session(websocket=websocket):
            return False

        async with self._lock:
            after_seq = self._last_seq_by_connection.get(id(websocket))
            pending_event_loader = self._pending_event_loaders.get(id(websocket), self.pending_event_loader)
        if after_seq is None:
            return False

        db_session = self.session_factory()
        try:
            pending_events = pending_event_loader(db_session, session_id, after_seq)
        finally:
            db_session.close()

        for event in pending_events:
            if not await self._revalidate_auth_session(websocket=websocket):
                return False
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
        return True

    async def _revalidate_auth_session(self, *, websocket: WebSocket) -> bool:
        async with self._lock:
            validator = self._auth_validators.get(id(websocket))
            unauthorized_close_code = self._unauthorized_close_codes.get(id(websocket), 4401)

        if validator is None:
            return True

        try:
            is_valid = validator()
        except Exception:
            is_valid = False

        if is_valid:
            return True

        with suppress(Exception):
            await websocket.close(code=unauthorized_close_code)
        return False

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
