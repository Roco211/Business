from sqlalchemy import select
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.db.session import get_session_factory
from app.models import AuditLog, PilotControl
from app.api.routes import health as health_routes
from conftest import auth_headers, login_and_get_token


def _auth_headers(client, monkeypatch=None) -> dict[str, str]:
    return auth_headers(login_and_get_token(client, monkeypatch))


def _list_cutover_transition_audits(*, shop_id: str) -> list[AuditLog]:
    db_session = get_session_factory()()
    try:
        return db_session.scalars(
            select(AuditLog)
            .where(
                AuditLog.shop_id == shop_id,
                AuditLog.scope == "pilot",
                AuditLog.action == "pilot.cutover_transition",
            )
            .order_by(AuditLog.created_at.asc(), AuditLog.audit_log_id.asc())
        ).all()
    finally:
        db_session.close()


def test_pilot_control_endpoint_requires_owner_auth(client) -> None:
    response = client.get("/api/v1/system/pilot-control")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


def test_pilot_control_get_creates_default_closed_record_for_seeded_shop(client, monkeypatch) -> None:
    monkeypatch.setenv("TRIAL_PROVIDER_PROFILE", "pilot-v1")

    response = client.get("/api/v1/system/pilot-control", headers=_auth_headers(client, monkeypatch))

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["shop_id"] == "shop_default"
    assert payload["trial_provider_profile"] == "pilot-v1"
    assert payload["cutover_mode"] == "closed"
    assert payload["approved_calibration_artifact_id"] is None

    db_session = get_session_factory()()
    try:
        rows = db_session.scalars(
            select(PilotControl).where(PilotControl.shop_id == payload["shop_id"])
        ).all()
        assert len(rows) == 1
        assert rows[0].cutover_mode == "closed"
    finally:
        db_session.close()


