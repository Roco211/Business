from app.db.session import get_session_factory
from app.services.v2_outbox_due_scopes import (
    drain_due_v2_outbox_scopes as run_due_scope_drain,
)
from app.workers.celery_app import celery_app


@celery_app.task(name="app.workers.v2_outbox_due_tasks.drain_due_v2_outbox_scopes")
def drain_due_v2_outbox_scopes(
    scope_limit: int = 20,
    batch_limit_per_scope: int = 50,
    max_batches_per_scope: int = 10,
    retry_after_seconds: int | None = 60,
) -> dict[str, object]:
    db_session = get_session_factory()()
    try:
        result = run_due_scope_drain(
            db_session,
            scope_limit=scope_limit,
            batch_limit_per_scope=batch_limit_per_scope,
            max_batches_per_scope=max_batches_per_scope,
            retry_after_seconds=retry_after_seconds,
        )
        db_session.commit()
        return {
            "scope_limit": result.scope_limit,
            "batch_limit_per_scope": result.batch_limit_per_scope,
            "max_batches_per_scope": result.max_batches_per_scope,
            "scope_count": result.scope_count,
            "claimed_count": result.claimed_count,
            "completed_count": result.completed_count,
            "retried_count": result.retried_count,
            "failed_count": result.failed_count,
            "drained_at": result.drained_at.isoformat(),
        }
    except Exception:
        db_session.rollback()
        raise
    finally:
        db_session.close()
