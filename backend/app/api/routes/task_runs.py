from fastapi import APIRouter, Depends, Header, status
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.contracts.common import DataEnvelope, ErrorBody, ErrorEnvelope
from app.contracts.task_run import TaskRunData
from app.db.session import get_db_session
from app.models import Confirmation, TaskRun

router = APIRouter(prefix="/api/v1/task-runs", tags=["task-runs"])


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
            error=ErrorBody(code="task_run_not_found", message="Task run not found", details=[])
        ).model_dump(),
    )


def _load_confirmation_id(db_session: Session, *, task_run_id: str) -> str | None:
    return db_session.scalar(
        select(Confirmation.confirmation_id).where(Confirmation.task_run_id == task_run_id)
    )


@router.get("/{task_run_id}", response_model=DataEnvelope[TaskRunData])
def get_task_run(
    task_run_id: str,
    authorization: str | None = Header(default=None),
    db_session: Session = Depends(get_db_session),
) -> DataEnvelope[TaskRunData] | JSONResponse:
    if authorization != "Bearer mock_owner_token":
        return _unauthorized()

    task_run = db_session.get(TaskRun, task_run_id)
    if task_run is None:
        return _not_found()

    return DataEnvelope(
        data=TaskRunData(
            task_run_id=task_run.task_run_id,
            session_id=task_run.session_id,
            source_message_id=task_run.source_message_id,
            task_type=task_run.task_type,
            status=task_run.status,
            assigned_employee_id=task_run.assigned_employee_id,
            result_summary=task_run.result_summary,
            error_code=task_run.error_code,
            error_message=task_run.error_message,
            confirmation_id=_load_confirmation_id(db_session, task_run_id=task_run.task_run_id),
            created_at=task_run.created_at,
            updated_at=task_run.updated_at,
            completed_at=task_run.completed_at,
        )
    )
