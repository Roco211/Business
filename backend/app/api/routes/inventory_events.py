from fastapi import APIRouter, Depends, Header, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.contracts.common import DataEnvelope, ErrorBody, ErrorEnvelope
from app.contracts.inventory_event import CreateInventoryCorrectionData, CreateInventoryCorrectionRequest
from app.core.config import Settings, get_settings
from app.db.session import get_db_session
from app.services.inventory_corrections import (
    InventoryCorrectionConflictError,
    InventoryCorrectionItemNotFoundError,
    InventoryCorrectionValidationError,
    submit_inventory_correction,
)

router = APIRouter(prefix="/api/v1/inventory-events", tags=["inventory-events"])


def _unauthorized() -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content=ErrorEnvelope(
            error=ErrorBody(code="unauthorized", message="Unauthorized", details=[])
        ).model_dump(),
    )


def _error_response(status_code: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=ErrorEnvelope(
            error=ErrorBody(code=code, message=message, details=[])
        ).model_dump(),
    )


@router.post("/corrections", response_model=DataEnvelope[CreateInventoryCorrectionData])
def post_inventory_correction(
    payload: CreateInventoryCorrectionRequest,
    authorization: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
    db_session: Session = Depends(get_db_session),
) -> DataEnvelope[CreateInventoryCorrectionData] | JSONResponse:
    if authorization != "Bearer mock_owner_token":
        return _unauthorized()

    try:
        result = submit_inventory_correction(
            db_session,
            shop_id=settings.default_shop_id,
            item_id=payload.item_id,
            expected_quantity=payload.expected_quantity,
            corrected_quantity=payload.corrected_quantity,
            reason=payload.reason,
            actor_id=settings.default_owner_actor_id,
        )
    except InventoryCorrectionItemNotFoundError:
        return _error_response(status.HTTP_404_NOT_FOUND, "item_not_found", "Inventory item not found")
    except InventoryCorrectionConflictError:
        return _error_response(
            status.HTTP_409_CONFLICT,
            "inventory_conflict",
            "Inventory correction conflicts with the current item state",
        )
    except InventoryCorrectionValidationError as exc:
        return _error_response(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "validation_error",
            str(exc),
        )

    return DataEnvelope(
        data=CreateInventoryCorrectionData(
            correction_event_id=result.inventory_event.inventory_event_id,
            item_id=result.inventory_item.item_id,
            new_quantity=result.inventory_item.current_stock,
        )
    )
