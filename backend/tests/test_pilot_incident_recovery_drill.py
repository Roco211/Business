from __future__ import annotations

from datetime import timedelta

from app.db.session import get_session_factory
from app.services.bootstrap import ensure_default_context
from app.services.pilot_control import get_or_create_pilot_control
from pilot_test_helpers import auth_owner_headers, insert_provider_telemetry, insert_task_run, utc_now_naive


def test_pilot_incident_recovery_drill_covers_export_diagnostics_replay_backfill_and_reopen(
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
        )
        db_session.commit()
    finally:
        db_session.close()

    headers = auth_owner_headers(client, monkeypatch)

    diagnostics_response = client.get(
        "/api/v1/system/operator-diagnostics?hours=24&limit=10",
        headers=headers,
    )
    assert diagnostics_response.status_code == 200
    diagnostics_payload = diagnostics_response.json()["data"]
    assert diagnostics_payload["operator_verdict"] == "rollback-recommended"

    bundle_response = client.post(
        "/api/v1/system/shift-bundle-exports",
        headers=headers,
        json={
            "bundle_id": "shift_bundle_20260407T090000000000Z",
            "manifest_path": "C:/secure/pilot/shift_bundle_20260407/manifest.json",
            "overall_status": "degraded",
            "degraded_reasons": ["provider_failures_present"],
            "cutover_mode": "open",
            "hours": 24,
        },
    )
    assert bundle_response.status_code == 200
    assert bundle_response.json()["data"]["reused_existing"] is False

    timeline_response = client.get(
        "/api/v1/system/incident-timeline?hours=24&limit=10",
        headers=headers,
    )
    assert timeline_response.status_code == 200
    timeline_payload = timeline_response.json()["data"]
    assert timeline_payload["summary"]["total_incidents"] >= 1

    replay_response = client.post(
        "/api/v1/system/incident-replays/task-diagnostic",
        headers=headers,
        json={"task_run_id": failed_task_id, "idempotency_key": "drill-replay-1"},
    )
    assert replay_response.status_code == 200
    assert replay_response.json()["data"]["incident"]["task"]["task_run_id"] == failed_task_id

    backfill_response = client.post(
        "/api/v1/system/operator-view-backfills",
        headers=headers,
        json={"view": "incident-timeline", "hours": 24, "limit": 10, "idempotency_key": "drill-backfill-1"},
    )
    assert backfill_response.status_code == 200
    assert backfill_response.json()["data"]["snapshot"]["total_incidents"] >= 1

    close_response = client.post(
        "/api/v1/system/pilot-control",
        headers=headers,
        json={"cutover_mode": "closed", "notes": "incident rollback drill"},
    )
    assert close_response.status_code == 200
    assert close_response.json()["data"]["cutover_mode"] == "closed"

    shadow_response = client.post(
        "/api/v1/system/pilot-control",
        headers=headers,
        json={"cutover_mode": "shadow", "notes": "shadow reopen after drill"},
    )
    assert shadow_response.status_code == 200
    assert shadow_response.json()["data"]["cutover_mode"] == "shadow"

    reopen_response = client.post(
        "/api/v1/system/pilot-control",
        headers=headers,
        json={
            "cutover_mode": "open",
            "approved_calibration_artifact_id": "artifact_20260407",
            "last_preflight_status": "ready",
            "notes": "reopen after incident drill",
        },
    )
    assert reopen_response.status_code == 200
    assert reopen_response.json()["data"]["cutover_mode"] == "open"

    final_control = client.get("/api/v1/system/pilot-control", headers=headers)
    assert final_control.status_code == 200
    assert final_control.json()["data"]["cutover_mode"] == "open"
