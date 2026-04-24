"""V2 Ledger API for inventory transaction ledger queries."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps.v2_context import (
    V2AuthenticatedAccount,
    V2ExecutionContext,
    require_v2_authenticated_account,
    require_v2_execution_context,
)
from app.contracts.v2.common import V2DataEnvelope
from app.db.session import get_db_session
from app.services.v2_inventory import list_v2_inventory_events

router = APIRouter(prefix="/api/v2/ledger", tags=["v2-ledger"])


@router.get("/events", response_model=V2DataEnvelope[dict])
def list_ledger_events_v2(
    account: V2AuthenticatedAccount = Depends(require_v2_authenticated_account),
    context: V2ExecutionContext = Depends(require_v2_execution_context),
    item_id: str | None = Query(default=None),
    event_type: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=50),
    db_session: Session = Depends(get_db_session),
) -> V2DataEnvelope[dict]:
    """List inventory ledger events."""
    results = list_v2_inventory_events(
        db_session=db_session,
        tenant_id=context.tenant_id,
        shop_id=context.shop_id,
        limit=limit,
    )
    events_data = []
    for event, item in results:
        events_data.append({
            "event_id": event.event_id,
            "inventory_item_id": event.inventory_item_id,
            "item_name": item.name if item else None,
            "event_type": event.event_type,
            "quantity_delta": float(event.quantity_delta) if event.quantity_delta else 0,
            "quantity_after": float(event.quantity_after) if event.quantity_after else 0,
            "unit": event.unit,
            "price": float(event.price) if event.price else None,
            "source_type": event.source_type,
            "source_id": event.source_id,
            "reason": event.reason,
            "occurred_at": event.occurred_at.isoformat() if event.occurred_at else None,
        })
    return V2DataEnvelope(
        data={
            "events": events_data,
            "count": len(events_data),
        }
    )
