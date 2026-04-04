from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.ids import new_prefixed_id
from app.models import Confirmation

PENDING_STATUS = "pending"
APPROVED_STATUS = "approved"
REJECTED_STATUS = "rejected"


@dataclass(frozen=True)
class ConfirmationListPage:
    items: list[Confirmation]


class ConfirmationConflictError(ValueError):
    pass


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _require_confirmation(db_session: Session, confirmation_id: str) -> Confirmation:
    confirmation = db_session.get(Confirmation, confirmation_id)
    if confirmation is None:
        raise LookupError(confirmation_id)
    return confirmation


def create_pending_confirmation(
    db_session: Session,
    *,
    task_run_id: str,
    confirmation_type: str,
    fields: dict[str, Any],
    requested_by_employee_id: str | None,
) -> Confirmation:
    existing = db_session.scalar(select(Confirmation).where(Confirmation.task_run_id == task_run_id))
    if existing is not None:
        return existing

    now = _now()
    confirmation = Confirmation(
        confirmation_id=new_prefixed_id("conf"),
        task_run_id=task_run_id,
        confirmation_type=confirmation_type,
        status=PENDING_STATUS,
        fields=fields,
        requested_by_employee_id=requested_by_employee_id,
        resolution_payload=None,
        approved_by_actor_id=None,
        created_at=now,
        resolved_at=None,
    )
    db_session.add(confirmation)
    db_session.flush()
    return confirmation


def approve_confirmation(
    db_session: Session,
    *,
    confirmation_id: str,
    resolution_payload: dict[str, Any],
    approved_by_actor_id: str,
) -> Confirmation:
    confirmation = _require_confirmation(db_session, confirmation_id)
    if confirmation.status != PENDING_STATUS:
        raise ConfirmationConflictError("Confirmation already resolved")

    confirmation.status = APPROVED_STATUS
    confirmation.resolution_payload = resolution_payload
    confirmation.approved_by_actor_id = approved_by_actor_id
    confirmation.resolved_at = _now()
    db_session.flush()
    return confirmation


def reject_confirmation(
    db_session: Session,
    *,
    confirmation_id: str,
) -> Confirmation:
    confirmation = _require_confirmation(db_session, confirmation_id)
    if confirmation.status != PENDING_STATUS:
        raise ConfirmationConflictError("Confirmation already resolved")

    confirmation.status = REJECTED_STATUS
    confirmation.resolution_payload = None
    confirmation.approved_by_actor_id = None
    confirmation.resolved_at = _now()
    db_session.flush()
    return confirmation


def list_confirmations(
    db_session: Session,
    *,
    status: str | None,
    limit: int,
) -> ConfirmationListPage:
    safe_limit = max(1, min(limit, 50))
    query = select(Confirmation)
    if status is not None:
        query = query.where(Confirmation.status == status)
    query = query.order_by(Confirmation.created_at.desc(), Confirmation.confirmation_id.desc()).limit(safe_limit)
    return ConfirmationListPage(items=list(db_session.scalars(query)))
