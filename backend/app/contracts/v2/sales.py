from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class V2CreateSalesOrderLineRequest(BaseModel):
    inventory_item_id: str
    quantity: Decimal
    unit_price: Decimal


class V2CreateSalesOrderRequest(BaseModel):
    customer_name: str | None = None
    payment_method: str = "unknown"
    items: list[V2CreateSalesOrderLineRequest] = Field(min_length=1)
    note: str | None = None


class V2SalesOrderLineData(BaseModel):
    sales_order_line_id: str
    sales_order_id: str
    inventory_item_id: str
    item_name: str
    quantity: Decimal
    unit: str
    unit_price: Decimal
    line_amount: Decimal


class V2SalesOrderData(BaseModel):
    sales_order_id: str
    tenant_id: str
    shop_id: str
    order_no: str
    status: str
    customer_name: str | None
    payment_method: str
    total_amount: Decimal
    note: str | None
    items: list[V2SalesOrderLineData]
    created_by_account_id: str
    created_at: datetime
    updated_at: datetime


class V2SalesOrderSummaryData(BaseModel):
    sales_order_id: str
    tenant_id: str
    shop_id: str
    order_no: str
    status: str
    customer_name: str | None
    payment_method: str
    total_amount: Decimal
    items_count: int
    created_at: datetime


class V2SalesOrderDetailData(BaseModel):
    order: V2SalesOrderData


class V2SalesOrderListData(BaseModel):
    orders: list[V2SalesOrderSummaryData]
    count: int
