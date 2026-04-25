from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api.deps.v2_context import V2AuthenticatedAccount, V2ExecutionContext, require_v2_authenticated_account, require_v2_execution_context
from app.contracts.v2.common import V2DataEnvelope, V2ErrorBody, V2ErrorEnvelope
from app.db.session import get_db_session
from app.services.v2_commercial import create_customer, create_purchase_order, create_sales_order_confirmation_from_text, create_supplier, customer_repurchase_analysis, finance_summary, get_finance_transactions, list_customers, list_purchase_orders, list_suppliers


def _err(status: int, code: str, message: str):
    return JSONResponse(status_code=status, content=V2ErrorEnvelope(error=V2ErrorBody(code=code, message=message)).model_dump())


def _guard(account: V2AuthenticatedAccount, context: V2ExecutionContext):
    if account.account_id != context.account_id:
        return _err(403, "context_account_mismatch", "Context account mismatch")
    return None


purchasing_router = APIRouter(prefix="/api/v2/purchasing", tags=["v2-purchasing"])
customers_router = APIRouter(prefix="/api/v2/customers", tags=["v2-customers"])
finance_router = APIRouter(prefix="/api/v2/finance", tags=["v2-finance"])
sales_draft_router = APIRouter(prefix="/api/v2/sales", tags=["v2-sales-ai"])


@purchasing_router.get("/suppliers")
def list_suppliers_v2(account: V2AuthenticatedAccount = Depends(require_v2_authenticated_account), context: V2ExecutionContext = Depends(require_v2_execution_context), limit: int = Query(default=20, ge=1, le=50), db_session: Session = Depends(get_db_session)):
    if mismatch := _guard(account, context): return mismatch
    suppliers = list_suppliers(db_session, tenant_id=context.tenant_id, shop_id=context.shop_id, limit=limit)
    return V2DataEnvelope(data={"suppliers": [{"supplier_id": supplier.supplier_id, "tenant_id": supplier.tenant_id, "shop_id": supplier.shop_id, "name": supplier.name, "phone": supplier.phone, "status": supplier.status, "created_at": supplier.created_at} for supplier in suppliers], "count": len(suppliers)})


@purchasing_router.post("/suppliers")
def create_supplier_v2(payload: dict, account: V2AuthenticatedAccount = Depends(require_v2_authenticated_account), context: V2ExecutionContext = Depends(require_v2_execution_context), db_session: Session = Depends(get_db_session)):
    if mismatch := _guard(account, context): return mismatch
    supplier = create_supplier(db_session, tenant_id=context.tenant_id, shop_id=context.shop_id, name=str(payload.get("name") or ""), phone=payload.get("phone"))
    return V2DataEnvelope(data={"supplier": {"supplier_id": supplier.supplier_id, "tenant_id": supplier.tenant_id, "shop_id": supplier.shop_id, "name": supplier.name, "phone": supplier.phone, "status": supplier.status}})


@purchasing_router.get("/orders")
def list_purchase_orders_v2(account: V2AuthenticatedAccount = Depends(require_v2_authenticated_account), context: V2ExecutionContext = Depends(require_v2_execution_context), limit: int = Query(default=20, ge=1, le=50), db_session: Session = Depends(get_db_session)):
    if mismatch := _guard(account, context): return mismatch
    orders = list_purchase_orders(db_session, tenant_id=context.tenant_id, shop_id=context.shop_id, limit=limit)
    return V2DataEnvelope(data={"purchase_orders": [{"purchase_order_id": order.purchase_order_id, "tenant_id": order.tenant_id, "shop_id": order.shop_id, "supplier_id": order.supplier_id, "order_no": order.order_no, "status": order.status, "total_amount": order.total_amount, "note": order.note, "created_at": order.created_at} for order in orders], "count": len(orders)})


@purchasing_router.post("/orders")
def create_purchase_order_v2(payload: dict, account: V2AuthenticatedAccount = Depends(require_v2_authenticated_account), context: V2ExecutionContext = Depends(require_v2_execution_context), db_session: Session = Depends(get_db_session)):
    if mismatch := _guard(account, context): return mismatch
    try:
        order = create_purchase_order(db_session, tenant_id=context.tenant_id, shop_id=context.shop_id, supplier_id=str(payload.get("supplier_id") or ""), items=list(payload.get("items") or []), note=payload.get("note"), account_id=account.account_id)
    except LookupError:
        return _err(404, "purchase_resource_not_found", "Purchase resource not found")
    return V2DataEnvelope(data={"purchase_order": {"purchase_order_id": order.purchase_order_id, "tenant_id": order.tenant_id, "shop_id": order.shop_id, "supplier_id": order.supplier_id, "order_no": order.order_no, "status": order.status, "total_amount": order.total_amount, "note": order.note, "created_at": order.created_at}})


