from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class V2InventoryItemData(BaseModel):
    inventory_item_id: str
    tenant_id: str
    sku: str | None
    name: str
    barcode: str | None
    default_unit: str
    status: str
    created_at: datetime
    updated_at: datetime


class V2InventoryItemListData(BaseModel):
    items: list[V2InventoryItemData]
    count: int


class V2InventoryItemDetailData(BaseModel):
    item: V2InventoryItemData


class V2CreateInventoryItemRequest(BaseModel):
    sku: str | None = None
    name: str
    barcode: str | None = None
    default_unit: str


class V2UpdateInventoryItemRequest(BaseModel):
    sku: str | None = None
    name: str | None = None
    barcode: str | None = None
    default_unit: str | None = None


class V2InventoryStockData(BaseModel):
    snapshot_id: str
    tenant_id: str
    shop_id: str
    inventory_item_id: str
    item_name: str
    default_unit: str
    current_quantity: Decimal
    current_price: Decimal | None
    low_stock_threshold: Decimal | None
    updated_at: datetime


class V2InventoryStockListData(BaseModel):
    items: list[V2InventoryStockData]
    count: int


class V2InventoryLedgerEventData(BaseModel):
    event_id: str
    tenant_id: str
    shop_id: str
    inventory_item_id: str
    item_name: str
    event_type: str
    quantity_delta: Decimal
    quantity_after: Decimal
    unit: str
    price: Decimal | None
    source_type: str
    source_id: str
    reason: str | None
    created_by_account_id: str
    occurred_at: datetime


class V2InventoryLedgerEventListData(BaseModel):
    events: list[V2InventoryLedgerEventData]
    count: int


class V2SubmitInventoryCorrectionRequest(BaseModel):
    inventory_item_id: str
    expected_quantity: Decimal
    corrected_quantity: Decimal
    reason: str


class V2SubmitInventoryCorrectionData(BaseModel):
    correction_event_id: str
    inventory_item_id: str
    new_quantity: Decimal


class V2SubmitInventoryStockInRequest(BaseModel):
    inventory_item_id: str | None = None
    item_name: str | None = None
    stock_in_quantity: Decimal
    unit: str
    price: Decimal
    reason: str | None = None


class V2SubmitInventoryStockInData(BaseModel):
    stock_in_event_id: str
    inventory_item_id: str
    new_quantity: Decimal


class V2SubmitInventoryStockOutRequest(BaseModel):
    inventory_item_id: str
    expected_quantity: Decimal
    stock_out_quantity: Decimal
    reason: str


class V2SubmitInventoryStockOutData(BaseModel):
    stock_out_event_id: str
    inventory_item_id: str
    new_quantity: Decimal
