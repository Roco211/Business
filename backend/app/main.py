from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.api.deps.auth import AuthUnauthorizedError
from app.api.deps.v2_context import V2ContextRequiredError, V2UnauthorizedError
from app.core.config import get_settings
from app.contracts.common import ErrorBody, ErrorEnvelope
from app.contracts.v2.common import V2ErrorBody, V2ErrorEnvelope
from app.db.session import get_session_factory
from app.api.router import api_router
from app.realtime.connection_manager import SessionStreamConnectionManager


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AuthUnauthorizedError)
    async def _handle_auth_unauthorized(_, __) -> JSONResponse:
        return JSONResponse(
            status_code=401,
            content=ErrorEnvelope(
                error=ErrorBody(code="unauthorized", message="Unauthorized", details=[])
            ).model_dump(),
        )

    @app.exception_handler(V2UnauthorizedError)
    async def _handle_v2_unauthorized(_, __) -> JSONResponse:
        return JSONResponse(
            status_code=401,
            content=V2ErrorEnvelope(
                error=V2ErrorBody(code="unauthorized", message="Unauthorized")
            ).model_dump(),
        )

    @app.exception_handler(V2ContextRequiredError)
    async def _handle_v2_context_required(_, __) -> JSONResponse:
        return JSONResponse(
            status_code=401,
            content=V2ErrorEnvelope(
                error=V2ErrorBody(code="context_required", message="Context required")
            ).model_dump(),
        )


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="AI Store Manager Backend",
        version="0.1.0",
    )
    app.state.session_stream_manager = SessionStreamConnectionManager(
        keepalive_interval_seconds=settings.session_stream_keepalive_seconds,
        pending_poll_interval_seconds=settings.session_stream_pending_poll_seconds,
        session_factory=get_session_factory(),
    )
    register_exception_handlers(app)
    app.include_router(api_router)
    return app
