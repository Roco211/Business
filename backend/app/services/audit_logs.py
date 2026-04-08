from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.ids import new_prefixed_id
from app.models import AuditLog, InventoryEvent, InventoryItem, Shop


class UnsupportedAuditScopeError(ValueError):
    pass


@dataclass(frozen=True)
class AuditLogListPage:
    items: list[AuditLog]


def list_audit_logs(
    db_session: Session,
    *,
    shop_id: str,
    scope: str,
    limit: int,
) -> AuditLogListPage:
    if scope != "inventory":
        raise UnsupportedAuditScopeError(scope)

    safe_limit = max(1, min(limit, 50))
    statement = (
        select(AuditLog)
        .where(
            AuditLog.shop_id == shop_id,
            AuditLog.scope == scope,
        )
        .order_by(AuditLog.created_at.desc(), AuditLog.audit_log_id.desc())
        .limit(safe_limit)
    )
    return AuditLogListPage(items=list(db_session.scalars(statement)))


def append_inventory_stock_in_audit_log(
    db_session: Session,
    *,
    shop_id: str,
    task_run_id: str,
    actor_id: str,
    confirmation_id: str,
    item: InventoryItem,
    inventory_event: InventoryEvent,
) -> AuditLog:
    log = AuditLog(
        audit_log_id=new_prefixed_id("audit"),
        shop_id=shop_id,
        scope="inventory",
        action="inventory.stock_in_confirmed",
        actor_type="owner",
        actor_id=actor_id,
        task_run_id=task_run_id,
        target_type="inventory_item",
        target_id=item.item_id,
        metadata_json={
            "confirmation_id": confirmation_id,
            "inventory_event_id": inventory_event.inventory_event_id,
            "event_type": inventory_event.event_type,
            "item_id": item.item_id,
            "item_name": item.name,
            "quantity_delta": float(inventory_event.quantity_delta),
            "quantity_after": float(inventory_event.quantity_after),
            "unit": item.default_unit,
            "price": float(inventory_event.price or 0),
            "source": inventory_event.source,
        },
        created_at=datetime.now(UTC).replace(tzinfo=None),
    )
    db_session.add(log)
    db_session.flush()
    return log


def append_inventory_receipt_stock_in_audit_log(
    db_session: Session,
    *,
    shop_id: str,
    task_run_id: str,
    actor_id: str,
    confirmation_id: str,
    ocr_document_id: str,
    line_id: str,
    item: InventoryItem,
    inventory_event: InventoryEvent,
) -> AuditLog:
    log = AuditLog(
        audit_log_id=new_prefixed_id("audit"),
        shop_id=shop_id,
        scope="inventory",
        action="inventory.receipt_stock_in_confirmed",
        actor_type="owner",
        actor_id=actor_id,
        task_run_id=task_run_id,
        target_type="inventory_item",
        target_id=item.item_id,
        metadata_json={
            "confirmation_id": confirmation_id,
            "ocr_document_id": ocr_document_id,
            "inventory_event_id": inventory_event.inventory_event_id,
            "line_id": line_id,
            "event_type": inventory_event.event_type,
            "item_id": item.item_id,
            "item_name": item.name,
            "quantity_delta": float(inventory_event.quantity_delta),
            "quantity_after": float(inventory_event.quantity_after),
            "unit": item.default_unit,
            "price": float(inventory_event.price or 0),
            "source": inventory_event.source,
        },
        created_at=datetime.now(UTC).replace(tzinfo=None),
    )
    db_session.add(log)
    db_session.flush()
    return log


def append_inventory_correction_audit_log(
    db_session: Session,
    *,
    item: InventoryItem,
    inventory_event: InventoryEvent,
    previous_quantity: float,
    actor_id: str,
    reason: str,
) -> AuditLog:
    log = AuditLog(
        audit_log_id=new_prefixed_id("audit"),
        shop_id=item.shop_id,
        scope="inventory",
        action="inventory.correction_submitted",
        actor_type="owner",
        actor_id=actor_id,
        task_run_id=None,
        target_type="inventory_item",
        target_id=item.item_id,
        metadata_json={
            "inventory_event_id": inventory_event.inventory_event_id,
            "event_type": inventory_event.event_type,
            "item_id": item.item_id,
            "item_name": item.name,
            "previous_quantity": previous_quantity,
            "corrected_quantity": float(inventory_event.quantity_after),
            "quantity_delta": float(inventory_event.quantity_delta),
            "unit": item.default_unit,
            "price": float(inventory_event.price or 0),
            "reason": reason,
            "source": inventory_event.source,
        },
        created_at=datetime.now(UTC).replace(tzinfo=None),
    )
    db_session.add(log)
    db_session.flush()
    return log


