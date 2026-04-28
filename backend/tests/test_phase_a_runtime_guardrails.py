from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.db.session import get_engine, get_session_factory
from app.models import V2Account
from app.services.v2_identity import hash_v2_password
from app.services.system_readiness import build_mock_guardrails_check

from conftest import load_create_app, upgrade_test_database


def _settings(**overrides) -> Settings:
    base = {
        "app_env": "development",
        "app_host": "0.0.0.0",
        "app_port": 8001,
        "redis_url": "redis://redis:6379/0",
        "database_url": "sqlite:///./aism-dev.db",
    }
    base.update(overrides)
    return Settings(**base)


def test_readiness_mock_guardrails_reports_degraded_for_production_mock():
    check = build_mock_guardrails_check(
        _settings(app_env="production", app_runtime_mode="local-demo", object_storage_provider="mock")
    )

    payload = check.as_dict()
    assert payload["key"] == "mock_guardrails"
    assert payload["status"] == "degraded"
    assert payload["details"]["violation_count"] >= 1
    assert any(v["key"] == "OBJECT_STORAGE_PROVIDER" for v in payload["details"]["violations"])


def test_readiness_mock_guardrails_reports_ready_for_development_demo():
    check = build_mock_guardrails_check(_settings(app_env="development", app_runtime_mode="local-demo"))

    assert check.as_dict()["status"] == "ready"


def test_system_readiness_endpoint_includes_mock_guardrails(monkeypatch):
    from importlib import reload

    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("APP_RUNTIME_MODE", "local-demo")
    monkeypatch.setenv("OBJECT_STORAGE_PROVIDER", "mock")
    monkeypatch.setenv("APP_RATE_LIMIT_PER_MINUTE", "0")

    import app.core.config as config
    import app.main as main

    reload(config)
    reload(main)
    client = TestClient(main.create_app())

    response = client.get("/api/v2/system/readiness")

    assert response.status_code == 200
    body = response.json()["data"]
    assert body["overall_status"] == "degraded"
    check = next(item for item in body["checks"] if item["key"] == "mock_guardrails")
    assert check["status"] == "degraded"
    assert check["details"]["violation_count"] >= 1


def test_production_phone_code_rejects_888888_even_with_seeded_account(monkeypatch, tmp_path):
    database_url = f"sqlite:///{(tmp_path / 'prod-login.db').as_posix()}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("APP_RUNTIME_MODE", "production")
    monkeypatch.setenv("SEED_OWNER_EMAIL", "owner@example.com")
    upgrade_test_database(database_url)

    session = get_session_factory()()
    salt_hex = "22" * 16
    session.add(
        V2Account(
            account_id="acct_prod_phone",
            email="owner@example.com",
            display_name="Owner",
            password_hash=hash_v2_password("dev-password", salt_hex),
            password_salt=salt_hex,
            status="active",
        )
    )
    session.commit()
    session.close()

    client = TestClient(load_create_app()())
    response = client.post(
        "/api/v2/auth/login",
        json={"auth_method": "phone_code", "phone": "13800000000", "verification_code": "888888"},
    )

    assert response.status_code == 401
