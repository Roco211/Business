from __future__ import annotations

import os
from importlib import reload

from fastapi.testclient import TestClient


def test_settings_support_postgres_and_production_security_env(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://business:secret@postgres:5432/business")
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("APP_CORS_ORIGINS", "https://app.example.com,https://admin.example.com")
    monkeypatch.setenv("APP_RATE_LIMIT_PER_MINUTE", "120")
    monkeypatch.setenv("APP_SECURITY_HEADERS_ENABLED", "1")

    import app.core.config as config

    reload(config)
    settings = config.get_settings()

    assert settings.database_url.startswith("postgresql+psycopg://")
    assert settings.cors_origins() == ["https://app.example.com", "https://admin.example.com"]
    assert settings.rate_limit_per_minute == 120
    assert settings.security_headers_enabled is True


def test_app_adds_cors_security_headers_and_rate_limit(monkeypatch):
    monkeypatch.setenv("APP_CORS_ORIGINS", "https://app.example.com")
    monkeypatch.setenv("APP_RATE_LIMIT_PER_MINUTE", "2")
    monkeypatch.setenv("APP_SECURITY_HEADERS_ENABLED", "1")

    import app.core.config as config
    import app.main as main

    reload(config)
    reload(main)
    client = TestClient(main.create_app())

    first = client.get("/api/v2/health", headers={"Origin": "https://app.example.com"})
    second = client.get("/api/v2/health", headers={"Origin": "https://app.example.com"})
    third = client.get("/api/v2/health", headers={"Origin": "https://app.example.com"})

    assert first.status_code == 200
    assert first.headers["access-control-allow-origin"] == "https://app.example.com"
    assert first.headers["x-content-type-options"] == "nosniff"
    assert first.headers["x-frame-options"] == "DENY"
    assert second.status_code == 200
    assert third.status_code == 429
    assert third.json()["error"]["code"] == "rate_limited"


def test_app_logs_unhandled_errors_with_request_id(monkeypatch, caplog):
    monkeypatch.setenv("APP_RATE_LIMIT_PER_MINUTE", "0")
    monkeypatch.setenv("APP_SECURITY_HEADERS_ENABLED", "0")

    import app.core.config as config
    import app.main as main

    reload(config)
    reload(main)
    app = main.create_app()

    @app.get("/boom-for-error-log-test")
    def boom_for_error_log_test():
        raise RuntimeError("boom for log")

    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/boom-for-error-log-test")

    assert response.status_code == 500
    body = response.json()
    assert body["error"]["code"] == "internal_server_error"
    assert body["error"]["message"] == "Internal server error"
    assert body["error"]["details"][0]["field"] == "request_id"
    request_id = body["error"]["details"][0]["message"]
    assert request_id
    assert response.headers["x-request-id"] == request_id
    assert any("Unhandled request error" in record.message and request_id in record.message for record in caplog.records)