def append_inventory_stock_out_audit_log(
    db_session: Session,
    *,
    item: InventoryItem,
    inventory_event: InventoryEvent,
    previous_quantity: float,
    actor_id: str,
    reason: str,
    task_run_id: str | None = None,
    confirmation_id: str | None = None,
) -> AuditLog:
    metadata_json = {
        "inventory_event_id": inventory_event.inventory_event_id,
        "event_type": inventory_event.event_type,
        "item_id": item.item_id,
        "item_name": item.name,
        "previous_quantity": previous_quantity,
        "quantity_delta": float(inventory_event.quantity_delta),
        "quantity_after": float(inventory_event.quantity_after),
        "unit": item.default_unit,
        "reason": reason,
        "source": inventory_event.source,
    }
    if confirmation_id is not None:
        metadata_json["confirmation_id"] = confirmation_id

    log = AuditLog(
        audit_log_id=new_prefixed_id("audit"),
        shop_id=item.shop_id,
        scope="inventory",
        action="inventory.stock_out_submitted",
        actor_type="owner",
        actor_id=actor_id,
        task_run_id=task_run_id,
        target_type="inventory_item",
        target_id=item.item_id,
        metadata_json=metadata_json,
        created_at=datetime.now(UTC).replace(tzinfo=None),
    )
    db_session.add(log)
    db_session.flush()
    return log


def append_shop_rules_trial_calibration_audit_log(
    db_session: Session,
    *,
    shop: Shop,
    actor_id: str,
    artifact_id: str,
    trial_provider_profile: str,
    before: dict[str, object],
    after: dict[str, object],
) -> AuditLog:
    log = AuditLog(
        audit_log_id=new_prefixed_id("audit"),
        shop_id=shop.shop_id,
        scope="shop-rules",
        action="shop_rules.trial_calibration_applied",
        actor_type="owner",
        actor_id=actor_id,
        task_run_id=None,
        target_type="shop",
        target_id=shop.shop_id,
        metadata_json={
            "trial_provider_profile": trial_provider_profile,
            "artifact_id": artifact_id,
            "before": before,
            "after": after,
        },
        created_at=datetime.now(UTC).replace(tzinfo=None),
    )
    db_session.add(log)
    db_session.flush()
    return log


def append_pilot_cutover_transition_audit_log(
    db_session: Session,
    *,
    shop_id: str,
    actor_id: str,
    previous_cutover_mode: str,
    new_cutover_mode: str,
    trial_provider_profile: str,
    approved_calibration_artifact_id: str | None,
    note: str | None,
) -> AuditLog:
    log = AuditLog(
        audit_log_id=new_prefixed_id("audit"),
        shop_id=shop_id,
        scope="pilot",
        action="pilot.cutover_transition",
        actor_type="owner",
        actor_id=actor_id,
        task_run_id=None,
        target_type="shop",
        target_id=shop_id,
        metadata_json={
            "shop_id": shop_id,
            "previous_cutover_mode": previous_cutover_mode,
            "new_cutover_mode": new_cutover_mode,
            "actor_id": actor_id,
            "trial_provider_profile": trial_provider_profile,
            "approved_calibration_artifact_id": approved_calibration_artifact_id,
            "note": note,
        },
        created_at=datetime.now(UTC).replace(tzinfo=None),
    )
    db_session.add(log)
    db_session.flush()
    return log


