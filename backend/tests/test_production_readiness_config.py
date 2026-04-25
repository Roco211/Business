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
