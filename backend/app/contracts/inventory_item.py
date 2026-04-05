from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class InventoryItemData(BaseModel):
    item_id: str
    shop_id: str
    sku: str | None
    name: str
    category: str | None
    barcode: str | None
    default_unit: str
    current_stock: Decimal
    current_price: Decimal | None
    low_stock_threshold: Decimal | None
    image_media_id: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class ListInventoryItemsMeta(BaseModel):
    count: int


class ListInventoryItemsResponse(BaseModel):
    data: list[InventoryItemData]
    meta: ListInventoryItemsMeta


class RecognizeAndQueryRequest(BaseModel):
    media_id: str


class RecognizedItemData(BaseModel):
    item_id: str | None
    name: str
    confidence: float


class RecognizeAndQueryInventoryData(BaseModel):
    stock: Decimal | None
    unit: str | None
    is_low_stock: bool | None


class RecognizeAndQueryData(BaseModel):
    recognized_item: RecognizedItemData
    inventory: RecognizeAndQueryInventoryData