def test_pilot_control_post_rejects_invalid_mode_transition(client, monkeypatch) -> None:
    monkeypatch.setenv("TRIAL_PROVIDER_PROFILE", "pilot-v1")

    response = client.post(
        "/api/v1/system/pilot-control",
        headers=_auth_headers(client, monkeypatch),
        json={"cutover_mode": "open"},
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "invalid_cutover_mode_transition"


def test_pilot_control_surfaces_profile_artifact_and_current_mode(client, monkeypatch) -> None:
    monkeypatch.setenv("TRIAL_PROVIDER_PROFILE", "pilot-v1")
    headers = _auth_headers(client, monkeypatch)

    update_response = client.post(
        "/api/v1/system/pilot-control",
        headers=headers,
        json={
            "cutover_mode": "shadow",
            "approved_calibration_artifact_id": "artifact_20260407",
        },
    )
    assert update_response.status_code == 200

    response = client.get("/api/v1/system/pilot-control", headers=headers)

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["trial_provider_profile"] == "pilot-v1"
    assert payload["approved_calibration_artifact_id"] == "artifact_20260407"
    assert payload["cutover_mode"] == "shadow"


def test_pilot_control_post_rejects_invalid_mode_literal(client, monkeypatch) -> None:
    monkeypatch.setenv("TRIAL_PROVIDER_PROFILE", "pilot-v1")

    response = client.post(
        "/api/v1/system/pilot-control",
        headers=_auth_headers(client, monkeypatch),
        json={"cutover_mode": "invalid-mode"},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_cutover_mode"


def test_pilot_control_post_requires_non_empty_mutation_payload(client, monkeypatch) -> None:
    monkeypatch.setenv("TRIAL_PROVIDER_PROFILE", "pilot-v1")

    response = client.post(
        "/api/v1/system/pilot-control",
        headers=_auth_headers(client, monkeypatch),
        json={},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_pilot_control_post_switches_closed_to_shadow_and_writes_transition_audit(
    client,
    monkeypatch,
) -> None:
    monkeypatch.setenv("TRIAL_PROVIDER_PROFILE", "pilot-v1")
    headers = _auth_headers(client, monkeypatch)

    response = client.post(
        "/api/v1/system/pilot-control",
        headers=headers,
        json={
            "cutover_mode": "shadow",
            "notes": "provider observation window",
        },
    )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["previous_cutover_mode"] == "closed"
    assert payload["cutover_mode"] == "shadow"
    assert payload["notes"] == "provider observation window"
    assert isinstance(payload["transition_audit_log_id"], str)

    audit_logs = _list_cutover_transition_audits(shop_id="shop_default")
    assert len(audit_logs) == 1
    assert audit_logs[0].audit_log_id == payload["transition_audit_log_id"]
    assert audit_logs[0].actor_id == "owner_default"
    assert audit_logs[0].metadata_json == {
        "shop_id": "shop_default",
        "previous_cutover_mode": "closed",
        "new_cutover_mode": "shadow",
        "actor_id": "owner_default",
        "trial_provider_profile": "pilot-v1",
        "approved_calibration_artifact_id": None,
        "note": "provider observation window",
    }


def test_pilot_control_post_rejects_shadow_to_open_without_ready_preflight(
    client,
    monkeypatch,
) -> None:
    monkeypatch.setenv("TRIAL_PROVIDER_PROFILE", "pilot-v1")
    headers = _auth_headers(client, monkeypatch)

    shadow_response = client.post(
        "/api/v1/system/pilot-control",
        headers=headers,
        json={"cutover_mode": "shadow"},
    )
    assert shadow_response.status_code == 200

    response = client.post(
        "/api/v1/system/pilot-control",
        headers=headers,
        json={"cutover_mode": "open", "notes": "morning shift"},
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "invalid_cutover_mode_transition"

    current_state = client.get("/api/v1/system/pilot-control", headers=headers)
    assert current_state.status_code == 200
    assert current_state.json()["data"]["cutover_mode"] == "shadow"

    audit_logs = _list_cutover_transition_audits(shop_id="shop_default")
    assert len(audit_logs) == 1
    assert audit_logs[0].metadata_json["new_cutover_mode"] == "shadow"


def test_pilot_control_post_allows_shadow_to_open_after_ready_preflight_and_close_with_note(
    client,
    monkeypatch,
) -> None:
    monkeypatch.setenv("TRIAL_PROVIDER_PROFILE", "pilot-v1")
    headers = _auth_headers(client, monkeypatch)

    shadow_response = client.post(
        "/api/v1/system/pilot-control",
        headers=headers,
        json={"cutover_mode": "shadow", "notes": "provider observation window"},
    )
    assert shadow_response.status_code == 200
    shadow_payload = shadow_response.json()["data"]

    open_response = client.post(
        "/api/v1/system/pilot-control",
        headers=headers,
        json={
            "cutover_mode": "open",
            "approved_calibration_artifact_id": "artifact_20260407",
            "last_preflight_status": "ready",
            "notes": "morning shift",
        },
    )
    assert open_response.status_code == 200
    open_payload = open_response.json()["data"]
    assert open_payload["previous_cutover_mode"] == "shadow"
    assert open_payload["cutover_mode"] == "open"
    assert open_payload["last_preflight_status"] == "ready"

    close_response = client.post(
        "/api/v1/system/pilot-control",
        headers=headers,
        json={
            "cutover_mode": "closed",
            "notes": "provider incident rollback",
        },
    )
    assert close_response.status_code == 200
    close_payload = close_response.json()["data"]
    assert close_payload["previous_cutover_mode"] == "open"
    assert close_payload["cutover_mode"] == "closed"
    assert close_payload["closed_by_actor_id"] == "owner_default"
    assert close_payload["notes"] == "provider incident rollback"

    audit_logs = _list_cutover_transition_audits(shop_id="shop_default")
    assert len(audit_logs) == 3
    assert [log.audit_log_id for log in audit_logs] == [
        shadow_payload["transition_audit_log_id"],
        open_payload["transition_audit_log_id"],
        close_payload["transition_audit_log_id"],
    ]
    assert [log.metadata_json["previous_cutover_mode"] for log in audit_logs] == [
        "closed",
        "shadow",
        "open",
    ]
    assert [log.metadata_json["new_cutover_mode"] for log in audit_logs] == [
        "shadow",
        "open",
        "closed",
    ]
    assert audit_logs[1].metadata_json["approved_calibration_artifact_id"] == "artifact_20260407"
    assert audit_logs[2].metadata_json["note"] == "provider incident rollback"


def test_pilot_control_post_requires_fresh_note_for_close_transition(
    client,
    monkeypatch,
) -> None:
    monkeypatch.setenv("TRIAL_PROVIDER_PROFILE", "pilot-v1")
    headers = _auth_headers(client, monkeypatch)

    shadow_response = client.post(
        "/api/v1/system/pilot-control",
        headers=headers,
        json={"cutover_mode": "shadow", "notes": "provider observation window"},
    )
    assert shadow_response.status_code == 200

    open_response = client.post(
        "/api/v1/system/pilot-control",
        headers=headers,
        json={
            "cutover_mode": "open",
            "approved_calibration_artifact_id": "artifact_20260407",
            "last_preflight_status": "ready",
            "notes": "morning shift",
        },
    )
    assert open_response.status_code == 200

    close_without_note = client.post(
        "/api/v1/system/pilot-control",
        headers=headers,
        json={"cutover_mode": "closed"},
    )
    assert close_without_note.status_code == 409
    assert close_without_note.json()["error"]["code"] == "invalid_cutover_mode_transition"

    state_after_rejected_close = client.get("/api/v1/system/pilot-control", headers=headers)
    assert state_after_rejected_close.status_code == 200
    assert state_after_rejected_close.json()["data"]["cutover_mode"] == "open"

    close_with_note = client.post(
        "/api/v1/system/pilot-control",
        headers=headers,
        json={"cutover_mode": "closed", "notes": "provider incident rollback"},
    )
    assert close_with_note.status_code == 200

    audit_logs = _list_cutover_transition_audits(shop_id="shop_default")
    assert len(audit_logs) == 3
    assert [log.metadata_json["new_cutover_mode"] for log in audit_logs] == [
        "shadow",
        "open",
        "closed",
    ]
    assert audit_logs[2].metadata_json["note"] == "provider incident rollback"


def test_pilot_control_post_requires_fresh_preflight_status_for_each_shadow_to_open_transition(
    client,
    monkeypatch,
) -> None:
    monkeypatch.setenv("TRIAL_PROVIDER_PROFILE", "pilot-v1")
    headers = _auth_headers(client, monkeypatch)

    shadow_first = client.post(
        "/api/v1/system/pilot-control",
        headers=headers,
        json={"cutover_mode": "shadow", "notes": "first window"},
    )
    assert shadow_first.status_code == 200

    open_first = client.post(
        "/api/v1/system/pilot-control",
        headers=headers,
        json={
            "cutover_mode": "open",
            "approved_calibration_artifact_id": "artifact_20260407",
            "last_preflight_status": "ready",
            "notes": "first open",
        },
    )
    assert open_first.status_code == 200

    close_first = client.post(
        "/api/v1/system/pilot-control",
        headers=headers,
        json={"cutover_mode": "closed", "notes": "close first window"},
    )
    assert close_first.status_code == 200

    shadow_second = client.post(
        "/api/v1/system/pilot-control",
        headers=headers,
        json={"cutover_mode": "shadow", "notes": "second window"},
    )
    assert shadow_second.status_code == 200

    open_without_fresh_preflight = client.post(
        "/api/v1/system/pilot-control",
        headers=headers,
        json={"cutover_mode": "open", "approved_calibration_artifact_id": "artifact_20260407"},
    )
    assert open_without_fresh_preflight.status_code == 409
    assert open_without_fresh_preflight.json()["error"]["code"] == "invalid_cutover_mode_transition"

    state_after_rejected_open = client.get("/api/v1/system/pilot-control", headers=headers)
    assert state_after_rejected_open.status_code == 200
    assert state_after_rejected_open.json()["data"]["cutover_mode"] == "shadow"

    open_with_fresh_preflight = client.post(
        "/api/v1/system/pilot-control",
        headers=headers,
        json={
            "cutover_mode": "open",
            "approved_calibration_artifact_id": "artifact_20260407",
            "last_preflight_status": "ready",
            "notes": "second open",
        },
    )
    assert open_with_fresh_preflight.status_code == 200


def test_pilot_control_database_enforces_allowed_cutover_modes(client, monkeypatch) -> None:
    monkeypatch.setenv("TRIAL_PROVIDER_PROFILE", "pilot-v1")
    headers = _auth_headers(client, monkeypatch)
    ensure_response = client.get("/api/v1/system/pilot-control", headers=headers)
    assert ensure_response.status_code == 200

    db_session = get_session_factory()()
    try:
        try:
            db_session.execute(
                text(
                    "UPDATE pilot_controls SET cutover_mode = 'invalid-literal' "
                    "WHERE shop_id = 'shop_default'"
                )
            )
            db_session.commit()
        except IntegrityError:
            db_session.rollback()
        else:
            raise AssertionError("Expected IntegrityError when writing invalid cutover_mode literal")
    finally:
        db_session.close()


def test_pilot_control_get_recovers_from_duplicate_create_commit_race(client, monkeypatch) -> None:
    monkeypatch.setenv("TRIAL_PROVIDER_PROFILE", "pilot-v1")
    headers = _auth_headers(client, monkeypatch)

    original_commit = health_routes.Session.commit
    triggered = {"value": False}

    def flaky_commit(self):
        has_new_pilot_control = any(isinstance(instance, PilotControl) for instance in self.new)
        if has_new_pilot_control and not triggered["value"]:
            triggered["value"] = True
            race_session = get_session_factory()()
            try:
                race_session.add(
                    PilotControl(
                        shop_id="shop_default",
                        trial_provider_profile="pilot-v1",
                        approved_calibration_artifact_id=None,
                        approved_calibration_report_path=None,
                        cutover_mode="closed",
                        opened_at=None,
                        opened_by_actor_id=None,
                        closed_at=None,
                        closed_by_actor_id=None,
                        last_preflight_at=None,
                        last_preflight_status=None,
                        notes=None,
                    )
                )
                original_commit(race_session)
            finally:
                race_session.close()
            raise IntegrityError("duplicate key", {}, Exception("duplicate key"))
        return original_commit(self)

    monkeypatch.setattr(health_routes.Session, "commit", flaky_commit)

    response = client.get("/api/v1/system/pilot-control", headers=headers)
    assert response.status_code == 200
    assert response.json()["data"]["shop_id"] == "shop_default"
    assert response.json()["data"]["cutover_mode"] == "closed"
    assert triggered["value"] is True


def test_pilot_control_post_recovers_from_duplicate_create_during_first_mutation(client, monkeypatch) -> None:
    monkeypatch.setenv("TRIAL_PROVIDER_PROFILE", "pilot-v1")
    headers = _auth_headers(client, monkeypatch)

    real_mutate = health_routes.mutate_pilot_control
    calls = {"count": 0}

    def flaky_mutate(*args, **kwargs):
        if calls["count"] == 0:
            calls["count"] += 1
            raise IntegrityError("duplicate key", {}, Exception("duplicate key"))
        return real_mutate(*args, **kwargs)

    monkeypatch.setattr(health_routes, "mutate_pilot_control", flaky_mutate)

    response = client.post(
        "/api/v1/system/pilot-control",
        headers=headers,
        json={"cutover_mode": "shadow"},
    )

    assert response.status_code == 200
    assert response.json()["data"]["cutover_mode"] == "shadow"
    assert calls["count"] == 1