@customers_router.get("")
def list_customers_v2(account: V2AuthenticatedAccount = Depends(require_v2_authenticated_account), context: V2ExecutionContext = Depends(require_v2_execution_context), limit: int = Query(default=20, ge=1, le=50), db_session: Session = Depends(get_db_session)):
    if mismatch := _guard(account, context): return mismatch
    customers = list_customers(db_session, tenant_id=context.tenant_id, shop_id=context.shop_id, limit=limit)
    return V2DataEnvelope(data={"customers": [{"customer_id": customer.customer_id, "tenant_id": customer.tenant_id, "shop_id": customer.shop_id, "name": customer.name, "phone": customer.phone, "status": customer.status, "created_at": customer.created_at} for customer in customers], "count": len(customers)})


@customers_router.post("")
def create_customer_v2(payload: dict, account: V2AuthenticatedAccount = Depends(require_v2_authenticated_account), context: V2ExecutionContext = Depends(require_v2_execution_context), db_session: Session = Depends(get_db_session)):
    if mismatch := _guard(account, context): return mismatch
    customer = create_customer(db_session, tenant_id=context.tenant_id, shop_id=context.shop_id, name=str(payload.get("name") or ""), phone=payload.get("phone"))
    return V2DataEnvelope(data={"customer": {"customer_id": customer.customer_id, "tenant_id": customer.tenant_id, "shop_id": customer.shop_id, "name": customer.name, "phone": customer.phone, "status": customer.status}})


@customers_router.get("/repurchase-analysis")
def customer_repurchase_analysis_v2(account: V2AuthenticatedAccount = Depends(require_v2_authenticated_account), context: V2ExecutionContext = Depends(require_v2_execution_context), db_session: Session = Depends(get_db_session)):
    if mismatch := _guard(account, context): return mismatch
    return V2DataEnvelope(data=customer_repurchase_analysis(db_session, tenant_id=context.tenant_id, shop_id=context.shop_id))


@finance_router.get("/transactions")
def list_finance_transactions_v2(account: V2AuthenticatedAccount = Depends(require_v2_authenticated_account), context: V2ExecutionContext = Depends(require_v2_execution_context), limit: int = Query(default=20, ge=1, le=50), db_session: Session = Depends(get_db_session)):
    if mismatch := _guard(account, context): return mismatch
    transactions = get_finance_transactions(db_session, tenant_id=context.tenant_id, shop_id=context.shop_id, limit=limit)
    return V2DataEnvelope(data={"transactions": [{"finance_transaction_id": tx.finance_transaction_id, "tenant_id": tx.tenant_id, "shop_id": tx.shop_id, "transaction_type": tx.transaction_type, "direction": tx.direction, "amount": tx.amount, "source_type": tx.source_type, "source_id": tx.source_id, "counterparty_name": tx.counterparty_name, "note": tx.note, "occurred_at": tx.occurred_at} for tx in transactions], "count": len(transactions)})


@finance_router.get("/summary")
def finance_summary_v2(account: V2AuthenticatedAccount = Depends(require_v2_authenticated_account), context: V2ExecutionContext = Depends(require_v2_execution_context), db_session: Session = Depends(get_db_session)):
    if mismatch := _guard(account, context): return mismatch
    return V2DataEnvelope(data={"summary": finance_summary(db_session, tenant_id=context.tenant_id, shop_id=context.shop_id)})


@sales_draft_router.post("/order-drafts/from-text")
def create_sales_order_draft_from_text_v2(payload: dict, account: V2AuthenticatedAccount = Depends(require_v2_authenticated_account), context: V2ExecutionContext = Depends(require_v2_execution_context), db_session: Session = Depends(get_db_session)):
    if mismatch := _guard(account, context): return mismatch
    try:
        confirmation = create_sales_order_confirmation_from_text(db_session, tenant_id=context.tenant_id, shop_id=context.shop_id, account_id=account.account_id, message=str(payload.get("message") or ""))
    except LookupError:
        return _err(404, "inventory_item_not_found", "Inventory item not found")
    return V2DataEnvelope(data={"confirmation": {"confirmation_id": confirmation.confirmation_id, "confirmation_type": confirmation.confirmation_type, "status": confirmation.status, "draft_payload": confirmation.draft_payload}})
