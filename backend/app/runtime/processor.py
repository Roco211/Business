from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Confirmation, TaskRun
from app.runtime.context import build_runtime_turn_context
from app.runtime.policy import evaluate_runtime_policy
from app.runtime.router import RuntimeRouteBlocked, route_runtime_input
from app.runtime.summarizer import summarize_completed_task, summarize_failed_task
from app.services.confirmations import create_pending_confirmation
from app.services.runtime_messages import write_runtime_message
from app.services.task_runs import (
    CREATED_STATUS,
    PENDING_CLASSIFICATION_TASK_TYPE,
    claim_task_run_for_runtime,
    complete_task_run,
    fail_task_run,
    mark_task_run_awaiting_confirmation,
)


@dataclass(frozen=True)
class RuntimeProcessResult:
    status: str
    task_run_id: str
    task_type: str | None
    error_code: str | None


def _build_confirmation_fields(transcript: str | None) -> dict[str, object]:
    return {
        "summary": "Please confirm the stock-in details before commit.",
        "transcript": (transcript or "").strip(),
        "draft_fields": {
            "item_name": None,
            "quantity": None,
            "unit": None,
            "price": None,
        },
        "required_fields": ["item_name", "quantity", "unit", "price"],
    }


def _load_pending_confirmation(
    db_session: Session,
    *,
    confirmation_id: str,
) -> Confirmation:
    confirmation = db_session.scalar(
        select(Confirmation)
        .where(
            Confirmation.confirmation_id == confirmation_id,
            Confirmation.status == "pending",
        )
        .execution_options(populate_existing=True)
    )
    if confirmation is None:
        raise ValueError(f"Confirmation {confirmation_id} is not pending.")
    return confirmation


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
    if current_task_run.status != CREATED_STATUS or current_task_run.task_type != PENDING_CLASSIFICATION_TASK_TYPE:
        return RuntimeProcessResult(
            status="skipped",
            task_run_id=current_task_run.task_run_id,
            task_type=current_task_run.task_type,
            error_code=current_task_run.error_code,
        )

    recovery_claim = claim_task_run_for_runtime(db_session, task_run_id=task_run_id)
    if not recovery_claim.changed:
        return RuntimeProcessResult(
            status="skipped",
            task_run_id=recovery_claim.task_run.task_run_id,
            task_type=recovery_claim.task_run.task_type,
            error_code=recovery_claim.task_run.error_code,
        )

    return _build_failed_result(
        db_session,
        task_run_id=task_run_id,
        session_id=session_id,
        error_code="runtime_processing_error",
        error_message=error_message,
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
        policy = evaluate_runtime_policy(task_type=decision.task_type)
        if policy.outcome == "require-confirmation":
            if context.pending_confirmation_id is not None:
                _load_pending_confirmation(
                    db_session,
                    confirmation_id=context.pending_confirmation_id,
                )
            else:
                create_pending_confirmation(
                    db_session,
                    task_run_id=task_run_id,
                    confirmation_type=policy.confirmation_type or "low-confidence-recognition",
                    fields=_build_confirmation_fields(decision.transcript),
                    requested_by_employee_id=decision.assigned_employee_id,
                )
            mark_task_run_awaiting_confirmation(
                db_session,
                task_run_id=task_run_id,
                task_type=decision.task_type,
                assigned_employee_id=decision.assigned_employee_id,
                result_summary="Awaiting owner confirmation for stock-in details.",
            )
            write_runtime_message(
                db_session,
                session_id=context.session_id,
                task_run_id=task_run_id,
                text="Mock runtime: please confirm the stock-in details before commit.",
            )
            db_session.commit()
            return RuntimeProcessResult(
                status="awaiting-confirmation",
                task_run_id=task_run_id,
                task_type=decision.task_type,
                error_code=None,
            )

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
