from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api.deps.v2_context import (
    V2AuthenticatedAccount,
    V2ExecutionContext,
    ensure_v2_permission,
    require_v2_authenticated_account,
    require_v2_execution_context,
)
from app.contracts.v2.common import V2DataEnvelope, V2ErrorBody, V2ErrorEnvelope
from app.contracts.v2.sales import (
    V2CreateSalesOrderRequest,
    V2SalesOrderData,
    V2SalesOrderDetailData,
    V2SalesOrderLineData,
    V2SalesOrderListData,
    V2SalesOrderSummaryData,
)
from app.db.session import get_db_session
from app.models.v2_sales import V2SalesOrder, V2SalesOrderLine
from app.services.v2_sales import (
    V2SalesOrderInsufficientStockError,
    V2SalesOrderItemNotFoundError,
    V2SalesOrderValidationError,
    create_v2_sales_order,
    list_v2_sales_order_lines,
    list_v2_sales_orders,
)
from app.services.v2_commercial import cancel_sales_order, get_sales_order_detail, return_sales_order_items

router = APIRouter(prefix="/api/v2/sales", tags=["v2-sales"])


def _context_account_mismatch() -> JSONResponse:
    return JSONResponse(
        status_code=403,
        content=V2ErrorEnvelope(
            error=V2ErrorBody(code="context_account_mismatch", message="Context account mismatch")
        ).model_dump(),
    )


def _error(status_code: int, *, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=V2ErrorEnvelope(error=V2ErrorBody(code=code, message=message)).model_dump(),
    )


def _to_line_data(line: V2SalesOrderLine) -> V2SalesOrderLineData:
    return V2SalesOrderLineData(
        sales_order_line_id=line.sales_order_line_id,
        sales_order_id=line.sales_order_id,
        inventory_item_id=line.inventory_item_id,
        item_name=line.item_name,
        quantity=line.quantity,
        unit=line.unit,
        unit_price=line.unit_price,
        line_amount=line.line_amount,
    )


def _to_order_data(order: V2SalesOrder, lines: list[V2SalesOrderLine]) -> V2SalesOrderData:
    return V2SalesOrderData(
        sales_order_id=order.sales_order_id,
        tenant_id=order.tenant_id,
        shop_id=order.shop_id,
        order_no=order.order_no,
        status=order.status,
        customer_id=order.customer_id,
        customer_name=order.customer_name,
        payment_method=order.payment_method,
        total_amount=order.total_amount,
        note=order.note,
        items=[_to_line_data(line) for line in lines],
        created_by_account_id=order.created_by_account_id,
        created_at=order.created_at,
        updated_at=order.updated_at,
    )


@router.post("/orders", response_model=V2DataEnvelope[V2SalesOrderDetailData])
def create_sales_order_v2(
    payload: V2CreateSalesOrderRequest,
    account: V2AuthenticatedAccount = Depends(require_v2_authenticated_account),
    context: V2ExecutionContext = Depends(require_v2_execution_context),
    db_session: Session = Depends(get_db_session),
) -> V2DataEnvelope[V2SalesOrderDetailData] | JSONResponse:
    if account.account_id != context.account_id:
        return _context_account_mismatch()
    ensure_v2_permission(context, "sales:write")
    try:
        result = create_v2_sales_order(
            db_session,
            tenant_id=context.tenant_id,
            shop_id=context.shop_id,
            customer_id=payload.customer_id,
            customer_name=payload.customer_name,
            payment_method=payload.payment_method,
            items=payload.items,
            note=payload.note,
            created_by_account_id=account.account_id,
        )
    except V2SalesOrderItemNotFoundError:
        return _error(404, code="inventory_item_not_found", message="Inventory item not found")
    except V2SalesOrderInsufficientStockError:
        return _error(409, code="insufficient_stock", message="Insufficient stock for sales order")
    except V2SalesOrderValidationError as exc:
        return _error(422, code="validation_error", message=str(exc))
    return V2DataEnvelope(data=V2SalesOrderDetailData(order=_to_order_data(result.order, result.lines)))


