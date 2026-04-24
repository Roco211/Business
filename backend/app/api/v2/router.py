from fastapi import APIRouter

from app.api.v2.routes.alerts import router as alerts_router
from app.api.v2.routes.audit import router as audit_router
from app.api.v2.routes.catalog import router as catalog_router
from app.api.v2.routes.chat import router as chat_router
from app.api.v2.routes.conversation import router as conversation_router
from app.api.v2.routes.dashboard import router as dashboard_router
from app.api.v2.routes.health import router as health_router
from app.api.v2.routes.identity import router as identity_router
from app.api.v2.routes.internal import router as internal_router
from app.api.v2.routes.inventory import router as inventory_router
from app.api.v2.routes.ledger import router as ledger_router
from app.api.v2.routes.media_ai import documents_router, router as media_ai_router
from app.api.v2.routes.photo import router as photo_router
from app.api.v2.routes.voice import router as voice_router

v2_router = APIRouter()
v2_router.include_router(chat_router)
v2_router.include_router(conversation_router)
v2_router.include_router(health_router)
v2_router.include_router(identity_router)
v2_router.include_router(internal_router)
v2_router.include_router(inventory_router)
v2_router.include_router(catalog_router)
v2_router.include_router(dashboard_router)
v2_router.include_router(ledger_router)
v2_router.include_router(media_ai_router)
v2_router.include_router(documents_router)
v2_router.include_router(photo_router)
v2_router.include_router(voice_router)
v2_router.include_router(alerts_router)
v2_router.include_router(audit_router)
