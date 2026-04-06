from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import Confirmation, InventoryItem, OcrDocument, TaskRun
from app.runtime.context import build_runtime_turn_context
from app.runtime.guardrails import evaluate_pilot_cutover_guardrail
from app.runtime.policy import PolicyDecision, evaluate_runtime_policy
from app.runtime.router import RuntimeRouteBlocked, route_runtime_input
from app.runtime.summarizer import summarize_completed_task, summarize_failed_task
from app.runtime.types import RuntimeRouteDecision
from app.services.audit_logs import append_pilot_runtime_telemetry_audit_log
from app.services.confirmations import create_pending_confirmation
from app.services.ocr_documents import create_ocr_document
from app.services.ocr_types import OcrProviderError
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


def _default_confirmation_type_for_task(task_type: str) -> str:
    if task_type == "voice-stock-out":
        return "stock-out"
    if task_type == "receipt-ocr":
        return "receipt-stock-in-batch"
    return "low-confidence-recognition"


def _with_guardrail_telemetry_payload(
    *,
    payload: dict[str, object],
    task_type: str,
    guardrail_telemetry: dict[str, object],
) -> dict[str, object]:
    enriched_payload = dict(payload)
    if "capability" not in enriched_payload:
        enriched_payload.update(
            {
                "task_type": task_type,
                "capability": "guardrail",
                "provider_mode": "guardrail",
                "provider_label": "pilot-cutover",
                "used_fallback": False,
                "recognized_confidence": None,
                "low_confidence": False,
            }
        )
    enriched_payload.update(guardrail_telemetry)
    return enriched_payload


def _build_ocr_provider_payload(
    *,
    payload: dict[str, object],
    provider_name: str,
    used_fallback: bool,
    low_confidence_fields: list[str],
) -> dict[str, object]:
    settings = get_settings()
    enriched_payload = dict(payload)
    enriched_payload.update(
        {
            "capability": "ocr",
            "provider_mode": settings.ocr_provider.strip().lower() or "mock",
            "provider_label": settings.ocr_provider_label.strip() or provider_name or "mock",
            "provider_name": provider_name,
            "used_fallback": used_fallback,
            "low_confidence_fields": list(low_confidence_fields),
        }
    )
    return enriched_payload


def _default_provider_telemetry(context_input_kind: str) -> tuple[str, str, str]:
    settings = get_settings()
    if context_input_kind == "voice":
        provider_mode = settings.asr_provider.strip().lower() or "mock"
        provider_label = settings.asr_provider_label.strip() or provider_mode
        return "asr", provider_mode, provider_label
    if context_input_kind == "image":
        provider_mode = settings.vision_provider.strip().lower() or "mock"
        provider_label = settings.vision_provider_label.strip() or provider_mode
        return "vision", provider_mode, provider_label
    provider_mode = settings.ocr_provider.strip().lower() or "mock"
    provider_label = settings.ocr_provider_label.strip() or provider_mode
    return "ocr", provider_mode, provider_label


