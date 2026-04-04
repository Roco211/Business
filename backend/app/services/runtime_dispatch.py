import logging

from app.workers.celery_app import celery_app as _celery_app
from app.workers.runtime_tasks import process_task_run

logger = logging.getLogger(__name__)


def enqueue_runtime_task(task_run_id: str) -> bool:
    try:
        process_task_run.delay(task_run_id)
    except Exception as exc:
        logger.warning("Failed to dispatch runtime task for %s: %s", task_run_id, exc)
        return False
    return True
