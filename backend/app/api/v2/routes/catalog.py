"""V2 Catalog API for product catalog management."""
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
from app.services.v2_inventory import list_v2_inventory_items

router = APIRouter(prefix="/api/v2/inventory", tags=["v2-catalog"])


@router.get("/catalog", response_model=V2DataEnvelope[dict])
def list_catalog_items_v2(
    account: V2AuthenticatedAccount = Depends(require_v2_authenticated_account),
    context: V2ExecutionContext = Depends(require_v2_execution_context),
    query: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=50),
    db_session: Session = Depends(get_db_session),
) -> V2DataEnvelope[dict]:
    """List products in the catalog."""
    items_data = list_v2_inventory_items(
        db_session=db_session,
        tenant_id=context.tenant_id,
        query=query,
        limit=limit,
    )
    return V2DataEnvelope(
        data={
            "items": [
                {
                    "inventory_item_id": item.inventory_item_id,
                    "sku": item.sku,
                    "name": item.name,
                    "barcode": item.barcode,
                    "default_unit": item.default_unit,
                    "status": item.status,
                    "created_at": item.created_at.isoformat() if item.created_at else None,
                    "updated_at": item.updated_at.isoformat() if item.updated_at else None,
                }
                for item in items_data
            ],
            "count": len(items_data),
        }
    )