def append_pilot_runtime_telemetry_audit_log(
    db_session: Session,
    *,
    shop_id: str,
    task_run_id: str,
    task_type: str | None,
    capability: str,
    provider_mode: str,
    provider_label: str,
    used_fallback: bool,
    recognized_confidence: float | None,
    low_confidence: bool,
    outcome: str,
    error_code: str | None,
    trial_provider_profile: str,
    cutover_mode: str | None = None,
    guardrail_status: str | None = None,
    guardrail_reason: str | None = None,
    shadow_forced_confirmation: bool | None = None,
    guardrail_degraded: bool | None = None,
    guardrail_degraded_reasons: list[str] | None = None,
) -> AuditLog:
    metadata_json: dict[str, object] = {
        "task_type": task_type,
        "capability": capability,
        "provider_mode": provider_mode,
        "provider_label": provider_label,
        "used_fallback": used_fallback,
        "recognized_confidence": recognized_confidence,
        "low_confidence": low_confidence,
        "outcome": outcome,
        "error_code": error_code,
        "trial_provider_profile": trial_provider_profile,
    }
    if cutover_mode is not None:
        metadata_json["cutover_mode"] = cutover_mode
    if guardrail_status is not None:
        metadata_json["guardrail_status"] = guardrail_status
    if guardrail_reason is not None:
        metadata_json["guardrail_reason"] = guardrail_reason
    if shadow_forced_confirmation is not None:
        metadata_json["shadow_forced_confirmation"] = shadow_forced_confirmation
    if guardrail_degraded is not None:
        metadata_json["guardrail_degraded"] = guardrail_degraded
    if guardrail_degraded_reasons is not None:
        metadata_json["guardrail_degraded_reasons"] = list(guardrail_degraded_reasons)

    log = AuditLog(
        audit_log_id=new_prefixed_id("audit"),
        shop_id=shop_id,
        scope="pilot",
        action="runtime.provider_telemetry",
        actor_type="system",
        actor_id="runtime_system",
        task_run_id=task_run_id,
        target_type="task_run",
        target_id=task_run_id,
        metadata_json=metadata_json,
        created_at=datetime.now(UTC).replace(tzinfo=None),
    )
    db_session.add(log)
    db_session.flush()
    return log


def append_pilot_task_diagnostic_replayed_audit_log(
    db_session: Session,
    *,
    shop_id: str,
    actor_id: str,
    task_run_id: str,
    idempotency_key: str | None,
    trial_provider_profile: str,
    incident_id: str | None,
    reasons: list[str],
) -> AuditLog:
    log = AuditLog(
        audit_log_id=new_prefixed_id("audit"),
        shop_id=shop_id,
        scope="pilot",
        action="pilot.task_diagnostic_replayed",
        actor_type="owner",
        actor_id=actor_id,
        task_run_id=task_run_id,
        target_type="task_run",
        target_id=task_run_id,
        metadata_json={
            "task_run_id": task_run_id,
            "idempotency_key": idempotency_key,
            "trial_provider_profile": trial_provider_profile,
            "incident_id": incident_id,
            "reasons": list(reasons),
        },
        created_at=datetime.now(UTC).replace(tzinfo=None),
    )
    db_session.add(log)
    db_session.flush()
    return log


def append_pilot_operator_view_backfill_audit_log(
    db_session: Session,
    *,
    shop_id: str,
    actor_id: str,
    view: str,
    hours: int,
    limit: int,
    idempotency_key: str | None,
    trial_provider_profile: str,
    total_incidents: int,
    current_cutover_mode: str,
    affected_task_ids: list[str],
) -> AuditLog:
    log = AuditLog(
        audit_log_id=new_prefixed_id("audit"),
        shop_id=shop_id,
        scope="pilot",
        action="pilot.operator_view_backfilled",
        actor_type="owner",
        actor_id=actor_id,
        task_run_id=None,
        target_type="operator_view",
        target_id=view,
        metadata_json={
            "view": view,
            "hours": hours,
            "limit": limit,
            "idempotency_key": idempotency_key,
            "trial_provider_profile": trial_provider_profile,
            "total_incidents": total_incidents,
            "current_cutover_mode": current_cutover_mode,
            "affected_task_ids": list(affected_task_ids),
        },
        created_at=datetime.now(UTC).replace(tzinfo=None),
    )
    db_session.add(log)
    db_session.flush()
    return log


def append_pilot_shift_bundle_export_audit_log(
    db_session: Session,
    *,
    shop_id: str,
    actor_id: str,
    bundle_id: str,
    manifest_path: str,
    overall_status: str,
    degraded_reasons: list[str],
    trial_provider_profile: str,
    cutover_mode: str | None,
    hours: int | None,
) -> AuditLog:
    log = AuditLog(
        audit_log_id=new_prefixed_id("audit"),
        shop_id=shop_id,
        scope="pilot",
        action="pilot.shift_bundle_exported",
        actor_type="owner",
        actor_id=actor_id,
        task_run_id=None,
        target_type="shift_bundle",
        target_id=bundle_id,
        metadata_json={
            "bundle_id": bundle_id,
            "manifest_path": manifest_path,
            "overall_status": overall_status,
            "degraded_reasons": list(degraded_reasons),
            "trial_provider_profile": trial_provider_profile,
            "cutover_mode": cutover_mode,
            "hours": hours,
        },
        created_at=datetime.now(UTC).replace(tzinfo=None),
    )
    db_session.add(log)
    db_session.flush()
    return log
