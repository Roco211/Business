from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.workers.celery_app import create_celery_app


def test_celery_app_uses_redis_broker_defaults() -> None:
    celery_app = create_celery_app()

    assert celery_app.main == "ai_store_manager"
    assert celery_app.conf.broker_url == "redis://redis:6379/0"
    assert celery_app.conf.result_backend == "redis://redis:6379/0"
    assert celery_app.conf.include == ("app.workers.runtime_tasks",)
    assert "app.workers.runtime_tasks.process_task_run" in celery_app.tasks
