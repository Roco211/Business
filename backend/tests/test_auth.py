from pathlib import Path
import sys

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.api.routes.auth import router as auth_router
from app.db.session import get_db_session
from app.models import SessionRecord

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import get_settings


def test_mock_login_endpoint_is_not_available(client) -> None:
    response = client.post("/api/v1/auth/mock-login", json={"shop_id": "shop_default"})

    assert response.status_code == 404


def test_get_settings_reads_environment_overrides(monkeypatch) -> None:
    monkeypatch.setenv("DEFAULT_SHOP_ID", "shop_env")
    monkeypatch.setenv("DEFAULT_OWNER_ACTOR_ID", "owner_env")
    monkeypatch.setenv("DEFAULT_SESSION_ID", "sess_env")
    monkeypatch.setenv("REDIS_URL", "redis://cache:6379/1")

    settings = get_settings()

    assert settings.default_shop_id == "shop_env"
    assert settings.default_owner_actor_id == "owner_env"
    assert settings.default_session_id == "sess_env"
    assert settings.redis_url == "redis://cache:6379/1"


def test_login_returns_opaque_bearer_token(client, monkeypatch) -> None:
    monkeypatch.setenv("SEED_OWNER_EMAIL", "owner@example.com")
    monkeypatch.setenv("SEED_OWNER_PASSWORD", "dev-password")

    response = client.post(
        "/api/v1/auth/login",
        json={"email": "owner@example.com", "password": "dev-password"},
    )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["token_type"] == "Bearer"
    assert payload["access_token"] != "mock_owner_token"
    assert payload["shop_id"] == "shop_default"


def test_login_rejects_invalid_password(client, monkeypatch) -> None:
    monkeypatch.setenv("SEED_OWNER_EMAIL", "owner@example.com")
    monkeypatch.setenv("SEED_OWNER_PASSWORD", "dev-password")

    response = client.post(
        "/api/v1/auth/login",
        json={"email": "owner@example.com", "password": "wrong-password"},
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


def test_login_does_not_create_default_session_record(db_session, monkeypatch) -> None:
    monkeypatch.setenv("SEED_OWNER_EMAIL", "owner@example.com")
    monkeypatch.setenv("SEED_OWNER_PASSWORD", "dev-password")

    app = FastAPI()
    app.include_router(auth_router)
    app.dependency_overrides[get_db_session] = lambda: db_session
    client = TestClient(app)

    before_count = db_session.scalar(select(func.count()).select_from(SessionRecord)) or 0

    response = client.post(
        "/api/v1/auth/login",
        json={"email": "owner@example.com", "password": "dev-password"},
    )

    after_count = db_session.scalar(select(func.count()).select_from(SessionRecord)) or 0

    assert response.status_code == 200
    assert before_count == 0
    assert after_count == 0


def test_login_issued_token_is_accepted_by_protected_routes(client, monkeypatch) -> None:
    monkeypatch.setenv("SEED_OWNER_EMAIL", "owner@example.com")
    monkeypatch.setenv("SEED_OWNER_PASSWORD", "dev-password")
    login_response = client.post(
        "/api/v1/auth/login",
        json={"email": "owner@example.com", "password": "dev-password"},
    )

    assert login_response.status_code == 200
    token = login_response.json()["data"]["access_token"]

    protected_response = client.post(
        "/api/v1/sessions/bootstrap",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert protected_response.status_code == 200
    assert protected_response.json()["data"]["session_id"] == "sess_default"
