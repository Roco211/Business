from decimal import Decimal

from pydantic import BaseModel


class CreateInventoryCorrectionRequest(BaseModel):
    item_id: str
    corrected_quantity: Decimal
    reason: str


class CreateInventoryCorrectionData(BaseModel):
    correction_event_id: str
    item_id: str
    new_quantity: Decimal
