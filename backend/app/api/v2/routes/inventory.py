from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api.deps.v2_context import (
    V2AuthenticatedAccount,
    V2ExecutionContext,
    require_v2_authenticated_account,
    require_v2_execution_context,
)
from app.contracts.v2.common import V2DataEnvelope, V2ErrorBody, V2ErrorEnvelope
from app.contracts.v2.inventory import (
    V2InventoryItemData,
    V2InventoryItemListData,
    V2InventoryLedgerEventData,
    V2InventoryLedgerEventListData,
    V2InventoryStockData,
    V2InventoryStockListData,
    V2SubmitInventoryCorrectionData,
    V2SubmitInventoryCorrectionRequest,
    V2SubmitInventoryStockInData,
    V2SubmitInventoryStockInRequest,
    V2SubmitInventoryStockOutData,
    V2SubmitInventoryStockOutRequest,
)
from app.db.session import get_db_session
from app.services.v2_inventory import (
    V2InventoryCorrectionConflictError,
    V2InventoryCorrectionItemNotFoundError,
    V2InventoryCorrectionValidationError,
    V2InventoryStockInItemNotFoundError,
    V2InventoryStockInValidationError,
    V2InventoryStockOutConflictError,
    V2InventoryStockOutItemNotFoundError,
    V2InventoryStockOutValidationError,
    list_v2_inventory_events,
    list_v2_inventory_items,
    list_v2_inventory_stock,
    submit_v2_inventory_correction,
    submit_v2_inventory_stock_in,
    submit_v2_inventory_stock_out,
)

router = APIRouter(prefix="/api/v2/inventory", tags=["v2-inventory"])


def _context_account_mismatch() -> JSONResponse:
    return JSONResponse(
        status_code=403,
        content=V2ErrorEnvelope(
            error=V2ErrorBody(code="context_account_mismatch", message="Context account mismatch")
        ).model_dump(),
    )


@router.get("/items", response_model=V2DataEnvelope[V2InventoryItemListData])
def list_inventory_items_v2(
    account: V2AuthenticatedAccount = Depends(require_v2_authenticated_account),
    context: V2ExecutionContext = Depends(require_v2_execution_context),
    query: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=50),
    db_session: Session = Depends(get_db_session),
) -> V2DataEnvelope[V2InventoryItemListData] | JSONResponse:
    if account.account_id != context.account_id:
        return _context_account_mismatch()

    items = [
        V2InventoryItemData(
            inventory_item_id=item.inventory_item_id,
            tenant_id=item.tenant_id,
            sku=item.sku,
            name=item.name,
            barcode=item.barcode,
            default_unit=item.default_unit,
            status=item.status,
            created_at=item.created_at,
            updated_at=item.updated_at,
        )
        for item in list_v2_inventory_items(
            db_session,
            tenant_id=context.tenant_id,
            query=query,
            limit=limit,
        )
    ]
    return V2DataEnvelope(data=V2InventoryItemListData(items=items, count=len(items)))


@router.get("/stock", response_model=V2DataEnvelope[V2InventoryStockListData])
def list_inventory_stock_v2(
    account: V2AuthenticatedAccount = Depends(require_v2_authenticated_account),
    context: V2ExecutionContext = Depends(require_v2_execution_context),
    limit: int = Query(default=20, ge=1, le=50),
    db_session: Session = Depends(get_db_session),
) -> V2DataEnvelope[V2InventoryStockListData] | JSONResponse:
    if account.account_id != context.account_id:
        return _context_account_mismatch()

    items = [
        V2InventoryStockData(
            snapshot_id=snapshot.snapshot_id,
            tenant_id=snapshot.tenant_id,
            shop_id=snapshot.shop_id,
            inventory_item_id=snapshot.inventory_item_id,
            item_name=item.name,
            default_unit=item.default_unit,
            current_quantity=snapshot.current_quantity,
            current_price=snapshot.current_price,
            low_stock_threshold=snapshot.low_stock_threshold,
            updated_at=snapshot.updated_at,
        )
        for snapshot, item in list_v2_inventory_stock(
            db_session,
            tenant_id=context.tenant_id,
            shop_id=context.shop_id,
            limit=limit,
        )
    ]
    return V2DataEnvelope(data=V2InventoryStockListData(items=items, count=len(items)))


@router.get("/events", response_model=V2DataEnvelope[V2InventoryLedgerEventListData])
def list_inventory_events_v2(
    account: V2AuthenticatedAccount = Depends(require_v2_authenticated_account),
    context: V2ExecutionContext = Depends(require_v2_execution_context),
    limit: int = Query(default=20, ge=1, le=50),
    db_session: Session = Depends(get_db_session),
) -> V2DataEnvelope[V2InventoryLedgerEventListData] | JSONResponse:
    if account.account_id != context.account_id:
        return _context_account_mismatch()

    events = [
        V2InventoryLedgerEventData(
            event_id=event.event_id,
            tenant_id=event.tenant_id,
            shop_id=event.shop_id,
            inventory_item_id=event.inventory_item_id,
            item_name=item.name,
            event_type=event.event_type,
            quantity_delta=event.quantity_delta,
            quantity_after=event.quantity_after,
            unit=event.unit,
            price=event.price,
            source_type=event.source_type,
            source_id=event.source_id,
            reason=event.reason,
            created_by_account_id=event.created_by_account_id,
            occurred_at=event.occurred_at,
        )
        for event, item in list_v2_inventory_events(
            db_session,
            tenant_id=context.tenant_id,
            shop_id=context.shop_id,
            limit=limit,
        )
    ]
    return V2DataEnvelope(data=V2InventoryLedgerEventListData(events=events, count=len(events)))


