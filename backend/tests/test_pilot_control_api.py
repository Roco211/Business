from sqlalchemy import select
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.db.session import get_session_factory
from app.models import PilotControl
from app.api.routes import health as health_routes
from conftest import auth_headers, login_and_get_token


def _auth_headers(client, monkeypatch=None) -> dict[str, str]:
    return auth_headers(login_and_get_token(client, monkeypatch))


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
