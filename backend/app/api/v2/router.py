from fastapi import APIRouter

from app.api.v2.routes.conversation import router as conversation_router
from app.api.v2.routes.health import router as health_router
from app.api.v2.routes.identity import router as identity_router
from app.api.v2.routes.internal import router as internal_router
from app.api.v2.routes.inventory import router as inventory_router
from app.api.v2.routes.media_ai import router as media_ai_router

v2_router = APIRouter()
v2_router.include_router(conversation_router)
v2_router.include_router(health_router)
v2_router.include_router(identity_router)
v2_router.include_router(internal_router)
v2_router.include_router(inventory_router)
v2_router.include_router(media_ai_router)
