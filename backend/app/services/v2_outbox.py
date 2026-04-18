from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.models import V2OutboxEvent
from app.services.v2_time import utc_now_naive

PENDING_OUTBOX_STATUS = "pending"
PROCESSING_OUTBOX_STATUS = "processing"
COMPLETED_OUTBOX_STATUS = "completed"
FAILED_OUTBOX_STATUS = "failed"


class V2OutboxTransitionError(ValueError):
    pass


@dataclass(frozen=True)
class V2OutboxHealthSummary:
    tenant_id: str
    shop_id: str
    pending_count: int
    processing_count: int
    completed_count: int
    failed_count: int
    oldest_pending_at: datetime | None
    oldest_available_pending_at: datetime | None


def _load_scoped_v2_outbox_event(
    db_session: Session,
    *,
    tenant_id: str,
    shop_id: str,
    outbox_event_id: str,
) -> V2OutboxEvent | None:
    return db_session.scalar(
        select(V2OutboxEvent)
        .where(
            V2OutboxEvent.tenant_id == tenant_id,
            V2OutboxEvent.shop_id == shop_id,
            V2OutboxEvent.outbox_event_id == outbox_event_id,
        )
        .execution_options(populate_existing=True)
    )


def _require_scoped_v2_outbox_event(
    db_session: Session,
    *,
    tenant_id: str,
    shop_id: str,
    outbox_event_id: str,
) -> V2OutboxEvent:
    event = _load_scoped_v2_outbox_event(
        db_session,
        tenant_id=tenant_id,
        shop_id=shop_id,
        outbox_event_id=outbox_event_id,
    )
    if event is None:
        raise LookupError(outbox_event_id)
    return event


def claim_v2_outbox_events(
    db_session: Session,
    *,
    tenant_id: str,
    shop_id: str,
    limit: int,
    now: datetime | None = None,
) -> list[V2OutboxEvent]:
    if limit <= 0:
        return []

    claim_now = now or utc_now_naive()
    candidate_ids = db_session.scalars(
        select(V2OutboxEvent.outbox_event_id)
        .where(
            V2OutboxEvent.tenant_id == tenant_id,
            V2OutboxEvent.shop_id == shop_id,
            V2OutboxEvent.status == PENDING_OUTBOX_STATUS,
            V2OutboxEvent.available_at <= claim_now,
        )
        .order_by(
            V2OutboxEvent.available_at.asc(),
            V2OutboxEvent.created_at.asc(),
            V2OutboxEvent.outbox_event_id.asc(),
        )
        .limit(limit)
    ).all()
    if not candidate_ids:
        return []

    claimed_ids: list[str] = []
    for outbox_event_id in candidate_ids:
        result = db_session.execute(
            update(V2OutboxEvent)
            .where(
                V2OutboxEvent.outbox_event_id == outbox_event_id,
                V2OutboxEvent.status == PENDING_OUTBOX_STATUS,
            )
            .values(
                status=PROCESSING_OUTBOX_STATUS,
                attempt_count=V2OutboxEvent.attempt_count + 1,
                processed_at=None,
                updated_at=claim_now,
            )
            .execution_options(synchronize_session=False)
        )
        if result.rowcount == 1:
            claimed_ids.append(outbox_event_id)

    if not claimed_ids:
        return []

    db_session.flush()
    return db_session.scalars(
        select(V2OutboxEvent)
        .where(V2OutboxEvent.outbox_event_id.in_(claimed_ids))
        .order_by(
            V2OutboxEvent.available_at.asc(),
            V2OutboxEvent.created_at.asc(),
            V2OutboxEvent.outbox_event_id.asc(),
        )
        .execution_options(populate_existing=True)
    ).all()


def complete_v2_outbox_event(
    db_session: Session,
    *,
    tenant_id: str,
    shop_id: str,
    outbox_event_id: str,
    now: datetime | None = None,
) -> V2OutboxEvent:
    completed_at = now or utc_now_naive()
    result = db_session.execute(
        update(V2OutboxEvent)
        .where(
            V2OutboxEvent.tenant_id == tenant_id,
            V2OutboxEvent.shop_id == shop_id,
            V2OutboxEvent.outbox_event_id == outbox_event_id,
            V2OutboxEvent.status == PROCESSING_OUTBOX_STATUS,
        )
        .values(
            status=COMPLETED_OUTBOX_STATUS,
            processed_at=completed_at,
            updated_at=completed_at,
            last_error_code=None,
            last_error_message=None,
        )
        .execution_options(synchronize_session=False)
    )
    event = _require_scoped_v2_outbox_event(
        db_session,
        tenant_id=tenant_id,
        shop_id=shop_id,
        outbox_event_id=outbox_event_id,
    )
    if result.rowcount != 1:
        raise V2OutboxTransitionError(
            f"Outbox event {outbox_event_id} must be in '{PROCESSING_OUTBOX_STATUS}' status to complete; found '{event.status}'."
        )
    db_session.flush()
    return event


