from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api.deps.v2_context import (
    V2AuthenticatedAccount,
    V2ExecutionContext,
    require_v2_authenticated_account,
    require_v2_execution_context,
)
from app.contracts.v2.common import V2DataEnvelope, V2ErrorBody, V2ErrorEnvelope
from app.contracts.v2.internal import (
    V2ProjectionReplayData,
    V2ProjectionReplayRequest,
    V2WorkerHealthData,
)
from app.db.session import get_db_session
from app.services.v2_inventory import V2InventoryItemNotFoundError
from app.services.v2_inventory_projections import replay_v2_inventory_stock_projection
from app.services.v2_outbox import get_v2_outbox_health_summary

router = APIRouter(prefix="/api/v2/internal", tags=["v2-internal"])


def _context_account_mismatch() -> JSONResponse:
    return JSONResponse(
        status_code=403,
        content=V2ErrorEnvelope(
            error=V2ErrorBody(code="context_account_mismatch", message="Context account mismatch")
        ).model_dump(),
    )


@router.get("/worker-health", response_model=V2DataEnvelope[V2WorkerHealthData])
def get_v2_worker_health(
    account: V2AuthenticatedAccount = Depends(require_v2_authenticated_account),
    context: V2ExecutionContext = Depends(require_v2_execution_context),
    db_session: Session = Depends(get_db_session),
) -> V2DataEnvelope[V2WorkerHealthData] | JSONResponse:
    if account.account_id != context.account_id:
        return _context_account_mismatch()

    summary = get_v2_outbox_health_summary(
        db_session,
        tenant_id=context.tenant_id,
        shop_id=context.shop_id,
    )
    return V2DataEnvelope(
        data=V2WorkerHealthData(
            tenant_id=summary.tenant_id,
            shop_id=summary.shop_id,
            pending_count=summary.pending_count,
            processing_count=summary.processing_count,
            completed_count=summary.completed_count,
            failed_count=summary.failed_count,
            oldest_pending_at=summary.oldest_pending_at,
            oldest_available_pending_at=summary.oldest_available_pending_at,
        )
    )


@router.post("/projections/replay", response_model=V2DataEnvelope[V2ProjectionReplayData])
def post_v2_projection_replay(
    payload: V2ProjectionReplayRequest,
    account: V2AuthenticatedAccount = Depends(require_v2_authenticated_account),
    context: V2ExecutionContext = Depends(require_v2_execution_context),
    db_session: Session = Depends(get_db_session),
) -> V2DataEnvelope[V2ProjectionReplayData] | JSONResponse:
    if account.account_id != context.account_id:
        return _context_account_mismatch()

    try:
        result = replay_v2_inventory_stock_projection(
            db_session,
            tenant_id=context.tenant_id,
            shop_id=context.shop_id,
            inventory_item_id=payload.inventory_item_id,
        )
    except V2InventoryItemNotFoundError:
        return JSONResponse(
            status_code=404,
            content=V2ErrorEnvelope(
                error=V2ErrorBody(code="inventory_item_not_found", message="Inventory item not found")
            ).model_dump(),
        )

    db_session.commit()
    return V2DataEnvelope(
        data=V2ProjectionReplayData(
            tenant_id=result.tenant_id,
            shop_id=result.shop_id,
            inventory_item_id=result.inventory_item_id,
            replayed_item_count=result.replayed_item_count,
            replayed_snapshot_count=result.replayed_snapshot_count,
            deleted_snapshot_count=result.deleted_snapshot_count,
            ledger_event_count=result.ledger_event_count,
            replayed_at=result.replayed_at,
        )
    )
