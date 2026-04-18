from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.workers.celery_app import create_celery_app


def test_celery_app_uses_redis_broker_defaults() -> None:
    celery_app = create_celery_app()

    assert celery_app.main == "ai_store_manager"
    assert celery_app.conf.broker_url == "redis://redis:6379/0"
    assert celery_app.conf.result_backend == "redis://redis:6379/0"
    assert celery_app.conf.include == (
        "app.workers.runtime_tasks",
        "app.workers.v2_outbox_tasks",
        "app.workers.v2_outbox_due_tasks",
    )
    assert "app.workers.runtime_tasks.process_task_run" in celery_app.tasks
    assert "app.workers.v2_outbox_tasks.drain_v2_outbox" in celery_app.tasks
    assert "app.workers.v2_outbox_due_tasks.drain_due_v2_outbox_scopes" in celery_app.tasks


def test_celery_app_registers_due_scope_beat_schedule_defaults() -> None:
    celery_app = create_celery_app()

    assert celery_app.conf.beat_schedule == {
        "v2-outbox-due-scope-sweep": {
            "task": "app.workers.v2_outbox_due_tasks.drain_due_v2_outbox_scopes",
            "schedule": 30,
            "kwargs": {
                "scope_limit": 20,
                "batch_limit_per_scope": 50,
                "max_batches_per_scope": 10,
                "retry_after_seconds": 60,
            },
        }
    }


def test_celery_app_uses_due_scope_beat_schedule_env_overrides(monkeypatch) -> None:
    monkeypatch.setenv("V2_OUTBOX_DUE_SWEEP_INTERVAL_SECONDS", "45")
    monkeypatch.setenv("V2_OUTBOX_DUE_SWEEP_SCOPE_LIMIT", "7")
    monkeypatch.setenv("V2_OUTBOX_DUE_SWEEP_BATCH_LIMIT_PER_SCOPE", "8")
    monkeypatch.setenv("V2_OUTBOX_DUE_SWEEP_MAX_BATCHES_PER_SCOPE", "2")
    monkeypatch.setenv("V2_OUTBOX_DUE_SWEEP_RETRY_AFTER_SECONDS", "120")

    celery_app = create_celery_app()

    assert celery_app.conf.beat_schedule == {
        "v2-outbox-due-scope-sweep": {
            "task": "app.workers.v2_outbox_due_tasks.drain_due_v2_outbox_scopes",
            "schedule": 45,
            "kwargs": {
                "scope_limit": 7,
                "batch_limit_per_scope": 8,
                "max_batches_per_scope": 2,
                "retry_after_seconds": 120,
            },
        }
    }
