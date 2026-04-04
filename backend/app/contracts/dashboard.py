from datetime import datetime

from pydantic import BaseModel


class DashboardSummaryData(BaseModel):
    shop_id: str
    today_stock_in_count: int
    today_task_completed_count: int
    pending_confirmations_count: int
    open_low_stock_alert_count: int
    last_inventory_event_at: datetime | None
