from __future__ import annotations

from datetime import timedelta

from app.db.session import get_session_factory
from app.services.bootstrap import ensure_default_context
from pilot_test_helpers import (
    auth_owner_headers,
    create_shop_and_session,
    insert_confirmation,
    insert_cutover_transition,
    insert_provider_telemetry,
    insert_session_event,
    insert_task_run,
    utc_now_naive,
)


def test_incident_timeline_endpoint_requires_owner_auth(client) -> None:
    response = client.get("/api/v1/system/incident-timeline")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


def test_incident_timeline_returns_correlated_provider_guardrail_and_cutover_incidents(
    client,
    monkeypatch,
) -> None:
    monkeypatch.setenv("TRIAL_PROVIDER_PROFILE", "pilot-v1")

    db_session = get_session_factory()()
    try:
        context = ensure_default_context(db_session)
        now = utc_now_naive()

        failed_task_id = insert_task_run(
            db_session,
            session_id=context.session.session_id,
            task_type="photo-stock-query",
            status="failed",
            created_at=now - timedelta(minutes=20),
            completed_at=now - timedelta(minutes=18),
            error_code="vision_unavailable",
        )
        forced_confirmation_task_id = insert_task_run(
            db_session,
            session_id=context.session.session_id,
            task_type="voice-stock-in",
            status="awaiting-confirmation",
            created_at=now - timedelta(minutes=12),
        )
        success_task_id = insert_task_run(
            db_session,
            session_id=context.session.session_id,
            task_type="voice-stock-query",
            status="completed",
            created_at=now - timedelta(minutes=8),
            completed_at=now - timedelta(minutes=7),
        )

        insert_confirmation(
            db_session,
            task_run_id=forced_confirmation_task_id,
            status="pending",
            created_at=now - timedelta(minutes=11),
        )

        insert_session_event(
            db_session,
            session_id=context.session.session_id,
            task_run_id=failed_task_id,
            event_type="message.created",
            occurred_at=now - timedelta(minutes=20),
            seq=1,
            payload={"preview_text": "where is cola"},
        )
        insert_session_event(
            db_session,
            session_id=context.session.session_id,
            task_run_id=failed_task_id,
            event_type="task.updated",
            occurred_at=now - timedelta(minutes=18),
            seq=2,
            payload={"status": "failed", "error_code": "vision_unavailable"},
        )
        insert_session_event(
            db_session,
            session_id=context.session.session_id,
            task_run_id=forced_confirmation_task_id,
            event_type="task.updated",
            occurred_at=now - timedelta(minutes=12),
            seq=3,
            payload={"status": "awaiting-confirmation"},
        )
        insert_session_event(
            db_session,
            session_id=context.session.session_id,
            task_run_id=forced_confirmation_task_id,
            event_type="confirmation.created",
            occurred_at=now - timedelta(minutes=11),
            seq=4,
            payload={"status": "pending"},
        )

        failed_audit_log_id = insert_provider_telemetry(
            db_session,
            shop_id=context.shop.shop_id,
            task_run_id=failed_task_id,
            created_at=now - timedelta(minutes=18),
            task_type="photo-stock-query",
            capability="vision",
            provider_mode="real-provider",
            provider_label="vision-primary",
            outcome="failed",
            error_code="vision_unavailable",
            cutover_mode="open",
            guardrail_status="allowed",
        )
        forced_confirmation_audit_log_id = insert_provider_telemetry(
            db_session,
            shop_id=context.shop.shop_id,
            task_run_id=forced_confirmation_task_id,
            created_at=now - timedelta(minutes=11),
            task_type="voice-stock-in",
            capability="guardrail",
            provider_mode="guardrail",
            provider_label="pilot-cutover",
            outcome="awaiting-confirmation",
            cutover_mode="shadow",
            guardrail_status="forced-confirmation",
            guardrail_reason="cutover_mode_shadow",
            shadow_forced_confirmation=True,
            guardrail_degraded=True,
            guardrail_degraded_reasons=["trial_provider_profile_mismatch"],
        )
        insert_provider_telemetry(
            db_session,
            shop_id=context.shop.shop_id,
            task_run_id=success_task_id,
            created_at=now - timedelta(minutes=7),
            task_type="voice-stock-query",
            capability="asr",
            provider_mode="real-provider",
            provider_label="asr-primary",
            outcome="completed",
            cutover_mode="shadow",
        )
        cutover_audit_log_id = insert_cutover_transition(
            db_session,
            shop_id=context.shop.shop_id,
            actor_id="owner_default",
            previous_cutover_mode="open",
            new_cutover_mode="closed",
            created_at=now - timedelta(minutes=5),
            note="rollback after incident",
        )

        other_session = create_shop_and_session(
            db_session,
            shop_id="shop_other",
            session_id="sess_other",
        )
        other_task_id = insert_task_run(
            db_session,
            session_id=other_session.session_id,
            task_type="photo-stock-query",
            status="failed",
            created_at=now - timedelta(minutes=6),
            completed_at=now - timedelta(minutes=4),
            error_code="vision_unavailable",
        )
        insert_provider_telemetry(
            db_session,
            shop_id="shop_other",
            task_run_id=other_task_id,
            created_at=now - timedelta(minutes=4),
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
            task_run_id=failed_task_id,
            created_at=now - timedelta(minutes=3),
            task_type="photo-stock-query",
            capability="vision",
            provider_mode="real-provider",
            provider_label="vision-primary",
            outcome="failed",
            error_code="vision_unavailable",
            cutover_mode="open",
            trial_provider_profile="pilot-v2",
        )
        db_session.commit()
    finally:
        db_session.close()

    response = client.get(
        "/api/v1/system/incident-timeline?hours=24&limit=10",
        headers=auth_owner_headers(client, monkeypatch),
    )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["time_window"]["hours"] == 24
    assert payload["trial_provider_profile"] == "pilot-v1"
    assert payload["summary"]["total_incidents"] == 3
    assert payload["summary"]["incidents_by_source"] == {
        "cutover-transition": 1,
        "provider-telemetry": 2,
    }
    assert payload["summary"]["provider_failures"] == {"vision_unavailable": 1}
    assert payload["summary"]["guardrail_reasons"] == {
        "cutover_mode_shadow": 1,
        "trial_provider_profile_mismatch": 1,
    }
    assert set(payload["summary"]["affected_task_ids"]) == {failed_task_id, forced_confirmation_task_id}

    incidents = {item["incident_id"]: item for item in payload["incidents"]}
    assert set(incidents) == {
        failed_audit_log_id,
        forced_confirmation_audit_log_id,
        cutover_audit_log_id,
    }

    failed_incident = incidents[failed_audit_log_id]
    assert failed_incident["source"] == "provider-telemetry"
    assert failed_incident["severity"] == "critical"
    assert failed_incident["reasons"] == ["vision_unavailable"]
    assert failed_incident["provider_label"] == "vision-primary"
    assert failed_incident["task"]["task_run_id"] == failed_task_id
    assert failed_incident["task"]["task_type"] == "photo-stock-query"
    assert failed_incident["task"]["status"] == "failed"
    assert failed_incident["confirmation"] is None
    assert [item["event_type"] for item in failed_incident["session_events"]] == [
        "message.created",
        "task.updated",
    ]

    forced_confirmation_incident = incidents[forced_confirmation_audit_log_id]
    assert forced_confirmation_incident["source"] == "provider-telemetry"
    assert forced_confirmation_incident["severity"] == "degraded"
    assert forced_confirmation_incident["cutover_mode"] == "shadow"
    assert forced_confirmation_incident["guardrail_status"] == "forced-confirmation"
    assert forced_confirmation_incident["reasons"] == [
        "cutover_mode_shadow",
        "trial_provider_profile_mismatch",
    ]
    assert forced_confirmation_incident["confirmation"]["status"] == "pending"
    assert [item["event_type"] for item in forced_confirmation_incident["session_events"]] == [
        "task.updated",
        "confirmation.created",
    ]

    cutover_incident = incidents[cutover_audit_log_id]
    assert cutover_incident["source"] == "cutover-transition"
    assert cutover_incident["severity"] == "critical"
    assert cutover_incident["summary"] == "Cutover changed from open to closed"
    assert cutover_incident["reasons"] == ["cutover_mode_closed"]
    assert cutover_incident["task"] is None
    assert cutover_incident["confirmation"] is None
    assert cutover_incident["session_events"] == []


