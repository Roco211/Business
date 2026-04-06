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
) -> AuditLog:
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
        metadata_json={
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
        },
        created_at=datetime.now(UTC).replace(tzinfo=None),
    )
    db_session.add(log)
    db_session.flush()
    return log
