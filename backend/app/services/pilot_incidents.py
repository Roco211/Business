from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
UTC = timezone.utc, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.contracts.system import (
    IncidentTaskDiagnosticReplayData,
    OperatorDiagnosticsAffectedTaskData,
    OperatorDiagnosticsData,
    OperatorDiagnosticsLatestShiftBundleData,
    IncidentTimelineConfirmationData,
    IncidentTimelineData,
    IncidentTimelineEntryData,
    IncidentTimelineSessionEventData,
    IncidentTimelineSummaryData,
    IncidentTimelineTaskData,
    OperatorViewBackfillData,
    OperatorViewBackfillSnapshotData,
    PilotSummaryTimeWindowData,
    ShiftBundleExportRecordData,
)
from app.models import AuditLog, Confirmation, SessionRecord, SessionStreamEvent, TaskRun
from app.services.audit_logs import (
    append_pilot_operator_view_backfill_audit_log,
    append_pilot_shift_bundle_export_audit_log,
    append_pilot_task_diagnostic_replayed_audit_log,
)
from app.services.pilot_control import get_or_create_pilot_control

SOURCE_PROVIDER_TELEMETRY = "provider-telemetry"
SOURCE_CUTOVER_TRANSITION = "cutover-transition"
SEVERITY_CRITICAL = "critical"
SEVERITY_DEGRADED = "degraded"
NON_INCIDENT_OUTCOMES = {"completed"}
ACTION_TASK_DIAGNOSTIC_REPLAYED = "pilot.task_diagnostic_replayed"
ACTION_OPERATOR_VIEW_BACKFILLED = "pilot.operator_view_backfilled"
ACTION_SHIFT_BUNDLE_EXPORTED = "pilot.shift_bundle_exported"


@dataclass(frozen=True)
class _IncidentDraft:
    audit_log: AuditLog
    source: str
    severity: str
    summary: str
    reasons: list[str]
    provider_label: str | None
    provider_mode: str | None
    capability: str | None
    cutover_mode: str | None
    guardrail_status: str | None


