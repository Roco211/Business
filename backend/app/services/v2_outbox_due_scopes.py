from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import V2OutboxEvent
from app.services.v2_outbox import PENDING_OUTBOX_STATUS
from app.services.v2_outbox_worker import drain_v2_outbox_events
from app.services.v2_time import utc_now_naive


@dataclass(frozen=True)
class V2OutboxDueScopesDrainResult:
    scope_limit: int
    batch_limit_per_scope: int
    max_batches_per_scope: int
    scope_count: int
    claimed_count: int
    completed_count: int
    retried_count: int
    failed_count: int
    drained_at: datetime


def drain_due_v2_outbox_scopes(
    db_session: Session,
    *,
    scope_limit: int = 20,
    batch_limit_per_scope: int = 50,
    max_batches_per_scope: int = 10,
    retry_after_seconds: int | None = 60,
    now: datetime | None = None,
) -> V2OutboxDueScopesDrainResult:
    if scope_limit <= 0:
        raise ValueError("scope_limit must be > 0")
    if batch_limit_per_scope <= 0:
        raise ValueError("batch_limit_per_scope must be > 0")
    if max_batches_per_scope <= 0:
        raise ValueError("max_batches_per_scope must be > 0")

    drain_now = now or utc_now_naive()
    due_scopes = db_session.execute(
        select(V2OutboxEvent.tenant_id, V2OutboxEvent.shop_id)
        .where(
            V2OutboxEvent.status == PENDING_OUTBOX_STATUS,
            V2OutboxEvent.available_at <= drain_now,
        )
        .group_by(V2OutboxEvent.tenant_id, V2OutboxEvent.shop_id)
        .order_by(
            func.min(V2OutboxEvent.available_at).asc(),
            V2OutboxEvent.tenant_id.asc(),
            V2OutboxEvent.shop_id.asc(),
        )
        .limit(scope_limit)
    ).all()

    claimed_count = 0
    completed_count = 0
    retried_count = 0
    failed_count = 0

    for tenant_id, shop_id in due_scopes:
        batch_result = drain_v2_outbox_events(
            db_session,
            tenant_id=tenant_id,
            shop_id=shop_id,
            batch_limit=batch_limit_per_scope,
            max_batches=max_batches_per_scope,
            retry_after_seconds=retry_after_seconds,
            now=drain_now,
        )
        claimed_count += batch_result.claimed_count
        completed_count += batch_result.completed_count
        retried_count += batch_result.retried_count
        failed_count += batch_result.failed_count

    return V2OutboxDueScopesDrainResult(
        scope_limit=scope_limit,
        batch_limit_per_scope=batch_limit_per_scope,
        max_batches_per_scope=max_batches_per_scope,
        scope_count=len(due_scopes),
        claimed_count=claimed_count,
        completed_count=completed_count,
        retried_count=retried_count,
        failed_count=failed_count,
        drained_at=drain_now,
    )
