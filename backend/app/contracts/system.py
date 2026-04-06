from datetime import datetime

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
    trial_provider_profile: str


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


class PilotControlMutationRequest(BaseModel):
    cutover_mode: str | None = None
    approved_calibration_artifact_id: str | None = None
    approved_calibration_report_path: str | None = None
    notes: str | None = None