def fail_v2_outbox_event(
    db_session: Session,
    *,
    tenant_id: str,
    shop_id: str,
    outbox_event_id: str,
    error_code: str,
    error_message: str,
    retry_after_seconds: int | None = None,
    now: datetime | None = None,
) -> V2OutboxEvent:
    normalized_error_code = error_code.strip()
    normalized_error_message = error_message.strip()
    if not normalized_error_code:
        raise ValueError("error_code is required")
    if not normalized_error_message:
        raise ValueError("error_message is required")
    if retry_after_seconds is not None and retry_after_seconds < 0:
        raise ValueError("retry_after_seconds must be >= 0")

    failed_at = now or utc_now_naive()
    next_status = FAILED_OUTBOX_STATUS
    next_available_at = failed_at
    processed_at: datetime | None = failed_at
    if retry_after_seconds is not None:
        next_status = PENDING_OUTBOX_STATUS
        next_available_at = failed_at + timedelta(seconds=retry_after_seconds)
        processed_at = None

    result = db_session.execute(
        update(V2OutboxEvent)
        .where(
            V2OutboxEvent.tenant_id == tenant_id,
            V2OutboxEvent.shop_id == shop_id,
            V2OutboxEvent.outbox_event_id == outbox_event_id,
            V2OutboxEvent.status == PROCESSING_OUTBOX_STATUS,
        )
        .values(
            status=next_status,
            available_at=next_available_at,
            processed_at=processed_at,
            updated_at=failed_at,
            last_error_code=normalized_error_code,
            last_error_message=normalized_error_message,
        )
        .execution_options(synchronize_session=False)
    )
    event = _require_scoped_v2_outbox_event(
        db_session,
        tenant_id=tenant_id,
        shop_id=shop_id,
        outbox_event_id=outbox_event_id,
    )
    if result.rowcount != 1:
        raise V2OutboxTransitionError(
            f"Outbox event {outbox_event_id} must be in '{PROCESSING_OUTBOX_STATUS}' status to fail; found '{event.status}'."
        )
    db_session.flush()
    return event


def get_v2_outbox_health_summary(
    db_session: Session,
    *,
    tenant_id: str,
    shop_id: str,
    now: datetime | None = None,
) -> V2OutboxHealthSummary:
    health_now = now or utc_now_naive()
    pending_scope = (
        V2OutboxEvent.tenant_id == tenant_id,
        V2OutboxEvent.shop_id == shop_id,
        V2OutboxEvent.status == PENDING_OUTBOX_STATUS,
    )
    processing_scope = (
        V2OutboxEvent.tenant_id == tenant_id,
        V2OutboxEvent.shop_id == shop_id,
        V2OutboxEvent.status == PROCESSING_OUTBOX_STATUS,
    )
    completed_scope = (
        V2OutboxEvent.tenant_id == tenant_id,
        V2OutboxEvent.shop_id == shop_id,
        V2OutboxEvent.status == COMPLETED_OUTBOX_STATUS,
    )
    failed_scope = (
        V2OutboxEvent.tenant_id == tenant_id,
        V2OutboxEvent.shop_id == shop_id,
        V2OutboxEvent.status == FAILED_OUTBOX_STATUS,
    )

    pending_count = db_session.scalar(select(func.count()).where(*pending_scope)) or 0
    processing_count = db_session.scalar(select(func.count()).where(*processing_scope)) or 0
    completed_count = db_session.scalar(select(func.count()).where(*completed_scope)) or 0
    failed_count = db_session.scalar(select(func.count()).where(*failed_scope)) or 0
    oldest_pending_at = db_session.scalar(select(func.min(V2OutboxEvent.created_at)).where(*pending_scope))
    oldest_available_pending_at = db_session.scalar(
        select(func.min(V2OutboxEvent.available_at)).where(
            *pending_scope,
            V2OutboxEvent.available_at <= health_now,
        )
    )
    return V2OutboxHealthSummary(
        tenant_id=tenant_id,
        shop_id=shop_id,
        pending_count=int(pending_count),
        processing_count=int(processing_count),
        completed_count=int(completed_count),
        failed_count=int(failed_count),
        oldest_pending_at=oldest_pending_at,
        oldest_available_pending_at=oldest_available_pending_at,
    )
