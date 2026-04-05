from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps.auth import AuthenticatedContext, require_authenticated_context
from app.contracts.common import DataEnvelope, ErrorBody, ErrorEnvelope
from app.contracts.confirmation import (
    ApproveConfirmationRequest,
    ConfirmationData,
    ListConfirmationsMeta,
    ListConfirmationsResponse,
)
from app.db.session import get_db_session
from app.models import Confirmation, SessionRecord, TaskRun
from app.services.approved_stock_out_commits import commit_approved_stock_out_confirmation
from app.services.approved_receipt_stock_in_commits import commit_approved_receipt_stock_in_confirmation
from app.services.approved_stock_in_commits import commit_approved_stock_in_confirmation
from app.services.confirmations import ConfirmationConflictError, reject_confirmation
from app.services.inventory_items import (
    ApprovedFieldsValidationError,
    InventoryItemAmbiguousError,
    InventoryItemInactiveError,
    InventoryItemNotFoundError,
    InventoryUnitMismatchError,
)
from app.services.runtime_messages import write_runtime_message
from app.services.task_runs import (
    TaskRunTransitionError,
    reject_awaiting_confirmation_task_run,
    resolve_awaiting_confirmation_task_run,
)

router = APIRouter(prefix="/api/v1/confirmations", tags=["confirmations"])


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


def _to_confirmation_data(confirmation: Confirmation, *, task_run: TaskRun | None = None) -> ConfirmationData:
    linked_task_run = task_run or confirmation.task_run
    return ConfirmationData(
        confirmation_id=confirmation.confirmation_id,
        session_id=linked_task_run.session_id,
        task_run_id=confirmation.task_run_id,
        confirmation_type=confirmation.confirmation_type,
        status=confirmation.status,
        fields=confirmation.fields,
        requested_by_employee_id=confirmation.requested_by_employee_id,
        resolution_payload=confirmation.resolution_payload,
        approved_by_actor_id=confirmation.approved_by_actor_id,
        created_at=confirmation.created_at,
        resolved_at=confirmation.resolved_at,
    )


def _validate_approve_payload(payload: ApproveConfirmationRequest) -> dict[str, object] | JSONResponse:
    if not payload.fields:
        return _error_response(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "validation_error",
            "fields must be a non-empty object",
        )
    return payload.fields


def _load_confirmation_for_shop(
    db_session: Session,
    *,
    confirmation_id: str,
    shop_id: str,
) -> Confirmation | None:
    return db_session.scalar(
        select(Confirmation)
        .join(TaskRun, TaskRun.task_run_id == Confirmation.task_run_id)
        .join(SessionRecord, SessionRecord.session_id == TaskRun.session_id)
        .where(
            Confirmation.confirmation_id == confirmation_id,
            SessionRecord.shop_id == shop_id,
        )
    )


def _list_confirmations_for_shop(
    db_session: Session,
    *,
    shop_id: str,
    status_filter: str | None,
    limit: int,
) -> list[Confirmation]:
    statement = (
        select(Confirmation)
        .join(TaskRun, TaskRun.task_run_id == Confirmation.task_run_id)
        .join(SessionRecord, SessionRecord.session_id == TaskRun.session_id)
        .where(SessionRecord.shop_id == shop_id)
    )
    if status_filter is not None:
        statement = statement.where(Confirmation.status == status_filter)
    statement = statement.order_by(Confirmation.created_at.desc(), Confirmation.confirmation_id.desc()).limit(limit)
    return list(db_session.scalars(statement))


@router.get("", response_model=ListConfirmationsResponse)
def get_confirmations(
    auth: AuthenticatedContext = Depends(require_authenticated_context),
    status_filter: str | None = Query(default="pending", alias="status"),
    limit: int = Query(default=20, ge=1, le=50),
    db_session: Session = Depends(get_db_session),
) -> ListConfirmationsResponse | JSONResponse:
    confirmations = _list_confirmations_for_shop(
        db_session,
        shop_id=auth.shop_id,
        status_filter=status_filter,
        limit=max(1, min(limit, 50)),
    )
    return ListConfirmationsResponse(
        data=[_to_confirmation_data(confirmation) for confirmation in confirmations],
        meta=ListConfirmationsMeta(count=len(confirmations)),
    )


