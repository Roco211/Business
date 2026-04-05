from fastapi import APIRouter, Depends, Header, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.contracts.common import DataEnvelope, ErrorBody, ErrorEnvelope
from app.contracts.inventory_item import (
    InventoryItemData,
    ListInventoryItemsMeta,
    ListInventoryItemsResponse,
    RecognizeAndQueryData,
    RecognizeAndQueryInventoryData,
    RecognizeAndQueryRequest,
    RecognizedItemData,
)
from app.core.config import Settings, get_settings
from app.db.session import get_db_session
from app.models import InventoryItem
from app.services.inventory_items import (
    get_inventory_item,
    list_inventory_items,
    recognize_inventory_item_from_media,
)
from app.services.media_uploads import MediaUploadNotReadyError

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


def _error_response(status_code: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=ErrorEnvelope(
            error=ErrorBody(code=code, message=message, details=[])
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


@router.post("/recognize-and-query", response_model=DataEnvelope[RecognizeAndQueryData])
def post_recognize_and_query_inventory_item(
    payload: RecognizeAndQueryRequest,
    authorization: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
    db_session: Session = Depends(get_db_session),
) -> DataEnvelope[RecognizeAndQueryData] | JSONResponse:
    if authorization != "Bearer mock_owner_token":
        return _unauthorized()
    try:
        result = recognize_inventory_item_from_media(
            db_session,
            shop_id=settings.default_shop_id,
            media_id=payload.media_id,
        )
    except MediaUploadNotReadyError:
        return _error_response(
            status.HTTP_404_NOT_FOUND,
            "media_upload_not_found",
            "Media upload not found",
        )
    return DataEnvelope(
        data=RecognizeAndQueryData(
            recognized_item=RecognizedItemData(
                item_id=result.item_id,
                name=result.item_name,
                confidence=result.confidence,
            ),
            inventory=RecognizeAndQueryInventoryData(
                stock=result.stock,
                unit=result.unit,
                is_low_stock=result.is_low_stock,
            ),
        )
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
