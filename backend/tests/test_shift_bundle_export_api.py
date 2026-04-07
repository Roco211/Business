from __future__ import annotations

from sqlalchemy import select

from app.db.session import get_session_factory
from app.models import AuditLog
from pilot_test_helpers import auth_owner_headers


def _list_shift_bundle_export_audits() -> list[AuditLog]:
    db_session = get_session_factory()()
    try:
        return db_session.scalars(
            select(AuditLog)
            .where(
                AuditLog.scope == "pilot",
                AuditLog.action == "pilot.shift_bundle_exported",
                AuditLog.shop_id == "shop_default",
            )
            .order_by(AuditLog.created_at.asc(), AuditLog.audit_log_id.asc())
        ).all()
    finally:
        db_session.close()


def test_shift_bundle_export_record_requires_owner_auth(client) -> None:
    response = client.post(
        "/api/v1/system/shift-bundle-exports",
        json={
            "bundle_id": "shift_bundle_20260407T090000000000Z",
            "manifest_path": "C:/secure/pilot/shift_bundle_20260407/manifest.json",
            "overall_status": "ready",
            "degraded_reasons": [],
        },
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


def test_shift_bundle_export_record_is_idempotent_by_bundle_id_and_path(
    client,
    monkeypatch,
) -> None:
    monkeypatch.setenv("TRIAL_PROVIDER_PROFILE", "pilot-v1")
    headers = auth_owner_headers(client, monkeypatch)
    payload = {
        "bundle_id": "shift_bundle_20260407T090000000000Z",
        "manifest_path": "C:/secure/pilot/shift_bundle_20260407/manifest.json",
        "overall_status": "degraded",
        "degraded_reasons": ["provider_failures_present"],
        "cutover_mode": "closed",
        "hours": 24,
    }

    response = client.post(
        "/api/v1/system/shift-bundle-exports",
        headers=headers,
        json=payload,
    )

    assert response.status_code == 200
    first = response.json()["data"]
    assert first["bundle_id"] == payload["bundle_id"]
    assert first["reused_existing"] is False

    second_response = client.post(
        "/api/v1/system/shift-bundle-exports",
        headers=headers,
        json=payload,
    )

    assert second_response.status_code == 200
    second = second_response.json()["data"]
    assert second["reused_existing"] is True
    assert second["shift_bundle_audit_log_id"] == first["shift_bundle_audit_log_id"]

    audit_logs = _list_shift_bundle_export_audits()
    assert len(audit_logs) == 1
    assert audit_logs[0].metadata_json == {
        "bundle_id": payload["bundle_id"],
        "manifest_path": payload["manifest_path"],
        "overall_status": payload["overall_status"],
        "degraded_reasons": payload["degraded_reasons"],
        "trial_provider_profile": "pilot-v1",
        "cutover_mode": "closed",
        "hours": 24,
    }
