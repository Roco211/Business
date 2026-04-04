from datetime import UTC, datetime
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.ids import new_prefixed_id
from app.models.task_run import TaskRun

PENDING_CLASSIFICATION_TASK_TYPE = "pending-classification"
CREATED_STATUS = "created"
PROCESSING_STATUS = "processing"
COMPLETED_STATUS = "completed"
FAILED_STATUS = "failed"


@dataclass(frozen=True)
class TaskRunTransitionResult:
    changed: bool
    task_run: TaskRun


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


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
    task_run = db_session.get(TaskRun, task_run_id)
    if task_run is None:
        raise LookupError(task_run_id)
    if task_run.status != CREATED_STATUS or task_run.task_type != PENDING_CLASSIFICATION_TASK_TYPE:
        return TaskRunTransitionResult(changed=False, task_run=task_run)

    task_run.status = PROCESSING_STATUS
    task_run.updated_at = _now()
    db_session.flush()
    return TaskRunTransitionResult(changed=True, task_run=task_run)


def complete_task_run(
    db_session: Session,
    *,
    task_run_id: str,
    task_type: str,
    assigned_employee_id: str,
    result_summary: str,
) -> TaskRun:
    task_run = db_session.get(TaskRun, task_run_id)
    if task_run is None:
        raise LookupError(task_run_id)

    now = _now()
    task_run.task_type = task_type
    task_run.status = COMPLETED_STATUS
    task_run.assigned_employee_id = assigned_employee_id
    task_run.result_summary = result_summary
    task_run.error_code = None
    task_run.error_message = None
    task_run.updated_at = now
    task_run.completed_at = now
    db_session.flush()
    return task_run


def fail_task_run(
    db_session: Session,
    *,
    task_run_id: str,
    error_code: str,
    error_message: str,
    result_summary: str,
) -> TaskRun:
    task_run = db_session.get(TaskRun, task_run_id)
    if task_run is None:
        raise LookupError(task_run_id)

    now = _now()
    task_run.status = FAILED_STATUS
    task_run.assigned_employee_id = None
    task_run.result_summary = result_summary
    task_run.error_code = error_code
    task_run.error_message = error_message
    task_run.updated_at = now
    task_run.completed_at = now
    db_session.flush()
    return task_run
