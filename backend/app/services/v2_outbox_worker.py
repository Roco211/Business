from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

from app.services.v2_outbox_dispatch import dispatch_v2_outbox_events
from app.services.v2_time import utc_now_naive


@dataclass(frozen=True)
class V2OutboxDrainResult:
    tenant_id: str
    shop_id: str
    batch_limit: int
    max_batches: int
    batches_run: int
    claimed_count: int
    completed_count: int
    retried_count: int
    failed_count: int
    drained_at: datetime


def drain_v2_outbox_events(
    db_session: Session,
    *,
    tenant_id: str,
    shop_id: str,
    batch_limit: int = 50,
    max_batches: int = 10,
    retry_after_seconds: int | None = 60,
    now: datetime | None = None,
) -> V2OutboxDrainResult:
    if batch_limit <= 0:
        raise ValueError("batch_limit must be > 0")
    if max_batches <= 0:
        raise ValueError("max_batches must be > 0")

    drain_now = now or utc_now_naive()
    batches_run = 0
    claimed_count = 0
    completed_count = 0
    retried_count = 0
    failed_count = 0

    for _ in range(max_batches):
        batch_result = dispatch_v2_outbox_events(
            db_session,
            tenant_id=tenant_id,
            shop_id=shop_id,
            limit=batch_limit,
            retry_after_seconds=retry_after_seconds,
            now=drain_now,
        )
        if batch_result.claimed_count == 0:
            break

        batches_run += 1
        claimed_count += batch_result.claimed_count
        completed_count += batch_result.completed_count
        retried_count += batch_result.retried_count
        failed_count += batch_result.failed_count

    return V2OutboxDrainResult(
        tenant_id=tenant_id,
        shop_id=shop_id,
        batch_limit=batch_limit,
        max_batches=max_batches,
        batches_run=batches_run,
        claimed_count=claimed_count,
        completed_count=completed_count,
        retried_count=retried_count,
        failed_count=failed_count,
        drained_at=drain_now,
    )
