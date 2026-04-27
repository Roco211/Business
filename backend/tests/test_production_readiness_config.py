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
    import logging

    caplog.set_level(logging.ERROR, logger="app.main")
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


def test_redis_rate_limiter_allows_until_limit_then_blocks():
    from app.core.production_middleware import RedisRateLimiter

    class FakeRedis:
        def __init__(self):
            self.values = {}
            self.expirations = {}

        def incr(self, key):
            self.values[key] = self.values.get(key, 0) + 1
            return self.values[key]

        def expire(self, key, seconds):
            self.expirations[key] = seconds

    fake = FakeRedis()
    limiter = RedisRateLimiter(limit_per_minute=2, redis_client=fake, key_prefix="business:test")

    assert limiter.allow("client-a") is True
    assert limiter.allow("client-a") is True
    assert limiter.allow("client-a") is False
    assert any(key.startswith("business:test:client-a:") for key in fake.values)
    assert all("redis://" not in key and "secret" not in key for key in fake.values)


def test_create_rate_limiter_uses_redis_backend_when_configured(monkeypatch):
    monkeypatch.setenv("APP_RATE_LIMIT_PER_MINUTE", "120")
    monkeypatch.setenv("APP_RATE_LIMIT_BACKEND", "redis")
    monkeypatch.setenv("REDIS_URL", "redis://:secret@redis:6379/0")

    import app.core.config as config
    from app.core.production_middleware import RedisRateLimiter, create_rate_limiter

    reload(config)
    settings = config.get_settings()
    limiter = create_rate_limiter(settings)

    assert isinstance(limiter, RedisRateLimiter)
    assert "secret" not in limiter.key_prefix


def test_sanitize_for_log_redacts_sensitive_values():
    from app.core.observability import sanitize_for_log

    payload = {
        "Authorization": "Bearer should-not-leak",
        "nested": {
            "password": "plain-password",
            "api_key": "provider-key",
            "redis_url": "redis://:secret@redis:6379/0",
            "safe": "visible",
        },
        "message": "failed with token=abc123 and password=secret-value",
    }

    sanitized = sanitize_for_log(payload)

    assert sanitized["Authorization"] == "[REDACTED]"
    assert sanitized["nested"]["password"] == "[REDACTED]"
    assert sanitized["nested"]["api_key"] == "[REDACTED]"
    assert sanitized["nested"]["redis_url"] == "[REDACTED]"
    assert sanitized["nested"]["safe"] == "visible"
    assert "abc123" not in sanitized["message"]
    assert "secret-value" not in sanitized["message"]
    assert "[REDACTED]" in sanitized["message"]


def test_app_emits_structured_request_log_with_request_id(monkeypatch, caplog):
    import logging

    caplog.set_level(logging.INFO, logger="app.main")
    monkeypatch.setenv("APP_RATE_LIMIT_PER_MINUTE", "0")
    monkeypatch.setenv("APP_SECURITY_HEADERS_ENABLED", "0")
    monkeypatch.setenv("APP_STRUCTURED_LOGGING_ENABLED", "1")

    import app.core.config as config
    import app.main as main

    reload(config)
    reload(main)
    client = TestClient(main.create_app())

    response = client.get("/api/v2/health", headers={"X-Request-ID": "req_k4_success"})

    assert response.status_code == 200
    assert response.headers["x-request-id"] == "req_k4_success"
    request_logs = [
        record.structured_payload
        for record in caplog.records
        if hasattr(record, "structured_payload") and record.structured_payload.get("event") == "http_request"
    ]
    assert request_logs
    payload = request_logs[-1]
    assert payload["request_id"] == "req_k4_success"
    assert payload["method"] == "GET"
    assert payload["path"] == "/api/v2/health"
    assert payload["status_code"] == "200"
    assert float(payload["latency_ms"]) >= 0


def test_app_logs_unhandled_errors_with_sanitized_structured_payload(monkeypatch, caplog):
    import logging

    caplog.set_level(logging.ERROR, logger="app.main")
    monkeypatch.setenv("APP_RATE_LIMIT_PER_MINUTE", "0")
    monkeypatch.setenv("APP_SECURITY_HEADERS_ENABLED", "0")
    monkeypatch.setenv("APP_STRUCTURED_LOGGING_ENABLED", "1")

    import app.core.config as config
    import app.main as main

    reload(config)
    reload(main)
    app = main.create_app()

    @app.get("/boom-for-k4-sanitized-log-test")
    def boom_for_k4_sanitized_log_test():
        raise RuntimeError("provider failed token=abc123 password=secret-value")

    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/boom-for-k4-sanitized-log-test", headers={"X-Request-ID": "req_k4_error"})

    assert response.status_code == 500
    response_text = response.text
    assert "abc123" not in response_text
    assert "secret-value" not in response_text
    assert response.headers["x-request-id"] == "req_k4_error"

    error_logs = [
        record.structured_payload
        for record in caplog.records
        if hasattr(record, "structured_payload") and record.structured_payload.get("event") == "http_request_error"
    ]
    assert error_logs
    payload = error_logs[-1]
    assert payload["request_id"] == "req_k4_error"
    assert payload["path"] == "/boom-for-k4-sanitized-log-test"
    assert payload["status_code"] == "500"
    assert payload["exception_type"] == "RuntimeError"
    assert "abc123" not in str(payload)
    assert "secret-value" not in str(payload)