@router.post("/corrections", response_model=V2DataEnvelope[V2SubmitInventoryCorrectionData])
def submit_inventory_correction_v2(
    payload: V2SubmitInventoryCorrectionRequest,
    account: V2AuthenticatedAccount = Depends(require_v2_authenticated_account),
    context: V2ExecutionContext = Depends(require_v2_execution_context),
    db_session: Session = Depends(get_db_session),
) -> V2DataEnvelope[V2SubmitInventoryCorrectionData] | JSONResponse:
    if account.account_id != context.account_id:
        return _context_account_mismatch()

    try:
        result = submit_v2_inventory_correction(
            db_session,
            tenant_id=context.tenant_id,
            shop_id=context.shop_id,
            inventory_item_id=payload.inventory_item_id,
            expected_quantity=payload.expected_quantity,
            corrected_quantity=payload.corrected_quantity,
            reason=payload.reason,
            created_by_account_id=account.account_id,
        )
    except V2InventoryCorrectionItemNotFoundError:
        return JSONResponse(
            status_code=404,
            content=V2ErrorEnvelope(
                error=V2ErrorBody(code="inventory_item_not_found", message="Inventory item not found")
            ).model_dump(),
        )
    except V2InventoryCorrectionConflictError:
        return JSONResponse(
            status_code=409,
            content=V2ErrorEnvelope(
                error=V2ErrorBody(code="inventory_conflict", message="Inventory correction conflicts with current stock")
            ).model_dump(),
        )
    except V2InventoryCorrectionValidationError as exc:
        return JSONResponse(
            status_code=422,
            content=V2ErrorEnvelope(
                error=V2ErrorBody(code="validation_error", message=str(exc))
            ).model_dump(),
        )

    return V2DataEnvelope(
        data=V2SubmitInventoryCorrectionData(
            correction_event_id=result.event.event_id,
            inventory_item_id=result.event.inventory_item_id,
            new_quantity=result.snapshot.current_quantity,
        )
    )


@router.post("/stock-in", response_model=V2DataEnvelope[V2SubmitInventoryStockInData])
def submit_inventory_stock_in_v2(
    payload: V2SubmitInventoryStockInRequest,
    account: V2AuthenticatedAccount = Depends(require_v2_authenticated_account),
    context: V2ExecutionContext = Depends(require_v2_execution_context),
    db_session: Session = Depends(get_db_session),
) -> V2DataEnvelope[V2SubmitInventoryStockInData] | JSONResponse:
    if account.account_id != context.account_id:
        return _context_account_mismatch()

    try:
        result = submit_v2_inventory_stock_in(
            db_session,
            tenant_id=context.tenant_id,
            shop_id=context.shop_id,
            inventory_item_id=payload.inventory_item_id,
            item_name=payload.item_name,
            stock_in_quantity=payload.stock_in_quantity,
            unit=payload.unit,
            price=payload.price,
            reason=payload.reason,
            created_by_account_id=account.account_id,
        )
    except V2InventoryStockInItemNotFoundError:
        return JSONResponse(
            status_code=404,
            content=V2ErrorEnvelope(
                error=V2ErrorBody(code="inventory_item_not_found", message="Inventory item not found")
            ).model_dump(),
        )
    except V2InventoryStockInValidationError as exc:
        return JSONResponse(
            status_code=422,
            content=V2ErrorEnvelope(
                error=V2ErrorBody(code="validation_error", message=str(exc))
            ).model_dump(),
        )

    return V2DataEnvelope(
        data=V2SubmitInventoryStockInData(
            stock_in_event_id=result.event.event_id,
            inventory_item_id=result.event.inventory_item_id,
            new_quantity=result.snapshot.current_quantity,
        )
    )


@router.post("/stock-out", response_model=V2DataEnvelope[V2SubmitInventoryStockOutData])
def submit_inventory_stock_out_v2(
    payload: V2SubmitInventoryStockOutRequest,
    account: V2AuthenticatedAccount = Depends(require_v2_authenticated_account),
    context: V2ExecutionContext = Depends(require_v2_execution_context),
    db_session: Session = Depends(get_db_session),
) -> V2DataEnvelope[V2SubmitInventoryStockOutData] | JSONResponse:
    if account.account_id != context.account_id:
        return _context_account_mismatch()

    try:
        result = submit_v2_inventory_stock_out(
            db_session,
            tenant_id=context.tenant_id,
            shop_id=context.shop_id,
            inventory_item_id=payload.inventory_item_id,
            expected_quantity=payload.expected_quantity,
            stock_out_quantity=payload.stock_out_quantity,
            reason=payload.reason,
            created_by_account_id=account.account_id,
        )
    except V2InventoryStockOutItemNotFoundError:
        return JSONResponse(
            status_code=404,
            content=V2ErrorEnvelope(
                error=V2ErrorBody(code="inventory_item_not_found", message="Inventory item not found")
            ).model_dump(),
        )
    except V2InventoryStockOutConflictError:
        return JSONResponse(
            status_code=409,
            content=V2ErrorEnvelope(
                error=V2ErrorBody(code="inventory_conflict", message="Inventory stock-out conflicts with current stock")
            ).model_dump(),
        )
    except V2InventoryStockOutValidationError as exc:
        return JSONResponse(
            status_code=422,
            content=V2ErrorEnvelope(
                error=V2ErrorBody(code="validation_error", message=str(exc))
            ).model_dump(),
        )

    return V2DataEnvelope(
        data=V2SubmitInventoryStockOutData(
            stock_out_event_id=result.event.event_id,
            inventory_item_id=result.event.inventory_item_id,
            new_quantity=result.snapshot.current_quantity,
        )
    )
