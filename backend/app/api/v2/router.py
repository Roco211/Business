from fastapi import APIRouter

from app.api.v2.routes.conversation import router as conversation_router
from app.api.v2.routes.health import router as health_router
from app.api.v2.routes.identity import router as identity_router

v2_router = APIRouter()
v2_router.include_router(conversation_router)
v2_router.include_router(health_router)
v2_router.include_router(identity_router)
