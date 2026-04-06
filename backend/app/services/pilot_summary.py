from collections import defaultdict
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.contracts.system import (
    PilotSummaryConfirmationData,
    PilotSummaryData,
    PilotSummaryTimeWindowData,
)
from app.models import AuditLog, Confirmation, SessionRecord, TaskRun


def build_pilot_summary(
    db_session: Session,
    *,
    shop_id: str,
    hours: int,
    trial_provider_profile: str,
) -> PilotSummaryData:
    ended_at = datetime.now(UTC).replace(tzinfo=None)
    started_at = ended_at - timedelta(hours=hours)

    task_totals: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    task_rows = db_session.execute(
        select(TaskRun.task_type, TaskRun.status)
        .join(SessionRecord, SessionRecord.session_id == TaskRun.session_id)
        .where(
            SessionRecord.shop_id == shop_id,
            TaskRun.created_at >= started_at,
            TaskRun.created_at <= ended_at,
        )
    ).all()
    for task_type, status in task_rows:
        task_totals[str(task_type)][str(status)] += 1

    confirmation_rows = db_session.execute(
        select(Confirmation.status, Confirmation.created_at, Confirmation.resolved_at)
        .join(TaskRun, TaskRun.task_run_id == Confirmation.task_run_id)
        .join(SessionRecord, SessionRecord.session_id == TaskRun.session_id)
        .where(SessionRecord.shop_id == shop_id)
    ).all()
    created_count = 0
    approved_count = 0
    rejected_count = 0
    for status, created_at, resolved_at in confirmation_rows:
        if started_at <= created_at <= ended_at:
            created_count += 1
        if status == "approved" and resolved_at is not None and started_at <= resolved_at <= ended_at:
            approved_count += 1
        if status == "rejected" and resolved_at is not None and started_at <= resolved_at <= ended_at:
            rejected_count += 1

    low_confidence_count = 0
    fallback_count = 0
    provider_failures: dict[str, int] = defaultdict(int)
    telemetry_rows = db_session.scalars(
        select(AuditLog)
        .where(
            AuditLog.shop_id == shop_id,
            AuditLog.scope == "pilot",
            AuditLog.action == "runtime.provider_telemetry",
            AuditLog.created_at >= started_at,
            AuditLog.created_at <= ended_at,
        )
        .order_by(AuditLog.created_at.desc(), AuditLog.audit_log_id.desc())
    ).all()
    for audit_log in telemetry_rows:
        metadata = audit_log.metadata_json
        if str(metadata.get("trial_provider_profile") or "") != trial_provider_profile:
            continue
        if bool(metadata.get("low_confidence")):
            low_confidence_count += 1
        if bool(metadata.get("used_fallback")):
            fallback_count += 1
        error_code = metadata.get("error_code")
        if isinstance(error_code, str) and error_code:
            provider_failures[error_code] += 1

    return PilotSummaryData(
        time_window=PilotSummaryTimeWindowData(
            hours=hours,
            started_at=started_at.isoformat(),
            ended_at=ended_at.isoformat(),
        ),
        task_totals={task_type: dict(statuses) for task_type, statuses in task_totals.items()},
        confirmations=PilotSummaryConfirmationData(
            created=created_count,
            approved=approved_count,
            rejected=rejected_count,
        ),
        low_confidence_count=low_confidence_count,
        fallback_count=fallback_count,
        provider_failures=dict(provider_failures),
        trial_provider_profile=trial_provider_profile,
    )
