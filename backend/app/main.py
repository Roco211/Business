from fastapi import FastAPI

from app.core.config import get_settings
from app.api.router import api_router
from app.realtime.connection_manager import SessionStreamConnectionManager


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="AI Store Manager Backend",
        version="0.1.0",
    )
    app.state.session_stream_manager = SessionStreamConnectionManager(
        keepalive_interval_seconds=settings.session_stream_keepalive_seconds
    )
    app.include_router(api_router)
    return app
