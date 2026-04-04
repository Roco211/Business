from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.core.ids import new_prefixed_id
from app.models.task_run import TaskRun

PENDING_CLASSIFICATION_TASK_TYPE = "pending-classification"
CREATED_STATUS = "created"


def create_initial_task_run(
    db_session: Session,
    *,
    session_id: str,
    source_message_id: str,
) -> TaskRun:
    now = datetime.now(UTC).replace(tzinfo=None)
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