def _build_provider_telemetry_record(
    *,
    context_input_kind: str,
    task_type: str | None,
    payload: dict[str, object] | None,
) -> dict[str, object] | None:
    raw_payload = dict(payload or {})
    capability, provider_mode, provider_label = _default_provider_telemetry(context_input_kind)
    capability = str(raw_payload.get("capability") or capability)
    provider_mode = str(raw_payload.get("provider_mode") or provider_mode)
    provider_label = str(
        raw_payload.get("provider_label")
        or raw_payload.get("provider_name")
        or provider_label
    )
    recognized_confidence_raw = raw_payload.get("recognized_confidence", raw_payload.get("confidence"))
    recognized_confidence = (
        float(recognized_confidence_raw)
        if isinstance(recognized_confidence_raw, (int, float))
        else None
    )
    used_fallback_raw = raw_payload.get("used_fallback")
    if used_fallback_raw is None and capability == "ocr":
        provider_name = str(raw_payload.get("provider_name") or "").strip().lower()
        used_fallback = provider_mode != "mock" and provider_name == "mock"
    else:
        used_fallback = bool(used_fallback_raw)
    low_confidence_raw = raw_payload.get("low_confidence")
    if low_confidence_raw is None and capability == "ocr":
        low_confidence = bool(raw_payload.get("low_confidence_fields"))
    else:
        low_confidence = bool(low_confidence_raw)
    if context_input_kind not in {"voice", "image", "receipt-image"} and "capability" not in raw_payload:
        return None
    record: dict[str, object] = {
        "task_type": task_type or raw_payload.get("task_type"),
        "capability": capability,
        "provider_mode": provider_mode,
        "provider_label": provider_label,
        "used_fallback": used_fallback,
        "recognized_confidence": recognized_confidence,
        "low_confidence": low_confidence,
    }
    if "cutover_mode" in raw_payload:
        cutover_mode_raw = raw_payload.get("cutover_mode")
        record["cutover_mode"] = (
            str(cutover_mode_raw).strip().lower()
            if cutover_mode_raw is not None and str(cutover_mode_raw).strip()
            else None
        )
    if "guardrail_status" in raw_payload:
        guardrail_status_raw = raw_payload.get("guardrail_status")
        record["guardrail_status"] = (
            str(guardrail_status_raw).strip()
            if guardrail_status_raw is not None and str(guardrail_status_raw).strip()
            else None
        )
    if "guardrail_reason" in raw_payload:
        guardrail_reason_raw = raw_payload.get("guardrail_reason")
        record["guardrail_reason"] = (
            str(guardrail_reason_raw).strip()
            if guardrail_reason_raw is not None and str(guardrail_reason_raw).strip()
            else None
        )
    if "shadow_forced_confirmation" in raw_payload:
        record["shadow_forced_confirmation"] = bool(raw_payload.get("shadow_forced_confirmation"))
    if "guardrail_degraded" in raw_payload:
        record["guardrail_degraded"] = bool(raw_payload.get("guardrail_degraded"))
    if "guardrail_degraded_reasons" in raw_payload:
        degraded_reasons_raw = raw_payload.get("guardrail_degraded_reasons")
        degraded_reasons = (
            [str(reason).strip() for reason in degraded_reasons_raw if str(reason).strip()]
            if isinstance(degraded_reasons_raw, list)
            else []
        )
        record["guardrail_degraded_reasons"] = degraded_reasons
    return record


def _append_provider_telemetry(
    db_session: Session,
    *,
    shop_id: str,
    task_run_id: str,
    outcome: str,
    error_code: str | None,
    provider_telemetry: dict[str, object] | None,
) -> None:
    if provider_telemetry is None:
        return

    settings = get_settings()
    append_pilot_runtime_telemetry_audit_log(
        db_session,
        shop_id=shop_id,
        task_run_id=task_run_id,
        task_type=(
            str(provider_telemetry.get("task_type"))
            if provider_telemetry.get("task_type") is not None
            else None
        ),
        capability=str(provider_telemetry["capability"]),
        provider_mode=str(provider_telemetry["provider_mode"]),
        provider_label=str(provider_telemetry["provider_label"]),
        used_fallback=bool(provider_telemetry["used_fallback"]),
        recognized_confidence=(
            float(provider_telemetry["recognized_confidence"])
            if provider_telemetry.get("recognized_confidence") is not None
            else None
        ),
        low_confidence=bool(provider_telemetry["low_confidence"]),
        outcome=outcome,
        error_code=error_code,
        trial_provider_profile=settings.trial_provider_profile.strip(),
        cutover_mode=(
            str(provider_telemetry.get("cutover_mode"))
            if provider_telemetry.get("cutover_mode") is not None
            else None
        ),
        guardrail_status=(
            str(provider_telemetry.get("guardrail_status"))
            if provider_telemetry.get("guardrail_status") is not None
            else None
        ),
        guardrail_reason=(
            str(provider_telemetry.get("guardrail_reason"))
            if provider_telemetry.get("guardrail_reason") is not None
            else None
        ),
        shadow_forced_confirmation=(
            bool(provider_telemetry.get("shadow_forced_confirmation"))
            if "shadow_forced_confirmation" in provider_telemetry
            else None
        ),
        guardrail_degraded=(
            bool(provider_telemetry.get("guardrail_degraded"))
            if "guardrail_degraded" in provider_telemetry
            else None
        ),
        guardrail_degraded_reasons=(
            [
                str(reason)
                for reason in provider_telemetry.get("guardrail_degraded_reasons", [])
                if str(reason).strip()
            ]
            if "guardrail_degraded_reasons" in provider_telemetry
            else None
        ),
    )


def _has_provider_telemetry_payload(payload: dict[str, object] | None) -> bool:
    if payload is None:
        return False
    return any(
        key in payload
        for key in (
            "capability",
            "provider_name",
            "provider_label",
            "provider_mode",
            "used_fallback",
            "recognized_confidence",
            "confidence",
            "low_confidence",
            "low_confidence_fields",
            "cutover_mode",
            "guardrail_status",
        )
    )