class IncidentRecoveryTaskNotFoundError(LookupError):
    pass


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _normalize_optional_string(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    return normalized or None


def _normalize_reason_list(raw_reasons: object) -> list[str]:
    if not isinstance(raw_reasons, list):
        return []
    normalized: list[str] = []
    for raw_reason in raw_reasons:
        candidate = _normalize_optional_string(raw_reason)
        if candidate is not None and candidate not in normalized:
            normalized.append(candidate)
    return normalized


def _dedupe_reasons(*reasons: str | None, extra: list[str] | None = None) -> list[str]:
    ordered: list[str] = []
    for candidate in reasons:
        if candidate is not None and candidate not in ordered:
            ordered.append(candidate)
    for candidate in extra or []:
        if candidate not in ordered:
            ordered.append(candidate)
    return ordered


def _build_provider_telemetry_draft(audit_log: AuditLog) -> _IncidentDraft | None:
    metadata = audit_log.metadata_json
    error_code = _normalize_optional_string(metadata.get("error_code"))
    guardrail_status = _normalize_optional_string(metadata.get("guardrail_status"))
    guardrail_reason = _normalize_optional_string(metadata.get("guardrail_reason"))
    degraded_reasons = _normalize_reason_list(metadata.get("guardrail_degraded_reasons"))
    low_confidence = bool(metadata.get("low_confidence"))
    used_fallback = bool(metadata.get("used_fallback"))
    shadow_forced_confirmation = bool(metadata.get("shadow_forced_confirmation"))
    guardrail_degraded = bool(metadata.get("guardrail_degraded"))
    outcome = (_normalize_optional_string(metadata.get("outcome")) or "").lower()

    has_incident_signal = any(
        (
            error_code is not None,
            guardrail_status == "blocked",
            shadow_forced_confirmation,
            guardrail_degraded,
            low_confidence,
            used_fallback,
            outcome not in NON_INCIDENT_OUTCOMES and outcome != "",
        )
    )
    if not has_incident_signal:
        return None

    reasons = _dedupe_reasons(
        guardrail_reason,
        error_code if guardrail_status != "blocked" else None,
        "fallback_used" if used_fallback else None,
        "low_confidence" if low_confidence else None,
        extra=degraded_reasons,
    )
    if not reasons and outcome and outcome not in NON_INCIDENT_OUTCOMES:
        reasons = [outcome]

    severity = SEVERITY_DEGRADED
    if guardrail_status == "blocked" or error_code is not None or outcome == "failed":
        severity = SEVERITY_CRITICAL

    task_type = _normalize_optional_string(metadata.get("task_type")) or "unknown-task"
    provider_label = _normalize_optional_string(metadata.get("provider_label"))
    summary = f"Incident detected for {task_type}"
    if provider_label is not None and error_code is not None:
        summary = f"{provider_label} reported {error_code} for {task_type}"
    elif guardrail_reason is not None:
        summary = f"Guardrail forced {task_type} because {guardrail_reason}"
    elif used_fallback:
        summary = f"{task_type} used provider fallback"
    elif low_confidence:
        summary = f"{task_type} hit low confidence"

    return _IncidentDraft(
        audit_log=audit_log,
        source=SOURCE_PROVIDER_TELEMETRY,
        severity=severity,
        summary=summary,
        reasons=reasons,
        provider_label=provider_label,
        provider_mode=_normalize_optional_string(metadata.get("provider_mode")),
        capability=_normalize_optional_string(metadata.get("capability")),
        cutover_mode=_normalize_optional_string(metadata.get("cutover_mode")),
        guardrail_status=guardrail_status,
    )


def _build_cutover_transition_draft(audit_log: AuditLog) -> _IncidentDraft:
    metadata = audit_log.metadata_json
    previous_cutover_mode = _normalize_optional_string(metadata.get("previous_cutover_mode")) or "unknown"
    new_cutover_mode = _normalize_optional_string(metadata.get("new_cutover_mode")) or "unknown"
    severity = SEVERITY_CRITICAL if new_cutover_mode == "closed" else SEVERITY_DEGRADED
    return _IncidentDraft(
        audit_log=audit_log,
        source=SOURCE_CUTOVER_TRANSITION,
        severity=severity,
        summary=f"Cutover changed from {previous_cutover_mode} to {new_cutover_mode}",
        reasons=[f"cutover_mode_{new_cutover_mode}"],
        provider_label=None,
        provider_mode=None,
        capability=None,
        cutover_mode=new_cutover_mode,
        guardrail_status=None,
    )


def _build_incident_draft(
    audit_log: AuditLog,
    *,
    trial_provider_profile: str,
) -> _IncidentDraft | None:
    metadata = audit_log.metadata_json
    log_profile = _normalize_optional_string(metadata.get("trial_provider_profile")) or ""
    if log_profile != trial_provider_profile:
        return None
    if audit_log.action == "runtime.provider_telemetry":
        return _build_provider_telemetry_draft(audit_log)
    if audit_log.action == "pilot.cutover_transition":
        return _build_cutover_transition_draft(audit_log)
    return None


def _load_task_map(db_session: Session, *, shop_id: str, task_run_ids: set[str]) -> dict[str, TaskRun]:
    if not task_run_ids:
        return {}
    rows = db_session.scalars(
        select(TaskRun)
        .join(SessionRecord, SessionRecord.session_id == TaskRun.session_id)
        .where(
            TaskRun.task_run_id.in_(sorted(task_run_ids)),
            SessionRecord.shop_id == shop_id,
        )
    ).all()
    return {row.task_run_id: row for row in rows}


def _load_confirmation_map(
    db_session: Session,
    *,
    task_run_ids: set[str],
) -> dict[str, Confirmation]:
    if not task_run_ids:
        return {}
    rows = db_session.scalars(
        select(Confirmation).where(Confirmation.task_run_id.in_(sorted(task_run_ids)))
    ).all()
    return {row.task_run_id: row for row in rows}


def _load_session_events_map(
    db_session: Session,
    *,
    task_run_ids: set[str],
) -> dict[str, list[SessionStreamEvent]]:
    if not task_run_ids:
        return {}
    rows = db_session.scalars(
        select(SessionStreamEvent)
        .where(SessionStreamEvent.task_run_id.in_(sorted(task_run_ids)))
        .order_by(SessionStreamEvent.occurred_at.asc(), SessionStreamEvent.seq.asc())
    ).all()
    grouped: dict[str, list[SessionStreamEvent]] = defaultdict(list)
    for row in rows:
        if row.task_run_id is not None:
            grouped[row.task_run_id].append(row)
    return dict(grouped)


def _build_incident_entry(
    draft: _IncidentDraft,
    *,
    task_map: dict[str, TaskRun],
    confirmation_map: dict[str, Confirmation],
    session_events_map: dict[str, list[SessionStreamEvent]],
) -> IncidentTimelineEntryData:
    task_data = None
    confirmation_data = None
    session_events: list[IncidentTimelineSessionEventData] = []

    if isinstance(draft.audit_log.task_run_id, str):
        task_run = task_map.get(draft.audit_log.task_run_id)
        if task_run is not None:
            task_data = IncidentTimelineTaskData(
                task_run_id=task_run.task_run_id,
                session_id=task_run.session_id,
                task_type=task_run.task_type,
                status=task_run.status,
                error_code=task_run.error_code,
                created_at=task_run.created_at,
                completed_at=task_run.completed_at,
            )
        confirmation = confirmation_map.get(draft.audit_log.task_run_id)
        if confirmation is not None:
            confirmation_data = IncidentTimelineConfirmationData(
                confirmation_id=confirmation.confirmation_id,
                confirmation_type=confirmation.confirmation_type,
                status=confirmation.status,
                created_at=confirmation.created_at,
                resolved_at=confirmation.resolved_at,
            )
        session_events = [
            IncidentTimelineSessionEventData(
                event_id=event.event_id,
                seq=event.seq,
                event_type=event.event_type,
                occurred_at=event.occurred_at,
            )
            for event in session_events_map.get(draft.audit_log.task_run_id, [])
        ]

    return IncidentTimelineEntryData(
        incident_id=draft.audit_log.audit_log_id,
        source=draft.source,
        action=draft.audit_log.action,
        severity=draft.severity,
        occurred_at=draft.audit_log.created_at,
        summary=draft.summary,
        reasons=draft.reasons,
        provider_label=draft.provider_label,
        provider_mode=draft.provider_mode,
        capability=draft.capability,
        cutover_mode=draft.cutover_mode,
        guardrail_status=draft.guardrail_status,
        task=task_data,
        confirmation=confirmation_data,
        session_events=session_events,
    )


def _find_existing_idempotent_audit_log(
    db_session: Session,
    *,
    shop_id: str,
    action: str,
    idempotency_key: str | None,
    target_id: str | None = None,
) -> AuditLog | None:
    normalized_key = _normalize_optional_string(idempotency_key)
    if normalized_key is None:
        return None
    rows = db_session.scalars(
        select(AuditLog)
        .where(
            AuditLog.shop_id == shop_id,
            AuditLog.scope == "pilot",
            AuditLog.action == action,
        )
        .order_by(AuditLog.created_at.desc(), AuditLog.audit_log_id.desc())
    ).all()
    for row in rows:
        if _normalize_optional_string(row.metadata_json.get("idempotency_key")) != normalized_key:
            continue
        if target_id is not None and _normalize_optional_string(row.target_id) != target_id:
            continue
        return row
    return None


def _load_task_for_shop(
    db_session: Session,
    *,
    shop_id: str,
    task_run_id: str,
) -> TaskRun:
    task_run = db_session.scalar(
        select(TaskRun)
        .join(SessionRecord, SessionRecord.session_id == TaskRun.session_id)
        .where(
            TaskRun.task_run_id == task_run_id,
            SessionRecord.shop_id == shop_id,
        )
    )
    if task_run is None:
        raise IncidentRecoveryTaskNotFoundError(task_run_id)
    return task_run


def _build_timeline_core(
    db_session: Session,
    *,
    shop_id: str,
    started_at: datetime,
    ended_at: datetime,
    trial_provider_profile: str,
) -> tuple[list[_IncidentDraft], dict[str, int], dict[str, int], dict[str, int], dict[str, int], set[str]]:
    audit_logs = db_session.scalars(
        select(AuditLog)
        .where(
            AuditLog.shop_id == shop_id,
            AuditLog.scope == "pilot",
            AuditLog.created_at >= started_at,
            AuditLog.created_at <= ended_at,
            AuditLog.action.in_(("runtime.provider_telemetry", "pilot.cutover_transition")),
        )
        .order_by(AuditLog.created_at.desc(), AuditLog.audit_log_id.desc())
    ).all()

    drafts: list[_IncidentDraft] = []
    affected_task_ids: set[str] = set()
    incidents_by_severity: dict[str, int] = defaultdict(int)
    incidents_by_source: dict[str, int] = defaultdict(int)
    provider_failures: dict[str, int] = defaultdict(int)
    guardrail_reasons: dict[str, int] = defaultdict(int)

    for audit_log in audit_logs:
        draft = _build_incident_draft(
            audit_log,
            trial_provider_profile=trial_provider_profile,
        )
        if draft is None:
            continue
        drafts.append(draft)
        incidents_by_severity[draft.severity] += 1
        incidents_by_source[draft.source] += 1
        if isinstance(audit_log.task_run_id, str) and audit_log.task_run_id:
            affected_task_ids.add(audit_log.task_run_id)
        if draft.source == SOURCE_PROVIDER_TELEMETRY:
            metadata = audit_log.metadata_json
            error_code = _normalize_optional_string(metadata.get("error_code"))
            guardrail_status = _normalize_optional_string(metadata.get("guardrail_status"))
            guardrail_reason = _normalize_optional_string(metadata.get("guardrail_reason"))
            if error_code is not None and guardrail_status != "blocked":
                provider_failures[error_code] += 1
            if guardrail_reason is not None:
                guardrail_reasons[guardrail_reason] += 1
            for degraded_reason in _normalize_reason_list(metadata.get("guardrail_degraded_reasons")):
                guardrail_reasons[degraded_reason] += 1

    return (
        drafts,
        dict(incidents_by_severity),
        dict(incidents_by_source),
        dict(provider_failures),
        dict(guardrail_reasons),
        affected_task_ids,
    )


def build_incident_timeline(
    db_session: Session,
    *,
    shop_id: str,
    hours: int,
    limit: int,
    trial_provider_profile: str,
) -> IncidentTimelineData:
    ended_at = _now()
    started_at = ended_at - timedelta(hours=hours)
    pilot_control, _ = get_or_create_pilot_control(
        db_session,
        shop_id=shop_id,
        trial_provider_profile=trial_provider_profile,
    )

    (
        drafts,
        incidents_by_severity,
        incidents_by_source,
        provider_failures,
        guardrail_reasons,
        affected_task_ids,
    ) = _build_timeline_core(
        db_session,
        shop_id=shop_id,
        started_at=started_at,
        ended_at=ended_at,
        trial_provider_profile=trial_provider_profile,
    )

    task_map = _load_task_map(db_session, shop_id=shop_id, task_run_ids=affected_task_ids)
    confirmation_map = _load_confirmation_map(db_session, task_run_ids=affected_task_ids)
    session_events_map = _load_session_events_map(db_session, task_run_ids=affected_task_ids)

    safe_limit = max(1, min(limit, 100))
    incidents = [
        _build_incident_entry(
            draft,
            task_map=task_map,
            confirmation_map=confirmation_map,
            session_events_map=session_events_map,
        )
        for draft in drafts[:safe_limit]
    ]

    latest_incident_at = drafts[0].audit_log.created_at if drafts else None
    return IncidentTimelineData(
        time_window=PilotSummaryTimeWindowData(
            hours=hours,
            started_at=started_at.isoformat(),
            ended_at=ended_at.isoformat(),
        ),
        trial_provider_profile=trial_provider_profile,
        current_cutover_mode=pilot_control.cutover_mode,
        summary=IncidentTimelineSummaryData(
            total_incidents=len(drafts),
            incidents_by_severity=incidents_by_severity,
            incidents_by_source=incidents_by_source,
            provider_failures=provider_failures,
            guardrail_reasons=guardrail_reasons,
            affected_task_ids=sorted(affected_task_ids),
            latest_incident_at=latest_incident_at,
        ),
        incidents=incidents,
    )


def build_task_diagnostic_replay(
    db_session: Session,
    *,
    shop_id: str,
    actor_id: str,
    task_run_id: str,
    idempotency_key: str | None,
    trial_provider_profile: str,
) -> IncidentTaskDiagnosticReplayData:
    task_run = _load_task_for_shop(
        db_session,
        shop_id=shop_id,
        task_run_id=task_run_id,
    )
    existing = _find_existing_idempotent_audit_log(
        db_session,
        shop_id=shop_id,
        action=ACTION_TASK_DIAGNOSTIC_REPLAYED,
        idempotency_key=idempotency_key,
        target_id=task_run_id,
    )

    drafts: list[_IncidentDraft] = []
    task_audits = db_session.scalars(
        select(AuditLog)
        .where(
            AuditLog.shop_id == shop_id,
            AuditLog.scope == "pilot",
            AuditLog.task_run_id == task_run_id,
            AuditLog.action == "runtime.provider_telemetry",
        )
        .order_by(AuditLog.created_at.desc(), AuditLog.audit_log_id.desc())
    ).all()
    for audit_log in task_audits:
        draft = _build_incident_draft(
            audit_log,
            trial_provider_profile=trial_provider_profile,
        )
        if draft is not None:
            drafts.append(draft)

    task_map = {task_run.task_run_id: task_run}
    confirmation_map = _load_confirmation_map(db_session, task_run_ids={task_run.task_run_id})
    session_events_map = _load_session_events_map(db_session, task_run_ids={task_run.task_run_id})
    incident = (
        _build_incident_entry(
            drafts[0],
            task_map=task_map,
            confirmation_map=confirmation_map,
            session_events_map=session_events_map,
        )
        if drafts
        else None
    )

    if existing is not None:
        return IncidentTaskDiagnosticReplayData(
            replay_audit_log_id=existing.audit_log_id,
            task_run_id=task_run_id,
            idempotency_key=_normalize_optional_string(idempotency_key),
            reused_existing=True,
            incident=incident,
        )

    replay_log = append_pilot_task_diagnostic_replayed_audit_log(
        db_session,
        shop_id=shop_id,
        actor_id=actor_id,
        task_run_id=task_run_id,
        idempotency_key=_normalize_optional_string(idempotency_key),
        trial_provider_profile=trial_provider_profile,
        incident_id=incident.incident_id if incident is not None else None,
        reasons=[] if incident is None else list(incident.reasons),
    )
    return IncidentTaskDiagnosticReplayData(
        replay_audit_log_id=replay_log.audit_log_id,
        task_run_id=task_run_id,
        idempotency_key=_normalize_optional_string(idempotency_key),
        reused_existing=False,
        incident=incident,
    )


def build_operator_view_backfill(
    db_session: Session,
    *,
    shop_id: str,
    actor_id: str,
    view: str,
    hours: int,
    limit: int,
    idempotency_key: str | None,
    trial_provider_profile: str,
) -> OperatorViewBackfillData:
    existing = _find_existing_idempotent_audit_log(
        db_session,
        shop_id=shop_id,
        action=ACTION_OPERATOR_VIEW_BACKFILLED,
        idempotency_key=idempotency_key,
        target_id=view,
    )
    timeline = build_incident_timeline(
        db_session,
        shop_id=shop_id,
        hours=hours,
        limit=limit,
        trial_provider_profile=trial_provider_profile,
    )
    snapshot = OperatorViewBackfillSnapshotData(
        total_incidents=timeline.summary.total_incidents,
        current_cutover_mode=timeline.current_cutover_mode,
        affected_task_ids=list(timeline.summary.affected_task_ids),
    )
    if existing is not None:
        return OperatorViewBackfillData(
            backfill_audit_log_id=existing.audit_log_id,
            view=view,
            idempotency_key=_normalize_optional_string(idempotency_key),
            reused_existing=True,
            snapshot=snapshot,
        )

    backfill_log = append_pilot_operator_view_backfill_audit_log(
        db_session,
        shop_id=shop_id,
        actor_id=actor_id,
        view=view,
        hours=hours,
        limit=limit,
        idempotency_key=_normalize_optional_string(idempotency_key),
        trial_provider_profile=trial_provider_profile,
        total_incidents=snapshot.total_incidents,
        current_cutover_mode=snapshot.current_cutover_mode,
        affected_task_ids=list(snapshot.affected_task_ids),
    )
    return OperatorViewBackfillData(
        backfill_audit_log_id=backfill_log.audit_log_id,
        view=view,
        idempotency_key=_normalize_optional_string(idempotency_key),
        reused_existing=False,
        snapshot=snapshot,
    )


def _load_latest_shift_bundle(
    db_session: Session,
    *,
    shop_id: str,
    trial_provider_profile: str,
) -> OperatorDiagnosticsLatestShiftBundleData | None:
    audit_logs = db_session.scalars(
        select(AuditLog)
        .where(
            AuditLog.shop_id == shop_id,
            AuditLog.scope == "pilot",
            AuditLog.action == ACTION_SHIFT_BUNDLE_EXPORTED,
        )
        .order_by(AuditLog.created_at.desc(), AuditLog.audit_log_id.desc())
    ).all()
    for audit_log in audit_logs:
        metadata = audit_log.metadata_json
        if (_normalize_optional_string(metadata.get("trial_provider_profile")) or "") != trial_provider_profile:
            continue
        bundle_id = _normalize_optional_string(metadata.get("bundle_id"))
        manifest_path = _normalize_optional_string(metadata.get("manifest_path"))
        overall_status = _normalize_optional_string(metadata.get("overall_status"))
        if bundle_id is None or manifest_path is None or overall_status is None:
            continue
        return OperatorDiagnosticsLatestShiftBundleData(
            audit_log_id=audit_log.audit_log_id,
            bundle_id=bundle_id,
            manifest_path=manifest_path,
            overall_status=overall_status,
            degraded_reasons=_normalize_reason_list(metadata.get("degraded_reasons")),
        )
    return None


def build_operator_diagnostics(
    db_session: Session,
    *,
    shop_id: str,
    hours: int,
    limit: int,
    trial_provider_profile: str,
) -> OperatorDiagnosticsData:
    timeline = build_incident_timeline(
        db_session,
        shop_id=shop_id,
        hours=hours,
        limit=limit,
        trial_provider_profile=trial_provider_profile,
    )

    recent_reasons: dict[str, int] = dict(timeline.summary.guardrail_reasons)
    for error_code, count in timeline.summary.provider_failures.items():
        recent_reasons[error_code] = recent_reasons.get(error_code, 0) + count

    affected_tasks: list[OperatorDiagnosticsAffectedTaskData] = []
    seen_task_ids: set[str] = set()
    for incident in timeline.incidents:
        if incident.task is None or incident.task.task_run_id in seen_task_ids:
            continue
        seen_task_ids.add(incident.task.task_run_id)
        affected_tasks.append(
            OperatorDiagnosticsAffectedTaskData(
                task_run_id=incident.task.task_run_id,
                task_type=incident.task.task_type,
                status=incident.task.status,
                severity=incident.severity,
                reasons=list(incident.reasons),
            )
        )

    critical_count = timeline.summary.incidents_by_severity.get(SEVERITY_CRITICAL, 0)
    if timeline.current_cutover_mode == "open" and critical_count > 0:
        operator_verdict = "rollback-recommended"
    elif timeline.summary.total_incidents > 0:
        operator_verdict = "investigate"
    else:
        operator_verdict = "stable"

    latest_shift_bundle = _load_latest_shift_bundle(
        db_session,
        shop_id=shop_id,
        trial_provider_profile=trial_provider_profile,
    )

    suggested_actions: list[str] = []
    if operator_verdict == "rollback-recommended":
        suggested_actions.append("set_cutover_closed")
        suggested_actions.append("run_task_diagnostic_replay")
        suggested_actions.append(
            "review_latest_shift_bundle" if latest_shift_bundle is not None else "export_shift_bundle"
        )
    elif operator_verdict == "investigate":
        suggested_actions.append("review_incident_timeline")
        suggested_actions.append("run_operator_view_backfill")
        suggested_actions.append(
            "review_latest_shift_bundle" if latest_shift_bundle is not None else "export_shift_bundle"
        )
    else:
        suggested_actions.append("continue_observation")

    return OperatorDiagnosticsData(
        time_window=timeline.time_window,
        trial_provider_profile=timeline.trial_provider_profile,
        current_cutover_mode=timeline.current_cutover_mode,
        operator_verdict=operator_verdict,
        incident_summary=timeline.summary,
        recent_reasons=recent_reasons,
        affected_tasks=affected_tasks,
        latest_shift_bundle=latest_shift_bundle,
        suggested_actions=suggested_actions,
    )


def record_shift_bundle_export(
    db_session: Session,
    *,
    shop_id: str,
    actor_id: str,
    bundle_id: str,
    manifest_path: str,
    overall_status: str,
    degraded_reasons: list[str],
    cutover_mode: str | None,
    hours: int | None,
    trial_provider_profile: str,
) -> ShiftBundleExportRecordData:
    existing_logs = db_session.scalars(
        select(AuditLog)
        .where(
            AuditLog.shop_id == shop_id,
            AuditLog.scope == "pilot",
            AuditLog.action == ACTION_SHIFT_BUNDLE_EXPORTED,
            AuditLog.target_id == bundle_id,
        )
        .order_by(AuditLog.created_at.desc(), AuditLog.audit_log_id.desc())
    ).all()
    for existing in existing_logs:
        if _normalize_optional_string(existing.metadata_json.get("manifest_path")) != manifest_path:
            continue
        return ShiftBundleExportRecordData(
            shift_bundle_audit_log_id=existing.audit_log_id,
            bundle_id=bundle_id,
            reused_existing=True,
        )

    audit_log = append_pilot_shift_bundle_export_audit_log(
        db_session,
        shop_id=shop_id,
        actor_id=actor_id,
        bundle_id=bundle_id,
        manifest_path=manifest_path,
        overall_status=overall_status,
        degraded_reasons=list(degraded_reasons),
        trial_provider_profile=trial_provider_profile,
        cutover_mode=cutover_mode,
        hours=hours,
    )
    return ShiftBundleExportRecordData(
        shift_bundle_audit_log_id=audit_log.audit_log_id,
        bundle_id=bundle_id,
        reused_existing=False,
    )
