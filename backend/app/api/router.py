from fastapi import APIRouter

from app.api.routes.auth import router as auth_router
from app.api.routes.health import router as health_router
from app.api.routes.messages import router as messages_router
from app.api.routes.sessions import router as sessions_router
from app.api.routes.task_runs import router as task_runs_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(auth_router)
api_router.include_router(messages_router)
api_router.include_router(sessions_router)
api_router.include_router(task_runs_router)
