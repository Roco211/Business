from __future__ import annotations

from datetime import timedelta

from app.db.session import get_session_factory
from app.services.bootstrap import ensure_default_context
from app.services.pilot_control import get_or_create_pilot_control
from pilot_test_helpers import (
    auth_owner_headers,
    insert_confirmation,
    insert_provider_telemetry,
    insert_shift_bundle_export,
    insert_task_run,
    utc_now_naive,
)


def test_operator_diagnostics_requires_owner_auth(client) -> None:
    response = client.get("/api/v1/system/operator-diagnostics")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


def test_operator_diagnostics_returns_cutover_reasons_affected_tasks_and_latest_bundle(
    client,
    monkeypatch,
) -> None:
    monkeypatch.setenv("TRIAL_PROVIDER_PROFILE", "pilot-v1")

    db_session = get_session_factory()()
    try:
        context = ensure_default_context(db_session)
        pilot_control, _ = get_or_create_pilot_control(
            db_session,
            shop_id=context.shop.shop_id,
            trial_provider_profile="pilot-v1",
        )
        pilot_control.cutover_mode = "open"
        pilot_control.approved_calibration_artifact_id = "artifact_20260407"
        pilot_control.last_preflight_status = "ready"

        now = utc_now_naive()
        failed_task_id = insert_task_run(
            db_session,
            session_id=context.session.session_id,
            task_type="photo-stock-query",
            status="failed",
            created_at=now - timedelta(minutes=30),
            completed_at=now - timedelta(minutes=28),
            error_code="vision_unavailable",
        )
        awaiting_confirmation_task_id = insert_task_run(
            db_session,
            session_id=context.session.session_id,
            task_type="voice-stock-in",
            status="awaiting-confirmation",
            created_at=now - timedelta(minutes=20),
        )
        insert_confirmation(
            db_session,
            task_run_id=awaiting_confirmation_task_id,
            status="pending",
            created_at=now - timedelta(minutes=19),
        )
        insert_provider_telemetry(
            db_session,
            shop_id=context.shop.shop_id,
            task_run_id=failed_task_id,
            created_at=now - timedelta(minutes=28),
            task_type="photo-stock-query",
            capability="vision",
            provider_mode="real-provider",
            provider_label="vision-primary",
            outcome="failed",
            error_code="vision_unavailable",
            cutover_mode="open",
            guardrail_status="allowed",
        )
        insert_provider_telemetry(
            db_session,
            shop_id=context.shop.shop_id,
            task_run_id=awaiting_confirmation_task_id,
            created_at=now - timedelta(minutes=19),
            task_type="voice-stock-in",
            capability="guardrail",
            provider_mode="guardrail",
            provider_label="pilot-cutover",
            outcome="awaiting-confirmation",
            cutover_mode="open",
            guardrail_status="forced-confirmation",
            guardrail_reason="cutover_alignment_invalid",
            guardrail_degraded=True,
            guardrail_degraded_reasons=["trial_provider_profile_mismatch"],
            shadow_forced_confirmation=False,
        )
        latest_bundle_audit_id = insert_shift_bundle_export(
            db_session,
            shop_id=context.shop.shop_id,
            actor_id="owner_default",
            created_at=now - timedelta(minutes=5),
            bundle_id="shift_bundle_20260407T090000000000Z",
            manifest_path="C:/secure/pilot/shift_bundle_20260407/manifest.json",
            overall_status="degraded",
            degraded_reasons=["provider_failures_present", "fallback_rate_exceeded"],
            cutover_mode="open",
        )
        db_session.commit()
    finally:
        db_session.close()

    response = client.get(
        "/api/v1/system/operator-diagnostics?hours=24&limit=10",
        headers=auth_owner_headers(client, monkeypatch),
    )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["trial_provider_profile"] == "pilot-v1"
    assert payload["current_cutover_mode"] == "open"
    assert payload["operator_verdict"] == "rollback-recommended"
    assert payload["incident_summary"]["total_incidents"] == 2
    assert payload["recent_reasons"] == {
        "cutover_alignment_invalid": 1,
        "trial_provider_profile_mismatch": 1,
        "vision_unavailable": 1,
    }
    assert {item["task_run_id"] for item in payload["affected_tasks"]} == {
        failed_task_id,
        awaiting_confirmation_task_id,
    }
    assert payload["latest_shift_bundle"] == {
        "audit_log_id": latest_bundle_audit_id,
        "bundle_id": "shift_bundle_20260407T090000000000Z",
        "manifest_path": "C:/secure/pilot/shift_bundle_20260407/manifest.json",
        "overall_status": "degraded",
        "degraded_reasons": ["provider_failures_present", "fallback_rate_exceeded"],
    }
    assert payload["suggested_actions"] == [
        "set_cutover_closed",
        "run_task_diagnostic_replay",
        "review_latest_shift_bundle",
    ]
