from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models import TaskRun
from app.runtime.context import build_runtime_turn_context
from app.runtime.router import RuntimeRouteBlocked, route_runtime_input
from app.runtime.summarizer import summarize_completed_task, summarize_failed_task
from app.services.runtime_messages import write_runtime_message
from app.services.task_runs import (
    CREATED_STATUS,
    PENDING_CLASSIFICATION_TASK_TYPE,
    PROCESSING_STATUS,
    claim_task_run_for_runtime,
    complete_task_run,
    fail_task_run,
)


@dataclass(frozen=True)
class RuntimeProcessResult:
    status: str
    task_run_id: str
    task_type: str | None
    error_code: str | None


def _build_failed_result(
    db_session: Session,
    *,
    task_run_id: str,
    session_id: str,
    error_code: str,
    error_message: str,
) -> RuntimeProcessResult:
    result_summary, runtime_text = summarize_failed_task(
        error_code=error_code,
        error_message=error_message,
    )
    fail_task_run(
        db_session,
        task_run_id=task_run_id,
        error_code=error_code,
        error_message=error_message,
        result_summary=result_summary,
    )
    try:
        write_runtime_message(
            db_session,
            session_id=session_id,
            task_run_id=task_run_id,
            text=runtime_text,
        )
    except LookupError:
        pass
    db_session.commit()
    return RuntimeProcessResult(
        status="failed",
        task_run_id=task_run_id,
        task_type=None,
        error_code=error_code,
    )


def _recover_unexpected_failure(
    db_session: Session,
    *,
    task_run_id: str,
    session_id: str,
    error_message: str,
) -> RuntimeProcessResult:
    db_session.rollback()
    current_task_run = db_session.get(TaskRun, task_run_id)
    if current_task_run is None:
        raise LookupError(task_run_id)
    if (
        current_task_run.status == CREATED_STATUS
        and current_task_run.task_type == PENDING_CLASSIFICATION_TASK_TYPE
    ):
        recovery_claim = claim_task_run_for_runtime(db_session, task_run_id=task_run_id)
        current_task_run = recovery_claim.task_run
    if current_task_run.status == PROCESSING_STATUS:
        return _build_failed_result(
            db_session,
            task_run_id=task_run_id,
            session_id=session_id,
            error_code="runtime_processing_error",
            error_message=error_message,
        )
    return RuntimeProcessResult(
        status=current_task_run.status,
        task_run_id=current_task_run.task_run_id,
        task_type=current_task_run.task_type,
        error_code=current_task_run.error_code,
    )


def process_task_run(db_session: Session, task_run_id: str) -> RuntimeProcessResult:
    claim = claim_task_run_for_runtime(db_session, task_run_id=task_run_id)
    if not claim.changed:
        return RuntimeProcessResult(
            status="skipped",
            task_run_id=claim.task_run.task_run_id,
            task_type=claim.task_run.task_type,
            error_code=claim.task_run.error_code,
        )

    try:
        context = build_runtime_turn_context(db_session, task_run_id=task_run_id)
        decision = route_runtime_input(context)
        result_summary, runtime_text = summarize_completed_task(
            task_type=decision.task_type,
            transcript=decision.transcript,
        )
        complete_task_run(
            db_session,
            task_run_id=task_run_id,
            task_type=decision.task_type,
            assigned_employee_id=decision.assigned_employee_id,
            result_summary=result_summary,
        )
        write_runtime_message(
            db_session,
            session_id=context.session_id,
            task_run_id=task_run_id,
            text=runtime_text,
        )
        db_session.commit()
        return RuntimeProcessResult(
            status="completed",
            task_run_id=task_run_id,
            task_type=decision.task_type,
            error_code=None,
        )
    except RuntimeRouteBlocked as exc:
        return _build_failed_result(
            db_session,
            task_run_id=task_run_id,
            session_id=claim.task_run.session_id,
            error_code=exc.error_code,
            error_message=exc.error_message,
        )
    except Exception as exc:
        return _recover_unexpected_failure(
            db_session,
            task_run_id=task_run_id,
            session_id=claim.task_run.session_id,
            error_message=f"Runtime processing failed: {exc}",
        )
