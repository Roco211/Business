from fastapi import APIRouter

from app.api.routes.audit_logs import router as audit_logs_router
from app.api.routes.alerts import router as alerts_router
from app.api.routes.auth import router as auth_router
from app.api.routes.confirmations import router as confirmations_router
from app.api.routes.dashboard import router as dashboard_router
from app.api.routes.health import router as health_router
from app.api.routes.inventory_items import router as inventory_items_router
from app.api.routes.inventory_events import router as inventory_events_router
from app.api.routes.messages import router as messages_router
from app.api.routes.sessions import router as sessions_router
from app.api.routes.task_runs import router as task_runs_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(audit_logs_router)
api_router.include_router(alerts_router)
api_router.include_router(auth_router)
api_router.include_router(confirmations_router)
api_router.include_router(dashboard_router)
api_router.include_router(inventory_events_router)
api_router.include_router(inventory_items_router)
api_router.include_router(messages_router)
api_router.include_router(sessions_router)
api_router.include_router(task_runs_router)
