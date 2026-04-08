import importlib.util
from collections.abc import Iterator
import os
from pathlib import Path
import sys

from alembic import command
from alembic.config import Config
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.session import get_engine, get_session_factory


def load_create_app():
    backend_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(backend_root))
    sys.modules.pop("app", None)
    main_path = backend_root / "app" / "main.py"
    spec = importlib.util.spec_from_file_location("foundation_backend_main", main_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load backend app module")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.create_app


def upgrade_test_database(database_url: str) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    config = Config(str(repo_root / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(config, "head")


@pytest.fixture(autouse=True)
def clear_db_caches() -> None:
    get_engine.cache_clear()
    get_session_factory.cache_clear()


@pytest.fixture
def database_url(tmp_path) -> str:
    return f"sqlite:///{(tmp_path / 'test.db').as_posix()}"


@pytest.fixture
def db_session(monkeypatch, database_url) -> Iterator[Session]:
    monkeypatch.setenv("DATABASE_URL", database_url)

    upgrade_test_database(database_url)

    engine = get_engine()
    session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
        get_engine.cache_clear()
        get_session_factory.cache_clear()


@pytest.fixture
def client(monkeypatch, tmp_path) -> TestClient:
    database_url = f"sqlite:///{(tmp_path / 'api.db').as_posix()}"
    monkeypatch.setenv("DATABASE_URL", database_url)

    upgrade_test_database(database_url)

    return TestClient(load_create_app()())


def login_and_get_token(
    client: TestClient,
    monkeypatch=None,
    *,
    email: str = "owner@example.com",
    password: str = "dev-password",
) -> str:
    if monkeypatch is not None:
        monkeypatch.setenv("SEED_OWNER_EMAIL", email)
        monkeypatch.setenv("SEED_OWNER_PASSWORD", password)
    else:
        os.environ["SEED_OWNER_EMAIL"] = email
        os.environ["SEED_OWNER_PASSWORD"] = password

    response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )

    assert response.status_code == 200
    return response.json()["data"]["access_token"]


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}