def _build_confirmation_fields(
    *,
    task_type: str,
    transcript: str | None,
    payload: dict[str, object],
    ocr_document: OcrDocument | None = None,
) -> dict[str, object]:
    if task_type == "photo-stock-in":
        return {
            "summary": f"Please confirm the stock-in details for {payload.get('item_name') or 'the recognized item'}.",
            "transcript": (transcript or "").strip(),
            "draft_fields": {
                "item_name": payload.get("item_name"),
                "quantity": None,
                "unit": payload.get("packaging_hint"),
                "price": None,
            },
            "required_fields": ["item_name", "quantity", "unit", "price"],
            "image_media_id": payload.get("image_media_id"),
            "recognized_confidence": payload.get("confidence"),
            "provider_name": payload.get("provider_name"),
        }
    if task_type == "voice-stock-out":
        return {
            "summary": "Please confirm the stock-out details before commit.",
            "transcript": (transcript or "").strip(),
            "draft_fields": {
                "item_id": None,
                "item_name": None,
                "stock_out_quantity": None,
                "unit": None,
                "reason": "stock out via chat",
            },
            "required_fields": ["item_name", "stock_out_quantity", "reason"],
        }
    if task_type == "receipt-ocr":
        extracted_fields = ocr_document.extracted_fields if ocr_document is not None else {}
        raw_items = extracted_fields.get("items") if isinstance(extracted_fields, dict) else []
        draft_items = []
        if isinstance(raw_items, list):
            for index, raw_item in enumerate(raw_items, start=1):
                if not isinstance(raw_item, dict):
                    continue
                draft_items.append(
                    {
                        "line_id": f"line_{index}",
                        "item_id": raw_item.get("item_id"),
                        "item_name": raw_item.get("name"),
                        "quantity": raw_item.get("quantity"),
                        "unit": raw_item.get("unit"),
                        "price": raw_item.get("price"),
                    }
                )
        return {
            "summary": "Please confirm the receipt line items before committing inventory.",
            "transcript": (transcript or "").strip(),
            "ocr_document_id": ocr_document.ocr_document_id if ocr_document is not None else None,
            "document_type": ocr_document.document_type if ocr_document is not None else payload.get("document_type"),
            "provider_name": ocr_document.provider_name if ocr_document is not None else payload.get("provider_name"),
            "total_amount": extracted_fields.get("total_amount") if isinstance(extracted_fields, dict) else None,
            "low_confidence_fields": list(ocr_document.low_confidence_fields) if ocr_document is not None else [],
            "draft_items": draft_items,
            "required_item_fields": ["item_name", "quantity", "unit", "price"],
        }
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
    shop_id: str | None,
    task_run_id: str,
    session_id: str,
    error_code: str,
    error_message: str,
    provider_telemetry: dict[str, object] | None = None,
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
    if shop_id is not None:
        _append_provider_telemetry(
            db_session,
            shop_id=shop_id,
            task_run_id=task_run_id,
            outcome="failed",
            error_code=error_code,
            provider_telemetry=provider_telemetry,
        )
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
    shop_id: str | None,
    task_run_id: str,
    session_id: str,
    error_message: str,
    provider_telemetry: dict[str, object] | None = None,
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
        shop_id=shop_id,
        task_run_id=task_run_id,
        session_id=session_id,
        error_code="runtime_processing_error",
        error_message=error_message,
        provider_telemetry=provider_telemetry,
    )