@router.post("/{confirmation_id}/approve", response_model=DataEnvelope[ConfirmationData])
def post_approve_confirmation(
    confirmation_id: str,
    payload: ApproveConfirmationRequest,
    auth: AuthenticatedContext = Depends(require_authenticated_context),
    db_session: Session = Depends(get_db_session),
) -> DataEnvelope[ConfirmationData] | JSONResponse:
    try:
        confirmation = _load_confirmation_for_shop(
            db_session,
            confirmation_id=confirmation_id,
            shop_id=auth.shop_id,
        )
        if confirmation is None:
            raise LookupError(confirmation_id)
        if confirmation.confirmation_type == "receipt-stock-in-batch":
            result = commit_approved_receipt_stock_in_confirmation(
                db_session,
                confirmation_id=confirmation_id,
                payload_fields=payload.fields,
                approved_by_actor_id=auth.actor_id,
            )
        elif confirmation.confirmation_type == "stock-out":
            result = commit_approved_stock_out_confirmation(
                db_session,
                confirmation_id=confirmation_id,
                payload_fields=payload.fields,
                approved_by_actor_id=auth.actor_id,
            )
        else:
            result = commit_approved_stock_in_confirmation(
                db_session,
                confirmation_id=confirmation_id,
                payload_fields=payload.fields,
                approved_by_actor_id=auth.actor_id,
            )
    except InventoryItemNotFoundError:
        return _error_response(
            status.HTTP_404_NOT_FOUND,
            "inventory_item_not_found",
            "Inventory item not found",
        )
    except LookupError:
        return _error_response(
            status.HTTP_404_NOT_FOUND,
            "confirmation_not_found",
            "Confirmation not found",
        )
    except ApprovedFieldsValidationError as exc:
        return _error_response(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "confirmation_fields_invalid",
            str(exc),
        )
    except InventoryItemAmbiguousError:
        return _error_response(
            status.HTTP_409_CONFLICT,
            "inventory_item_ambiguous",
            "Inventory item match is ambiguous",
        )
    except InventoryItemInactiveError:
        return _error_response(
            status.HTTP_409_CONFLICT,
            "inventory_item_inactive",
            "Inventory item is inactive",
        )
    except InventoryUnitMismatchError:
        return _error_response(
            status.HTTP_409_CONFLICT,
            "inventory_unit_mismatch",
            "Inventory unit does not match the existing item",
        )
    except (ConfirmationConflictError, TaskRunTransitionError):
        return _error_response(
            status.HTTP_409_CONFLICT,
            "confirmation_not_pending",
            "Confirmation is not pending",
        )
    return DataEnvelope(data=_to_confirmation_data(result.confirmation, task_run=result.task_run))


@router.post("/{confirmation_id}/reject", response_model=DataEnvelope[ConfirmationData])
def post_reject_confirmation(
    confirmation_id: str,
    auth: AuthenticatedContext = Depends(require_authenticated_context),
    db_session: Session = Depends(get_db_session),
) -> DataEnvelope[ConfirmationData] | JSONResponse:
    try:
        confirmation = _load_confirmation_for_shop(
            db_session,
            confirmation_id=confirmation_id,
            shop_id=auth.shop_id,
        )
        if confirmation is None:
            raise LookupError(confirmation_id)
        confirmation = reject_confirmation(
            db_session,
            confirmation_id=confirmation_id,
        )
        task_run = reject_awaiting_confirmation_task_run(
            db_session,
            task_run_id=confirmation.task_run_id,
            result_summary="Owner rejected the confirmation and the stock-in task was rejected.",
        )
        write_runtime_message(
            db_session,
            session_id=task_run.session_id,
            task_run_id=task_run.task_run_id,
            text="Mock runtime: owner rejected the confirmation and the stock-in task was rejected.",
        )
        db_session.commit()
    except LookupError:
        db_session.rollback()
        return _error_response(
            status.HTTP_404_NOT_FOUND,
            "confirmation_not_found",
            "Confirmation not found",
        )
    except (ConfirmationConflictError, TaskRunTransitionError):
        db_session.rollback()
        return _error_response(
            status.HTTP_409_CONFLICT,
            "confirmation_not_pending",
            "Confirmation is not pending",
        )

    return DataEnvelope(data=_to_confirmation_data(confirmation, task_run=task_run))
