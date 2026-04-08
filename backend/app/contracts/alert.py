from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class LowStockAlertData(BaseModel):
    alert_id: str
    shop_id: str
    alert_type: str
    item_id: str
    item_name: str
    status: str
    stock: Decimal
    threshold: Decimal
    unit: str
    created_at: datetime


class ListAlertsMeta(BaseModel):
    count: int


class ListLowStockAlertsResponse(BaseModel):
    data: list[LowStockAlertData]
    meta: ListAlertsMeta
