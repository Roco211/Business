from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import get_settings


def test_mock_login_returns_default_owner_context(client) -> None:
    response = client.post("/api/v1/auth/mock-login", json={"shop_id": "shop_default"})

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["access_token"] == "mock_owner_token"
    assert payload["owner_actor_id"] == "owner_default"
    assert payload["shop_id"] == "shop_default"


def test_mock_login_uses_default_shop_when_request_omits_shop_id(client) -> None:
    response = client.post("/api/v1/auth/mock-login", json={})

    assert response.status_code == 200
    assert response.json()["data"]["shop_id"] == "shop_default"


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
