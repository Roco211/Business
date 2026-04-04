from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.ids import new_prefixed_id
from app.models import Confirmation, TaskRun

PENDING_STATUS = "pending"
APPROVED_STATUS = "approved"
REJECTED_STATUS = "rejected"


@dataclass(frozen=True)
class ConfirmationListPage:
    items: list[Confirmation]


class ConfirmationConflictError(ValueError):
    pass


class ConfirmationTaskRunLifecycleError(ValueError):
    pass


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _load_confirmation(db_session: Session, confirmation_id: str) -> Confirmation | None:
    return db_session.scalar(
        select(Confirmation)
        .where(Confirmation.confirmation_id == confirmation_id)
        .execution_options(populate_existing=True)
    )


def _require_confirmation(db_session: Session, confirmation_id: str) -> Confirmation:
    confirmation = _load_confirmation(db_session, confirmation_id)
    if confirmation is None:
        raise LookupError(confirmation_id)
    return confirmation


def _require_task_run(db_session: Session, task_run_id: str) -> TaskRun:
    task_run = db_session.scalar(
        select(TaskRun)
        .where(TaskRun.task_run_id == task_run_id)
        .execution_options(populate_existing=True)
    )
    if task_run is None:
        raise LookupError(task_run_id)
    return task_run


def _require_task_run_ready_for_confirmation_creation(db_session: Session, task_run_id: str) -> TaskRun:
    task_run = _require_task_run(db_session, task_run_id)
    if task_run.status != "processing":
        raise ConfirmationTaskRunLifecycleError(
            f"Task run {task_run_id} must be in 'processing' status to create a pending confirmation; "
            f"found '{task_run.status}'."
        )
    return task_run


def _load_confirmation_for_task_run(db_session: Session, task_run_id: str) -> Confirmation | None:
    return db_session.scalar(select(Confirmation).where(Confirmation.task_run_id == task_run_id))


def get_pending_confirmation_for_task_run(
    db_session: Session,
    *,
    task_run_id: str,
) -> Confirmation | None:
    return db_session.scalar(
        select(Confirmation).where(
            Confirmation.task_run_id == task_run_id,
            Confirmation.status == PENDING_STATUS,
        )
    )


def create_pending_confirmation(
    db_session: Session,
    *,
    task_run_id: str,
    confirmation_type: str,
    fields: dict[str, Any],
    requested_by_employee_id: str | None,
) -> Confirmation:
    _require_task_run_ready_for_confirmation_creation(db_session, task_run_id)
    existing_pending = get_pending_confirmation_for_task_run(db_session, task_run_id=task_run_id)
    if existing_pending is not None:
        return existing_pending

    existing = _load_confirmation_for_task_run(db_session, task_run_id)
    if existing is not None:
        raise ValueError(
            f"Task run {task_run_id} already has a non-pending confirmation in status '{existing.status}'."
        )

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
    try:
        with db_session.begin_nested():
            db_session.add(confirmation)
            db_session.flush()
    except IntegrityError:
        existing_pending = get_pending_confirmation_for_task_run(db_session, task_run_id=task_run_id)
        if existing_pending is not None:
            return existing_pending
        existing = _load_confirmation_for_task_run(db_session, task_run_id)
        if existing is not None:
            raise ValueError(
                f"Task run {task_run_id} already has a non-pending confirmation in status '{existing.status}'."
            )
        raise
    return confirmation


def approve_confirmation(
    db_session: Session,
    *,
    confirmation_id: str,
    resolution_payload: dict[str, Any],
    approved_by_actor_id: str,
) -> Confirmation:
    resolved_at = _now()
    result = db_session.execute(
        update(Confirmation)
        .where(
            Confirmation.confirmation_id == confirmation_id,
            Confirmation.status == PENDING_STATUS,
        )
        .values(
            status=APPROVED_STATUS,
            resolution_payload=resolution_payload,
            approved_by_actor_id=approved_by_actor_id,
            resolved_at=resolved_at,
        )
        .execution_options(synchronize_session=False)
    )
    confirmation = _require_confirmation(db_session, confirmation_id)
    if result.rowcount != 1:
        raise ConfirmationConflictError(
            f"Confirmation {confirmation_id} must be in '{PENDING_STATUS}' status; found '{confirmation.status}'."
        )
    return confirmation


def reject_confirmation(
    db_session: Session,
    *,
    confirmation_id: str,
) -> Confirmation:
    resolved_at = _now()
    result = db_session.execute(
        update(Confirmation)
        .where(
            Confirmation.confirmation_id == confirmation_id,
            Confirmation.status == PENDING_STATUS,
        )
        .values(
            status=REJECTED_STATUS,
            resolution_payload=None,
            approved_by_actor_id=None,
            resolved_at=resolved_at,
        )
        .execution_options(synchronize_session=False)
    )
    confirmation = _require_confirmation(db_session, confirmation_id)
    if result.rowcount != 1:
        raise ConfirmationConflictError(
            f"Confirmation {confirmation_id} must be in '{PENDING_STATUS}' status; found '{confirmation.status}'."
        )
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
