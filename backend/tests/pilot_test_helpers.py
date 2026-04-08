from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from app.core.ids import new_prefixed_id
from app.models import AuditLog, Confirmation, Message, SessionRecord, SessionStreamEvent, Shop, TaskRun
from conftest import auth_headers, login_and_get_token


def auth_owner_headers(client, monkeypatch=None) -> dict[str, str]:
    return auth_headers(login_and_get_token(client, monkeypatch))


def utc_now_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def create_shop_and_session(db_session, *, shop_id: str, session_id: str) -> SessionRecord:
    now = utc_now_naive()
    shop = Shop(
        shop_id=shop_id,
        name=f"Shop {shop_id}",
        owner_name="Owner",
        industry="retail",
        locale="zh-CN",
        timezone="Asia/Shanghai",
        require_price_confirmation=True,
        require_new_item_confirmation=True,
        low_confidence_threshold=Decimal("0.8500"),
        default_low_stock_threshold=None,
        created_at=now,
        updated_at=now,
    )
    session = SessionRecord(
        session_id=session_id,
        shop_id=shop_id,
        session_type="workgroup",
        title=f"Session {session_id}",
        participants=["xiaoya"],
        last_event_seq=0,
        last_message_at=None,
        created_at=now,
        updated_at=now,
    )
    db_session.add(shop)
    db_session.add(session)
    db_session.flush()
    return session


def insert_task_run(
    db_session,
    *,
    session_id: str,
    task_type: str,
    status: str,
    created_at: datetime,
    completed_at: datetime | None = None,
    error_code: str | None = None,
) -> str:
    task_run_id = new_prefixed_id("task")
    message_id = new_prefixed_id("msg")
    db_session.add(
        Message(
            message_id=message_id,
            session_id=session_id,
            actor_type="owner",
            actor_id="owner_default",
            message_type="text",
            text=f"seed {task_type}",
            media_ids=[],
            client_request_id=f"seed_{task_run_id}",
            task_run_id=task_run_id,
            created_at=created_at,
        )
    )
    db_session.add(
        TaskRun(
            task_run_id=task_run_id,
            session_id=session_id,
            source_message_id=message_id,
            task_type=task_type,
            status=status,
            assigned_employee_id="xiaoya",
            result_summary=f"{task_type} {status}",
            error_code=error_code,
            error_message=error_code,
            created_at=created_at,
            updated_at=completed_at or created_at,
            completed_at=completed_at,
        )
    )
    db_session.flush()
    return task_run_id


def insert_confirmation(
    db_session,
    *,
    task_run_id: str,
    status: str,
    created_at: datetime,
    resolved_at: datetime | None = None,
) -> str:
    confirmation_id = new_prefixed_id("conf")
    db_session.add(
        Confirmation(
            confirmation_id=confirmation_id,
            task_run_id=task_run_id,
            confirmation_type="low-confidence-recognition",
            status=status,
            fields={"summary": "Confirm inventory action"},
            requested_by_employee_id="xiaoya",
            resolution_payload=None if resolved_at is None else {"decision": status},
            approved_by_actor_id=None if resolved_at is None else "owner_default",
            created_at=created_at,
            resolved_at=resolved_at,
        )
    )
    db_session.flush()
    return confirmation_id


def insert_provider_telemetry(
    db_session,
    *,
    shop_id: str,
    task_run_id: str,
    created_at: datetime,
    task_type: str,
    capability: str,
    provider_mode: str,
    provider_label: str,
    outcome: str,
    used_fallback: bool = False,
    recognized_confidence: float | None = None,
    low_confidence: bool = False,
    error_code: str | None = None,
    trial_provider_profile: str = "pilot-v1",
    cutover_mode: str | None = None,
    guardrail_status: str | None = None,
    guardrail_reason: str | None = None,
    shadow_forced_confirmation: bool | None = None,
    guardrail_degraded: bool | None = None,
    guardrail_degraded_reasons: list[str] | None = None,
) -> str:
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

    audit_log_id = new_prefixed_id("audit")
    db_session.add(
        AuditLog(
            audit_log_id=audit_log_id,
            shop_id=shop_id,
            scope="pilot",
            action="runtime.provider_telemetry",
            actor_type="system",
            actor_id="runtime_system",
            task_run_id=task_run_id,
            target_type="task_run",
            target_id=task_run_id,
            metadata_json=metadata_json,
            created_at=created_at,
        )
    )
    db_session.flush()
    return audit_log_id


def insert_cutover_transition(
    db_session,
    *,
    shop_id: str,
    actor_id: str,
    previous_cutover_mode: str,
    new_cutover_mode: str,
    created_at: datetime,
    trial_provider_profile: str = "pilot-v1",
    approved_calibration_artifact_id: str | None = None,
    note: str | None = None,
) -> str:
    audit_log_id = new_prefixed_id("audit")
    db_session.add(
        AuditLog(
            audit_log_id=audit_log_id,
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
            created_at=created_at,
        )
    )
    db_session.flush()
    return audit_log_id


def insert_shift_bundle_export(
    db_session,
    *,
    shop_id: str,
    actor_id: str,
    created_at: datetime,
    bundle_id: str,
    manifest_path: str,
    overall_status: str,
    degraded_reasons: list[str] | None = None,
    trial_provider_profile: str = "pilot-v1",
    cutover_mode: str | None = None,
) -> str:
    audit_log_id = new_prefixed_id("audit")
    db_session.add(
        AuditLog(
            audit_log_id=audit_log_id,
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
                "degraded_reasons": list(degraded_reasons or []),
                "trial_provider_profile": trial_provider_profile,
                "cutover_mode": cutover_mode,
            },
            created_at=created_at,
        )
    )
    db_session.flush()
    return audit_log_id


def insert_session_event(
    db_session,
    *,
    session_id: str,
    task_run_id: str | None,
    event_type: str,
    occurred_at: datetime,
    seq: int,
    payload: dict[str, object] | None = None,
) -> str:
    event_id = new_prefixed_id("evt")
    db_session.add(
        SessionStreamEvent(
            event_id=event_id,
            session_id=session_id,
            seq=seq,
            event_type=event_type,
            task_run_id=task_run_id,
            message_id=None,
            payload=dict(payload or {}),
            occurred_at=occurred_at,
        )
    )
    session = db_session.get(SessionRecord, session_id)
    if session is not None and session.last_event_seq < seq:
        session.last_event_seq = seq
    db_session.flush()
    return event_id
