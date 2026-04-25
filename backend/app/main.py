from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

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
    app.state.session_stream_manager = SessionStreamConnectionManager(
        keepalive_interval_seconds=settings.session_stream_keepalive_seconds,
        pending_poll_interval_seconds=settings.session_stream_pending_poll_seconds,
        session_factory=get_session_factory(),
    )
    register_exception_handlers(app)
    app.include_router(api_router)
    register_h5_static_routes(app)
    return app


app = create_app()
