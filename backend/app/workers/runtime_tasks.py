from celery import shared_task

from app.db.session import get_session_factory
from app.runtime.processor import process_task_run as run_runtime_processor


@shared_task(name="app.workers.runtime_tasks.process_task_run")
def process_task_run(task_run_id: str) -> dict[str, str | None]:
    db_session = get_session_factory()()
    try:
        result = run_runtime_processor(db_session, task_run_id)
        return {
            "status": result.status,
            "task_run_id": result.task_run_id,
            "task_type": result.task_type,
            "error_code": result.error_code,
        }
    finally:
        db_session.close()
