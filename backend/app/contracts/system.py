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