def _recover_ocr_provider_failure(
    db_session: Session,
    *,
    shop_id: str | None,
    task_run_id: str,
    session_id: str,
    error_code: str,
    error_message: str,
    provider_telemetry: dict[str, object] | None = None,
) -> RuntimeProcessResult:
    # Preserve structured provider errors (for example ocr_unavailable) instead of
    # collapsing them into runtime_processing_error.
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
        shop_id=shop_id,
        task_run_id=task_run_id,
        session_id=session_id,
        error_code=error_code,
        error_message=error_message,
        provider_telemetry=provider_telemetry,
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

    context = None
    decision = None
    try:
        settings = get_settings()
        context = build_runtime_turn_context(db_session, task_run_id=task_run_id)
        decision = route_runtime_input(context)
        guardrail_decision = evaluate_pilot_cutover_guardrail(
            db_session,
            settings=settings,
            shop_id=context.shop_id,
            task_type=decision.task_type,
        )
        if guardrail_decision.should_block:
            guardrail_payload = _with_guardrail_telemetry_payload(
                payload=decision.payload,
                task_type=decision.task_type,
                guardrail_telemetry=guardrail_decision.telemetry_fields(),
            )
            return _build_failed_result(
                db_session,
                shop_id=context.shop_id,
                task_run_id=task_run_id,
                session_id=claim.task_run.session_id,
                error_code=guardrail_decision.block_error_code or "pilot_cutover_closed",
                error_message=(
                    "Pilot cutover is closed for write-intent runtime tasks. "
                    "Move to shadow/open mode before retrying."
                ),
                provider_telemetry=_build_provider_telemetry_record(
                    context_input_kind=context.input_kind,
                    task_type=decision.task_type,
                    payload=guardrail_payload,
                ),
            )

        policy = evaluate_runtime_policy(task_type=decision.task_type)
        provider_payload = dict(decision.payload)
        if guardrail_decision.should_force_confirmation:
            provider_payload = _with_guardrail_telemetry_payload(
                payload=provider_payload,
                task_type=decision.task_type,
                guardrail_telemetry=guardrail_decision.telemetry_fields(),
            )
            decision = RuntimeRouteDecision(
                task_type=decision.task_type,
                assigned_employee_id=decision.assigned_employee_id,
                transcript=decision.transcript,
                payload=provider_payload,
            )
            policy = PolicyDecision(
                outcome="require-confirmation",
                confirmation_type=policy.confirmation_type or _default_confirmation_type_for_task(decision.task_type),
            )

        if policy.outcome == "require-confirmation":
            ocr_document: OcrDocument | None = None
            if decision.task_type == "receipt-ocr" and context.pending_confirmation_id is None:
                ocr_result = create_ocr_document(
                    db_session,
                    shop_id=context.shop_id,
                    media_id=context.media_ids[0],
                    document_type=str(decision.payload.get("document_type") or "purchase-receipt"),
                    task_run_id=task_run_id,
                )
                ocr_document = ocr_result.ocr_document
                provider_payload = _build_ocr_provider_payload(
                    payload=provider_payload,
                    provider_name=ocr_result.provider_name,
                    used_fallback=ocr_result.used_fallback,
                    low_confidence_fields=ocr_result.low_confidence_fields,
                )
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
                    fields=_build_confirmation_fields(
                        task_type=decision.task_type,
                        transcript=decision.transcript,
                        payload=provider_payload,
                        ocr_document=ocr_document,
                    ),
                    requested_by_employee_id=decision.assigned_employee_id,
                )
            mark_task_run_awaiting_confirmation(
                db_session,
                task_run_id=task_run_id,
                task_type=decision.task_type,
                assigned_employee_id=decision.assigned_employee_id,
                result_summary=(
                    "Awaiting owner confirmation for receipt line items."
                    if decision.task_type == "receipt-ocr"
                    else "Awaiting owner confirmation for stock-out details."
                    if decision.task_type == "voice-stock-out"
                    else "Awaiting owner confirmation for stock-in details."
                ),
            )
            write_runtime_message(
                db_session,
                session_id=context.session_id,
                task_run_id=task_run_id,
                text=(
                    "Mock runtime: please confirm the receipt line items before committing inventory."
                    if decision.task_type == "receipt-ocr"
                    else "Mock runtime: please confirm the stock-out details before commit."
                    if decision.task_type == "voice-stock-out"
                    else "Mock runtime: please confirm the stock-in details before commit."
                ),
            )
            _append_provider_telemetry(
                db_session,
                shop_id=context.shop_id,
                task_run_id=task_run_id,
                outcome="awaiting-confirmation",
                error_code=None,
                provider_telemetry=_build_provider_telemetry_record(
                    context_input_kind=context.input_kind,
                    task_type=decision.task_type,
                    payload=provider_payload,
                ),
            )
            db_session.commit()
            return RuntimeProcessResult(
                status="awaiting-confirmation",
                task_run_id=task_run_id,
                task_type=decision.task_type,
                error_code=None,
            )

        completed_payload = dict(decision.payload)
        if decision.task_type == "photo-stock-query":
            item_name = str(completed_payload.get("item_name") or "").strip()
            item = (
                db_session.scalar(
                    select(InventoryItem).where(
                        InventoryItem.shop_id == context.shop_id,
                        InventoryItem.name == item_name,
                        InventoryItem.is_active.is_(True),
                    )
                )
                if item_name
                else None
            )
            if item is None:
                completed_payload.update(
                    {
                        "item_id": None,
                        "stock": None,
                        "unit": None,
                        "is_low_stock": None,
                    }
                )
            else:
                is_low_stock = (
                    item.low_stock_threshold is not None
                    and item.current_stock <= item.low_stock_threshold
                )
                completed_payload.update(
                    {
                        "item_id": item.item_id,
                        "stock": item.current_stock,
                        "unit": item.default_unit,
                        "is_low_stock": is_low_stock,
                    }
                )
        if decision.task_type == "receipt-ocr":
            ocr_result = create_ocr_document(
                db_session,
                shop_id=context.shop_id,
                media_id=context.media_ids[0],
                document_type=str(decision.payload.get("document_type") or "purchase-receipt"),
                task_run_id=task_run_id,
            )
            ocr_document = ocr_result.ocr_document
            completed_payload.update(
                _build_ocr_provider_payload(
                    payload={
                        "ocr_document_id": ocr_document.ocr_document_id,
                        "document_type": ocr_document.document_type,
                        "provider_name": ocr_result.provider_name,
                        "total_amount": (ocr_document.extracted_fields or {}).get("total_amount"),
                        "low_confidence_fields": list(ocr_result.low_confidence_fields),
                    },
                    provider_name=ocr_result.provider_name,
                    used_fallback=ocr_result.used_fallback,
                    low_confidence_fields=ocr_result.low_confidence_fields,
                )
            )
            completed_payload.update(
                {
                    "ocr_document_id": ocr_document.ocr_document_id,
                    "document_type": ocr_document.document_type,
                    "provider_name": ocr_result.provider_name,
                    "total_amount": (ocr_document.extracted_fields or {}).get("total_amount"),
                    "low_confidence_fields": list(ocr_result.low_confidence_fields),
                    "used_fallback": ocr_result.used_fallback,
                }
            )

        if completed_payload:
            result_summary, runtime_text = summarize_completed_task(
                task_type=decision.task_type,
                transcript=decision.transcript,
                payload=completed_payload,
            )
        else:
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
        _append_provider_telemetry(
            db_session,
            shop_id=context.shop_id,
            task_run_id=task_run_id,
            outcome="completed",
            error_code=None,
            provider_telemetry=_build_provider_telemetry_record(
                context_input_kind=context.input_kind,
                task_type=decision.task_type,
                payload=completed_payload if completed_payload else decision.payload,
            ),
        )
        db_session.commit()
        return RuntimeProcessResult(
            status="completed",
            task_run_id=task_run_id,
            task_type=decision.task_type,
            error_code=None,
        )
    except RuntimeRouteBlocked as exc:
        telemetry_payload = getattr(exc, "telemetry", None)
        return _build_failed_result(
            db_session,
            shop_id=context.shop_id if context is not None else None,
            task_run_id=task_run_id,
            session_id=claim.task_run.session_id,
            error_code=exc.error_code,
            error_message=exc.error_message,
            provider_telemetry=_build_provider_telemetry_record(
                context_input_kind=context.input_kind,
                task_type=None,
                payload=telemetry_payload,
            )
            if context is not None and telemetry_payload is not None
            else None,
        )
    except OcrProviderError as exc:
        return _recover_ocr_provider_failure(
            db_session,
            shop_id=context.shop_id if context is not None else None,
            task_run_id=task_run_id,
            session_id=claim.task_run.session_id,
            error_code=exc.code,
            error_message=exc.message,
            provider_telemetry=(
                _build_provider_telemetry_record(
                    context_input_kind=context.input_kind,
                    task_type=decision.task_type if decision is not None else "receipt-ocr",
                    payload={"capability": "ocr"},
                )
                if context is not None
                else None
            ),
        )
    except Exception as exc:
        return _recover_unexpected_failure(
            db_session,
            shop_id=context.shop_id if context is not None else None,
            task_run_id=task_run_id,
            session_id=claim.task_run.session_id,
            error_message=f"Runtime processing failed: {exc}",
            provider_telemetry=(
                _build_provider_telemetry_record(
                    context_input_kind=context.input_kind,
                    task_type=decision.task_type if decision is not None else None,
                    payload=decision.payload if decision is not None else None,
                )
                if context is not None
                and decision is not None
                and _has_provider_telemetry_payload(decision.payload)
                else None
            ),
        )
