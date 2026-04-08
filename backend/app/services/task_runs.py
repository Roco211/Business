from datetime import UTC, datetime
from dataclasses import dataclass

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.ids import new_prefixed_id
from app.models.task_run import TaskRun
from app.services.session_stream import append_task_updated_event

PENDING_CLASSIFICATION_TASK_TYPE = "pending-classification"
CREATED_STATUS = "created"
PROCESSING_STATUS = "processing"
AWAITING_CONFIRMATION_STATUS = "awaiting-confirmation"
COMPLETED_STATUS = "completed"
FAILED_STATUS = "failed"
REJECTED_STATUS = "rejected"


@dataclass(frozen=True)
class TaskRunTransitionResult:
    changed: bool
    task_run: TaskRun


class TaskRunTransitionError(ValueError):
    pass


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _load_task_run(db_session: Session, task_run_id: str) -> TaskRun | None:
    return db_session.scalar(
        select(TaskRun)
        .where(TaskRun.task_run_id == task_run_id)
        .execution_options(populate_existing=True)
    )


def _require_task_run(db_session: Session, task_run_id: str) -> TaskRun:
    task_run = _load_task_run(db_session, task_run_id)
    if task_run is None:
        raise LookupError(task_run_id)
    return task_run


def create_initial_task_run(
    db_session: Session,
    *,
    session_id: str,
    source_message_id: str,
) -> TaskRun:
    now = _now()
    task_run = TaskRun(
        task_run_id=new_prefixed_id("task"),
        session_id=session_id,
        source_message_id=source_message_id,
        task_type=PENDING_CLASSIFICATION_TASK_TYPE,
        status=CREATED_STATUS,
        assigned_employee_id=None,
        result_summary=None,
        error_code=None,
        error_message=None,
        created_at=now,
        updated_at=now,
        completed_at=None,
    )
    db_session.add(task_run)
    db_session.flush()
    return task_run


def claim_task_run_for_runtime(
    db_session: Session,
    *,
    task_run_id: str,
) -> TaskRunTransitionResult:
    result = db_session.execute(
        update(TaskRun)
        .where(
            TaskRun.task_run_id == task_run_id,
            TaskRun.status == CREATED_STATUS,
            TaskRun.task_type == PENDING_CLASSIFICATION_TASK_TYPE,
        )
        .values(status=PROCESSING_STATUS, updated_at=_now())
        .execution_options(synchronize_session=False)
    )
    task_run = _require_task_run(db_session, task_run_id)
    if result.rowcount == 1:
        append_task_updated_event(db_session, task_run=task_run)
    return TaskRunTransitionResult(changed=result.rowcount == 1, task_run=task_run)


def complete_task_run(
    db_session: Session,
    *,
    task_run_id: str,
    task_type: str,
    assigned_employee_id: str,
    result_summary: str,
) -> TaskRun:
    now = _now()
    result = db_session.execute(
        update(TaskRun)
        .where(
            TaskRun.task_run_id == task_run_id,
            TaskRun.status == PROCESSING_STATUS,
        )
        .values(
            task_type=task_type,
            status=COMPLETED_STATUS,
            assigned_employee_id=assigned_employee_id,
            result_summary=result_summary,
            error_code=None,
            error_message=None,
            updated_at=now,
            completed_at=now,
        )
        .execution_options(synchronize_session=False)
    )
    task_run = _require_task_run(db_session, task_run_id)
    if result.rowcount != 1:
        raise TaskRunTransitionError(
            f"Task run {task_run_id} must be in '{PROCESSING_STATUS}' status to complete; found '{task_run.status}'."
        )
    append_task_updated_event(db_session, task_run=task_run)
    return task_run


def fail_task_run(
    db_session: Session,
    *,
    task_run_id: str,
    error_code: str,
    error_message: str,
    result_summary: str,
) -> TaskRun:
    now = _now()
    result = db_session.execute(
        update(TaskRun)
        .where(
            TaskRun.task_run_id == task_run_id,
            TaskRun.status == PROCESSING_STATUS,
        )
        .values(
            status=FAILED_STATUS,
            assigned_employee_id=None,
            result_summary=result_summary,
            error_code=error_code,
            error_message=error_message,
            updated_at=now,
            completed_at=now,
        )
        .execution_options(synchronize_session=False)
    )
    task_run = _require_task_run(db_session, task_run_id)
    if result.rowcount != 1:
        raise TaskRunTransitionError(
            f"Task run {task_run_id} must be in '{PROCESSING_STATUS}' status to fail; found '{task_run.status}'."
        )
    append_task_updated_event(db_session, task_run=task_run)
    return task_run


def mark_task_run_awaiting_confirmation(
    db_session: Session,
    *,
    task_run_id: str,
    task_type: str,
    assigned_employee_id: str,
    result_summary: str,
) -> TaskRun:
    now = _now()
    result = db_session.execute(
        update(TaskRun)
        .where(
            TaskRun.task_run_id == task_run_id,
            TaskRun.status == PROCESSING_STATUS,
        )
        .values(
            task_type=task_type,
            status=AWAITING_CONFIRMATION_STATUS,
            assigned_employee_id=assigned_employee_id,
            result_summary=result_summary,
            error_code=None,
            error_message=None,
            updated_at=now,
            completed_at=None,
        )
        .execution_options(synchronize_session=False)
    )
    task_run = _require_task_run(db_session, task_run_id)
    if result.rowcount != 1:
        raise TaskRunTransitionError(
            f"Task run {task_run_id} must be in '{PROCESSING_STATUS}' status to await confirmation; found '{task_run.status}'."
        )
    append_task_updated_event(db_session, task_run=task_run)
    return task_run


def resolve_awaiting_confirmation_task_run(
    db_session: Session,
    *,
    task_run_id: str,
    result_summary: str,
) -> TaskRun:
    now = _now()
    result = db_session.execute(
        update(TaskRun)
        .where(
            TaskRun.task_run_id == task_run_id,
            TaskRun.status == AWAITING_CONFIRMATION_STATUS,
        )
        .values(
            status=COMPLETED_STATUS,
            result_summary=result_summary,
            error_code=None,
            error_message=None,
            updated_at=now,
            completed_at=now,
        )
        .execution_options(synchronize_session=False)
    )
    task_run = _require_task_run(db_session, task_run_id)
    if result.rowcount != 1:
        raise TaskRunTransitionError(
            f"Task run {task_run_id} must be in '{AWAITING_CONFIRMATION_STATUS}' status to resolve; found '{task_run.status}'."
        )
    append_task_updated_event(db_session, task_run=task_run)
    return task_run


def reject_awaiting_confirmation_task_run(
    db_session: Session,
    *,
    task_run_id: str,
    result_summary: str,
) -> TaskRun:
    now = _now()
    result = db_session.execute(
        update(TaskRun)
        .where(
            TaskRun.task_run_id == task_run_id,
            TaskRun.status == AWAITING_CONFIRMATION_STATUS,
        )
        .values(
            status=REJECTED_STATUS,
            result_summary=result_summary,
            error_code=None,
            error_message=None,
            updated_at=now,
            completed_at=now,
        )
        .execution_options(synchronize_session=False)
    )
    task_run = _require_task_run(db_session, task_run_id)
    if result.rowcount != 1:
        raise TaskRunTransitionError(
            f"Task run {task_run_id} must be in '{AWAITING_CONFIRMATION_STATUS}' status to reject; found '{task_run.status}'."
        )
    append_task_updated_event(db_session, task_run=task_run)
    return task_run
