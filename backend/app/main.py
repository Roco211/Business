import logging
from pathlib import Path
import uuid

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.api.deps.auth import AuthUnauthorizedError
from app.api.deps.v2_context import V2ContextRequiredError, V2ForbiddenError, V2UnauthorizedError
from app.core.config import get_settings
from app.core.production_middleware import (
    InMemoryRateLimiter,
    build_rate_limit_middleware,
    security_headers_middleware,
)
from app.contracts.common import ErrorBody, ErrorEnvelope
from app.contracts.v2.common import V2ErrorBody, V2ErrorEnvelope
from app.db.session import get_session_factory
from app.api.router import api_router
from app.realtime.connection_manager import SessionStreamConnectionManager

logger = logging.getLogger(__name__)


def register_error_logging_middleware(app: FastAPI) -> None:
    @app.middleware("http")
    async def _log_unhandled_errors(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or f"req_{uuid.uuid4().hex[:16]}"
        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = request_id
            return response
        except Exception:
            logger.exception("Unhandled request error request_id=%s method=%s path=%s", request_id, request.method, request.url.path)
            return JSONResponse(
                status_code=500,
                content=ErrorEnvelope(
                    error=ErrorBody(
                        code="internal_server_error",
                        message="Internal server error",
                        details=[{"field": "request_id", "message": request_id}],
                    )
                ).model_dump(),
                headers={"X-Request-ID": request_id},
            )


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(Exception)
    async def _handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        request_id = request.headers.get("X-Request-ID") or f"req_{uuid.uuid4().hex[:16]}"
        logger.exception("Unhandled request error request_id=%s method=%s path=%s", request_id, request.method, request.url.path, exc_info=exc)
        return JSONResponse(
            status_code=500,
            content=ErrorEnvelope(
                error=ErrorBody(
                    code="internal_server_error",
                    message="Internal server error",
                    details=[{"request_id": request_id}],
                )
            ).model_dump(),
            headers={"X-Request-ID": request_id},
        )

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

    @app.exception_handler(V2ForbiddenError)
    async def _handle_v2_forbidden(_, exc: V2ForbiddenError) -> JSONResponse:
        return JSONResponse(
            status_code=403,
            content=V2ErrorEnvelope(
                error=V2ErrorBody(code="permission_denied", message="Permission denied", details=[{"field": "permission", "message": exc.permission}])
            ).model_dump(),
        )


def register_h5_static_routes(app: FastAPI) -> None:
    h5_root = Path(__file__).resolve().parent / "static" / "h5"
    index_file = h5_root / "index.html"
    assets_dir = h5_root / "assets"
    if not index_file.exists():
        return

    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="h5-assets")

    @app.get("/", include_in_schema=False)
    def _serve_h5_index() -> FileResponse:
        return FileResponse(index_file)

    @app.head("/", include_in_schema=False)
    def _head_h5_index() -> FileResponse:
        return FileResponse(index_file)

    @app.get("/{full_path:path}", include_in_schema=False)
    def _serve_h5_spa(full_path: str) -> FileResponse:
        if full_path.startswith("api/") or full_path in {"health", "docs", "redoc", "openapi.json"}:
            raise HTTPException(status_code=404)
        candidate = h5_root / full_path
        if candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(index_file)


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="AI Store Manager Backend",
        version="0.1.0",
        # Use field names instead of aliases in JSON responses
        # to avoid Hermes environment JSON masking of sensitive field names
        json_encoders={BaseModel: lambda m: m.model_dump(by_alias=False)},
    )
    cors_origins = settings.cors_origins()
    if cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=cors_origins,
            allow_credentials=True,
            allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
            allow_headers=["Authorization", "Content-Type", "X-Context-Token", "X-V2-Context-Token", "X-Request-ID"],
        )
    if settings.security_headers_enabled:
        app.middleware("http")(security_headers_middleware)
    if settings.rate_limit_per_minute > 0:
        app.middleware("http")(
            build_rate_limit_middleware(InMemoryRateLimiter(settings.rate_limit_per_minute))
        )
    app.state.session_stream_manager = SessionStreamConnectionManager(
        keepalive_interval_seconds=settings.session_stream_keepalive_seconds,
        pending_poll_interval_seconds=settings.session_stream_pending_poll_seconds,
        session_factory=get_session_factory(),
    )
    register_error_logging_middleware(app)
    register_exception_handlers(app)
    app.include_router(api_router)
    register_h5_static_routes(app)
    return app


app = create_app()
