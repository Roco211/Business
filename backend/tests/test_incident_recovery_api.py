from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select

from app.db.session import get_session_factory
from app.models import AuditLog
from app.services.bootstrap import ensure_default_context
from pilot_test_helpers import (
    auth_owner_headers,
    insert_confirmation,
    insert_cutover_transition,
    insert_provider_telemetry,
    insert_session_event,
    insert_task_run,
    utc_now_naive,
)


def _count_pilot_audits(*, action: str) -> int:
    db_session = get_session_factory()()
    try:
        return len(
            db_session.scalars(
                select(AuditLog).where(
                    AuditLog.scope == "pilot",
                    AuditLog.action == action,
                    AuditLog.shop_id == "shop_default",
                )
            ).all()
        )
    finally:
        db_session.close()


def test_incident_recovery_endpoints_require_owner_auth(client) -> None:
    replay_response = client.post(
        "/api/v1/system/incident-replays/task-diagnostic",
        json={"task_run_id": "task_123", "idempotency_key": "diag-1"},
    )
    backfill_response = client.post(
        "/api/v1/system/operator-view-backfills",
        json={"view": "incident-timeline", "idempotency_key": "backfill-1"},
    )

    assert replay_response.status_code == 401
    assert replay_response.json()["error"]["code"] == "unauthorized"
    assert backfill_response.status_code == 401
    assert backfill_response.json()["error"]["code"] == "unauthorized"


def test_task_diagnostic_replay_returns_correlated_incident_and_is_idempotent(
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
            created_at=now - timedelta(minutes=15),
            completed_at=now - timedelta(minutes=14),
            error_code="vision_unavailable",
        )
        insert_session_event(
            db_session,
            session_id=context.session.session_id,
            task_run_id=failed_task_id,
            event_type="task.updated",
            occurred_at=now - timedelta(minutes=14),
            seq=1,
            payload={"status": "failed", "error_code": "vision_unavailable"},
        )
        insert_provider_telemetry(
            db_session,
            shop_id=context.shop.shop_id,
            task_run_id=failed_task_id,
            created_at=now - timedelta(minutes=14),
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

    response = client.post(
        "/api/v1/system/incident-replays/task-diagnostic",
        headers=auth_owner_headers(client, monkeypatch),
        json={"task_run_id": failed_task_id, "idempotency_key": "diag-1"},
    )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["task_run_id"] == failed_task_id
    assert payload["idempotency_key"] == "diag-1"
    assert payload["reused_existing"] is False
    assert payload["incident"]["task"]["task_run_id"] == failed_task_id
    assert payload["incident"]["reasons"] == ["vision_unavailable"]
    assert payload["incident"]["session_events"][0]["event_type"] == "task.updated"
    assert _count_pilot_audits(action="pilot.task_diagnostic_replayed") == 1

    second_response = client.post(
        "/api/v1/system/incident-replays/task-diagnostic",
        headers=auth_owner_headers(client, monkeypatch),
        json={"task_run_id": failed_task_id, "idempotency_key": "diag-1"},
    )

    assert second_response.status_code == 200
    second_payload = second_response.json()["data"]
    assert second_payload["reused_existing"] is True
    assert second_payload["replay_audit_log_id"] == payload["replay_audit_log_id"]
    assert _count_pilot_audits(action="pilot.task_diagnostic_replayed") == 1


def test_operator_view_backfill_returns_summary_and_is_idempotent(
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
            created_at=now - timedelta(minutes=20),
            completed_at=now - timedelta(minutes=19),
            error_code="pilot_cutover_closed",
        )
        awaiting_confirmation_task_id = insert_task_run(
            db_session,
            session_id=context.session.session_id,
            task_type="receipt-ocr",
            status="awaiting-confirmation",
            created_at=now - timedelta(minutes=10),
        )
        insert_confirmation(
            db_session,
            task_run_id=awaiting_confirmation_task_id,
            status="pending",
            created_at=now - timedelta(minutes=9),
        )
        insert_provider_telemetry(
            db_session,
            shop_id=context.shop.shop_id,
            task_run_id=blocked_task_id,
            created_at=now - timedelta(minutes=19),
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
        insert_provider_telemetry(
            db_session,
            shop_id=context.shop.shop_id,
            task_run_id=awaiting_confirmation_task_id,
            created_at=now - timedelta(minutes=9),
            task_type="receipt-ocr",
            capability="ocr",
            provider_mode="real-provider",
            provider_label="ocr-primary",
            outcome="awaiting-confirmation",
            low_confidence=True,
            used_fallback=True,
            cutover_mode="shadow",
        )
        insert_cutover_transition(
            db_session,
            shop_id=context.shop.shop_id,
            actor_id="owner_default",
            previous_cutover_mode="shadow",
            new_cutover_mode="closed",
            created_at=now - timedelta(minutes=5),
            note="rollback after incident",
        )
        db_session.commit()
    finally:
        db_session.close()

    response = client.post(
        "/api/v1/system/operator-view-backfills",
        headers=auth_owner_headers(client, monkeypatch),
        json={
            "view": "incident-timeline",
            "hours": 24,
            "limit": 10,
            "idempotency_key": "backfill-1",
        },
    )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["view"] == "incident-timeline"
    assert payload["idempotency_key"] == "backfill-1"
    assert payload["reused_existing"] is False
    assert payload["snapshot"]["total_incidents"] == 3
    assert set(payload["snapshot"]["affected_task_ids"]) == {
        blocked_task_id,
        awaiting_confirmation_task_id,
    }
    assert _count_pilot_audits(action="pilot.operator_view_backfilled") == 1

    second_response = client.post(
        "/api/v1/system/operator-view-backfills",
        headers=auth_owner_headers(client, monkeypatch),
        json={
            "view": "incident-timeline",
            "hours": 24,
            "limit": 10,
            "idempotency_key": "backfill-1",
        },
    )

    assert second_response.status_code == 200
    second_payload = second_response.json()["data"]
    assert second_payload["reused_existing"] is True
    assert second_payload["backfill_audit_log_id"] == payload["backfill_audit_log_id"]
    assert _count_pilot_audits(action="pilot.operator_view_backfilled") == 1
