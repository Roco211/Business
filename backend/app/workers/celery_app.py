from celery import Celery

from app.core.config import get_settings


def create_celery_app() -> Celery:
    settings = get_settings()
    celery = Celery(
        "ai_store_manager",
        broker=settings.redis_url,
        backend=settings.redis_url,
        include=("app.workers.runtime_tasks",),
    )
    celery.set_default()
    return celery


celery_app = create_celery_app()
