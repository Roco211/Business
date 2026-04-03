from fastapi import FastAPI

from app.contracts.system import HealthResponse


def create_app() -> FastAPI:
    app = FastAPI(
        title="AI Store Manager Backend",
        version="0.1.0",
    )

    @app.get("/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        return HealthResponse(status="ok")

    return app