def test_incident_timeline_respects_limit_and_excludes_non_incident_telemetry(
    client,
    monkeypatch,
) -> None:
    monkeypatch.setenv("TRIAL_PROVIDER_PROFILE", "pilot-v1")

    db_session = get_session_factory()()
    try:
        context = ensure_default_context(db_session)
        now = utc_now_naive()

        blocked_task_id = insert_task_run(
            db_session,
            session_id=context.session.session_id,
            task_type="voice-stock-in",
            status="failed",
            created_at=now - timedelta(minutes=30),
            completed_at=now - timedelta(minutes=29),
            error_code="pilot_cutover_closed",
        )
        degraded_task_id = insert_task_run(
            db_session,
            session_id=context.session.session_id,
            task_type="receipt-ocr",
            status="awaiting-confirmation",
            created_at=now - timedelta(minutes=25),
        )
        success_task_id = insert_task_run(
            db_session,
            session_id=context.session.session_id,
            task_type="voice-stock-query",
            status="completed",
            created_at=now - timedelta(minutes=20),
            completed_at=now - timedelta(minutes=19),
        )

        blocked_audit_log_id = insert_provider_telemetry(
            db_session,
            shop_id=context.shop.shop_id,
            task_run_id=blocked_task_id,
            created_at=now - timedelta(minutes=29),
            task_type="voice-stock-in",
            capability="guardrail",
            provider_mode="guardrail",
            provider_label="pilot-cutover",
            outcome="failed",
            error_code="pilot_cutover_closed",
            cutover_mode="closed",
            guardrail_status="blocked",
            guardrail_reason="cutover_mode_closed",
        )
        degraded_audit_log_id = insert_provider_telemetry(
            db_session,
            shop_id=context.shop.shop_id,
            task_run_id=degraded_task_id,
            created_at=now - timedelta(minutes=24),
            task_type="receipt-ocr",
            capability="ocr",
            provider_mode="real-provider",
            provider_label="ocr-primary",
            outcome="awaiting-confirmation",
            used_fallback=True,
            low_confidence=True,
            cutover_mode="shadow",
        )
        insert_provider_telemetry(
            db_session,
            shop_id=context.shop.shop_id,
            task_run_id=success_task_id,
            created_at=now - timedelta(minutes=19),
            task_type="voice-stock-query",
            capability="asr",
            provider_mode="real-provider",
            provider_label="asr-primary",
            outcome="completed",
            cutover_mode="shadow",
        )
        db_session.commit()
    finally:
        db_session.close()

    response = client.get(
        "/api/v1/system/incident-timeline?hours=24&limit=1",
        headers=auth_owner_headers(client, monkeypatch),
    )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["summary"]["total_incidents"] == 2
    assert len(payload["incidents"]) == 1
    assert payload["incidents"][0]["incident_id"] == degraded_audit_log_id
    assert blocked_audit_log_id != degraded_audit_log_id
