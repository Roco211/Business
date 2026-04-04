from fastapi import APIRouter, Depends, Header, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.contracts.common import DataEnvelope, ErrorBody, ErrorEnvelope
from app.contracts.inventory_item import (
    InventoryItemData,
    ListInventoryItemsMeta,
    ListInventoryItemsResponse,
)
from app.core.config import Settings, get_settings
from app.db.session import get_db_session
from app.models import InventoryItem
from app.services.inventory_items import get_inventory_item, list_inventory_items

router = APIRouter(prefix="/api/v1/inventory-items", tags=["inventory-items"])


def _unauthorized() -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content=ErrorEnvelope(
            error=ErrorBody(code="unauthorized", message="Unauthorized", details=[])
        ).model_dump(),
    )


def _not_found() -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content=ErrorEnvelope(
            error=ErrorBody(
                code="inventory_item_not_found",
                message="Inventory item not found",
                details=[],
            )
        ).model_dump(),
    )


def _to_inventory_item_data(item: InventoryItem) -> InventoryItemData:
    return InventoryItemData.model_validate(item, from_attributes=True)


@router.get("", response_model=ListInventoryItemsResponse)
def get_inventory_items(
    authorization: str | None = Header(default=None),
    query: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=50),
    settings: Settings = Depends(get_settings),
    db_session: Session = Depends(get_db_session),
) -> ListInventoryItemsResponse | JSONResponse:
    if authorization != "Bearer mock_owner_token":
        return _unauthorized()

    page = list_inventory_items(
        db_session,
        shop_id=settings.default_shop_id,
        query=query,
        limit=limit,
    )
    return ListInventoryItemsResponse(
        data=[_to_inventory_item_data(item) for item in page.items],
        meta=ListInventoryItemsMeta(count=len(page.items)),
    )


@router.get("/{item_id}", response_model=DataEnvelope[InventoryItemData])
def get_inventory_item_detail(
    item_id: str,
    authorization: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
    db_session: Session = Depends(get_db_session),
) -> DataEnvelope[InventoryItemData] | JSONResponse:
    if authorization != "Bearer mock_owner_token":
        return _unauthorized()
    try:
        item = get_inventory_item(
            db_session,
            shop_id=settings.default_shop_id,
            item_id=item_id,
        )
    except LookupError:
        return _not_found()
    return DataEnvelope(data=_to_inventory_item_data(item))
