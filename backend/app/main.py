from fastapi import FastAPI

from app.api.router import api_router


def create_app() -> FastAPI:
    app = FastAPI(
        title="AI Store Manager Backend",
        version="0.1.0",
    )
    app.include_router(api_router)
    return app