@router.get("/orders/{sales_order_id}", response_model=V2DataEnvelope[V2SalesOrderDetailData])
def get_sales_order_v2(
    sales_order_id: str,
    account: V2AuthenticatedAccount = Depends(require_v2_authenticated_account),
    context: V2ExecutionContext = Depends(require_v2_execution_context),
    db_session: Session = Depends(get_db_session),
) -> V2DataEnvelope[V2SalesOrderDetailData] | JSONResponse:
    if account.account_id != context.account_id:
        return _context_account_mismatch()
    try:
        order, lines = get_sales_order_detail(db_session, tenant_id=context.tenant_id, shop_id=context.shop_id, sales_order_id=sales_order_id)
    except LookupError:
        return _error(404, code="sales_order_not_found", message="Sales order not found")
    return V2DataEnvelope(data=V2SalesOrderDetailData(order=_to_order_data(order, lines)))


@router.post("/orders/{sales_order_id}/cancel", response_model=V2DataEnvelope[V2SalesOrderDetailData])
def cancel_sales_order_v2(
    sales_order_id: str,
    payload: dict,
    account: V2AuthenticatedAccount = Depends(require_v2_authenticated_account),
    context: V2ExecutionContext = Depends(require_v2_execution_context),
    db_session: Session = Depends(get_db_session),
) -> V2DataEnvelope[V2SalesOrderDetailData] | JSONResponse:
    if account.account_id != context.account_id:
        return _context_account_mismatch()
    ensure_v2_permission(context, "sales:write")
    try:
        order, lines = cancel_sales_order(db_session, tenant_id=context.tenant_id, shop_id=context.shop_id, sales_order_id=sales_order_id, reason=str(payload.get("reason") or ""), account_id=account.account_id)
    except LookupError:
        return _error(404, code="sales_order_not_found", message="Sales order not found")
    except ValueError as exc:
        return _error(409, code="sales_order_state_conflict", message=str(exc))
    return V2DataEnvelope(data=V2SalesOrderDetailData(order=_to_order_data(order, lines)))


@router.post("/orders/{sales_order_id}/returns", response_model=V2DataEnvelope[V2SalesOrderDetailData])
def return_sales_order_v2(
    sales_order_id: str,
    payload: dict,
    account: V2AuthenticatedAccount = Depends(require_v2_authenticated_account),
    context: V2ExecutionContext = Depends(require_v2_execution_context),
    db_session: Session = Depends(get_db_session),
) -> V2DataEnvelope[V2SalesOrderDetailData] | JSONResponse:
    if account.account_id != context.account_id:
        return _context_account_mismatch()
    ensure_v2_permission(context, "sales:write")
    try:
        order, lines = return_sales_order_items(db_session, tenant_id=context.tenant_id, shop_id=context.shop_id, sales_order_id=sales_order_id, items=list(payload.get("items") or []), reason=str(payload.get("reason") or ""), account_id=account.account_id)
    except LookupError:
        return _error(404, code="sales_order_not_found", message="Sales order not found")
    except ValueError as exc:
        return _error(422, code="validation_error", message=str(exc))
    return V2DataEnvelope(data=V2SalesOrderDetailData(order=_to_order_data(order, lines)))


@router.get("/orders", response_model=V2DataEnvelope[V2SalesOrderListData])
def list_sales_orders_v2(
    account: V2AuthenticatedAccount = Depends(require_v2_authenticated_account),
    context: V2ExecutionContext = Depends(require_v2_execution_context),
    limit: int = Query(default=20, ge=1, le=50),
    db_session: Session = Depends(get_db_session),
) -> V2DataEnvelope[V2SalesOrderListData] | JSONResponse:
    if account.account_id != context.account_id:
        return _context_account_mismatch()
    rows = list_v2_sales_orders(db_session, tenant_id=context.tenant_id, shop_id=context.shop_id, limit=limit)
    orders: list[V2SalesOrderSummaryData] = []
    for order, items_count in rows:
        orders.append(
            V2SalesOrderSummaryData(
                sales_order_id=order.sales_order_id,
                tenant_id=order.tenant_id,
                shop_id=order.shop_id,
                order_no=order.order_no,
                status=order.status,
                customer_id=order.customer_id,
                customer_name=order.customer_name,
                payment_method=order.payment_method,
                total_amount=order.total_amount,
                items_count=items_count,
                created_at=order.created_at,
            )
        )
    return V2DataEnvelope(data=V2SalesOrderListData(orders=orders, count=len(orders)))
