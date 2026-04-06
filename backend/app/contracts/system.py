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
    low_confidence_count: int
    fallback_count: int
    provider_failures: dict[str, int]
    trial_provider_profile: str
