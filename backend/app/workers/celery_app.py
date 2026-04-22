import os

from celery import Celery

from app.core.config import get_settings


_V2_OUTBOX_DUE_SWEEP_TASK = "app.workers.v2_outbox_due_tasks.drain_due_v2_outbox_scopes"


def _build_v2_outbox_due_sweep_schedule(settings) -> dict[str, dict[str, object]]:
    return {
        "v2-outbox-due-scope-sweep": {
            "task": _V2_OUTBOX_DUE_SWEEP_TASK,
            "schedule": settings.v2_outbox_due_sweep_interval_seconds,
            "kwargs": {
                "scope_limit": settings.v2_outbox_due_sweep_scope_limit,
                "batch_limit_per_scope": settings.v2_outbox_due_sweep_batch_limit_per_scope,
                "max_batches_per_scope": settings.v2_outbox_due_sweep_max_batches_per_scope,
                "retry_after_seconds": settings.v2_outbox_due_sweep_retry_after_seconds,
            },
        }
    }


def _env_flag(name: str, *, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value not in ("0", "false", "False")


def create_celery_app() -> Celery:
    settings = get_settings()
    celery = Celery(
        "ai_store_manager",
        broker=settings.redis_url,
        backend=settings.redis_url,
        include=(
            "app.workers.runtime_tasks",
            "app.workers.v2_outbox_tasks",
            "app.workers.v2_outbox_due_tasks",
        ),
    )
    celery.conf.beat_schedule = _build_v2_outbox_due_sweep_schedule(settings)
    celery.conf.task_always_eager = _env_flag("CELERY_TASK_ALWAYS_EAGER", default=False)
    celery.conf.task_store_eager_result = False
    celery.set_default()
    return celery


celery_app = create_celery_app()
celery_app.loader.import_default_modules()
