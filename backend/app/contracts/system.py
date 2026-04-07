from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str


class ReadinessCheckData(BaseModel):
    status: str
    mode: str
    message: str
    details: dict[str, str]


class SystemReadinessData(BaseModel):
    overall_status: str
    runtime_mode: str
    trial_provider_profile: str
    approved_calibration_artifact_id: str | None = None
    cutover_mode: str = "closed"
    checks: dict[str, ReadinessCheckData]


class DemoBootstrapSummaryData(BaseModel):
    shop_id: str
    session_id: str
    inventory_item_count: int
    inventory_item_names: list[str]
    pending_confirmation_count: int
    pending_confirmation_types: list[str]
    open_low_stock_alert_count: int
    open_low_stock_item_names: list[str]
    message_count: int
    task_run_count: int


class PilotSummaryTimeWindowData(BaseModel):
    hours: int
    started_at: str
    ended_at: str


class PilotSummaryConfirmationData(BaseModel):
    created: int
    approved: int
    rejected: int


class PilotSummaryData(BaseModel):
    time_window: PilotSummaryTimeWindowData
    task_totals: dict[str, dict[str, int]]
    confirmations: PilotSummaryConfirmationData
    telemetry_task_count: int
    low_confidence_count: int
    fallback_count: int
    provider_failures: dict[str, int]
    cutover_mode_counts: dict[str, int]
    guardrail_blocks: dict[str, int]
    shadow_forced_confirmation_count: int
    guardrail_degraded_reasons: dict[str, int]
    trial_provider_profile: str


class IncidentTimelineSessionEventData(BaseModel):
    event_id: str
    seq: int
    event_type: str
    occurred_at: datetime


class IncidentTimelineTaskData(BaseModel):
    task_run_id: str
    session_id: str
    task_type: str
    status: str
    error_code: str | None
    created_at: datetime
    completed_at: datetime | None


class IncidentTimelineConfirmationData(BaseModel):
    confirmation_id: str
    confirmation_type: str
    status: str
    created_at: datetime
    resolved_at: datetime | None


class IncidentTimelineEntryData(BaseModel):
    incident_id: str
    source: str
    action: str
    severity: str
    occurred_at: datetime
    summary: str
    reasons: list[str]
    provider_label: str | None = None
    provider_mode: str | None = None
    capability: str | None = None
    cutover_mode: str | None = None
    guardrail_status: str | None = None
    task: IncidentTimelineTaskData | None = None
    confirmation: IncidentTimelineConfirmationData | None = None
    session_events: list[IncidentTimelineSessionEventData]


class IncidentTimelineSummaryData(BaseModel):
    total_incidents: int
    incidents_by_severity: dict[str, int]
    incidents_by_source: dict[str, int]
    provider_failures: dict[str, int]
    guardrail_reasons: dict[str, int]
    affected_task_ids: list[str]
    latest_incident_at: datetime | None = None


class IncidentTimelineData(BaseModel):
    time_window: PilotSummaryTimeWindowData
    trial_provider_profile: str
    current_cutover_mode: str
    summary: IncidentTimelineSummaryData
    incidents: list[IncidentTimelineEntryData]


class IncidentTaskDiagnosticReplayRequest(BaseModel):
    task_run_id: str
    idempotency_key: str | None = None


class IncidentTaskDiagnosticReplayData(BaseModel):
    replay_audit_log_id: str
    task_run_id: str
    idempotency_key: str | None = None
    reused_existing: bool
    incident: IncidentTimelineEntryData | None = None


class OperatorViewBackfillRequest(BaseModel):
    view: Literal["incident-timeline", "operator-diagnostics"] = "incident-timeline"
    hours: int = 24
    limit: int = 20
    idempotency_key: str | None = None


class OperatorViewBackfillSnapshotData(BaseModel):
    total_incidents: int
    current_cutover_mode: str
    affected_task_ids: list[str]


class OperatorViewBackfillData(BaseModel):
    backfill_audit_log_id: str
    view: str
    idempotency_key: str | None = None
    reused_existing: bool
    snapshot: OperatorViewBackfillSnapshotData


class OperatorDiagnosticsAffectedTaskData(BaseModel):
    task_run_id: str
    task_type: str
    status: str
    severity: str
    reasons: list[str]


class OperatorDiagnosticsLatestShiftBundleData(BaseModel):
    audit_log_id: str
    bundle_id: str
    manifest_path: str
    overall_status: str
    degraded_reasons: list[str]


class OperatorDiagnosticsData(BaseModel):
    time_window: PilotSummaryTimeWindowData
    trial_provider_profile: str
    current_cutover_mode: str
    operator_verdict: str
    incident_summary: IncidentTimelineSummaryData
    recent_reasons: dict[str, int]
    affected_tasks: list[OperatorDiagnosticsAffectedTaskData]
    latest_shift_bundle: OperatorDiagnosticsLatestShiftBundleData | None = None
    suggested_actions: list[str]


class ShiftBundleExportRecordRequest(BaseModel):
    bundle_id: str
    manifest_path: str
    overall_status: str
    degraded_reasons: list[str]
    cutover_mode: str | None = None
    hours: int | None = None


class ShiftBundleExportRecordData(BaseModel):
    shift_bundle_audit_log_id: str
    bundle_id: str
    reused_existing: bool


class PilotControlData(BaseModel):
    shop_id: str
    trial_provider_profile: str
    approved_calibration_artifact_id: str | None
    approved_calibration_report_path: str | None
    cutover_mode: str
    opened_at: datetime | None
    opened_by_actor_id: str | None
    closed_at: datetime | None
    closed_by_actor_id: str | None
    last_preflight_at: datetime | None
    last_preflight_status: str | None
    notes: str | None
    previous_cutover_mode: str | None = None
    transition_audit_log_id: str | None = None


class PilotControlMutationRequest(BaseModel):
    cutover_mode: str | None = None
    approved_calibration_artifact_id: str | None = None
    approved_calibration_report_path: str | None = None
    last_preflight_status: str | None = None
    notes: str | None = None
