from app.db.session import get_session_factory
from app.services.v2_outbox_worker import drain_v2_outbox_events as run_outbox_drain
from app.workers.celery_app import celery_app


@celery_app.task(name="app.workers.v2_outbox_tasks.drain_v2_outbox")
def drain_v2_outbox(
    tenant_id: str,
    shop_id: str,
    batch_limit: int = 50,
    max_batches: int = 10,
    retry_after_seconds: int | None = 60,
) -> dict[str, object]:
    db_session = get_session_factory()()
    try:
        result = run_outbox_drain(
            db_session,
            tenant_id=tenant_id,
            shop_id=shop_id,
            batch_limit=batch_limit,
            max_batches=max_batches,
            retry_after_seconds=retry_after_seconds,
        )
        db_session.commit()
        return {
            "tenant_id": result.tenant_id,
            "shop_id": result.shop_id,
            "batch_limit": result.batch_limit,
            "max_batches": result.max_batches,
            "batches_run": result.batches_run,
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
