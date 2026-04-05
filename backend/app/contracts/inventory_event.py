from decimal import Decimal

from pydantic import BaseModel


class CreateInventoryCorrectionRequest(BaseModel):
    item_id: str
    expected_quantity: Decimal
    corrected_quantity: Decimal
    reason: str


class CreateInventoryCorrectionData(BaseModel):
    correction_event_id: str
    item_id: str
    new_quantity: Decimal


class CreateInventoryStockOutRequest(BaseModel):
    item_id: str
    expected_quantity: Decimal
    stock_out_quantity: Decimal
    reason: str


class CreateInventoryStockOutData(BaseModel):
    stock_out_event_id: str
    item_id: str
    new_quantity: Decimal
