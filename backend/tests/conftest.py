import importlib.util
from pathlib import Path
import sys

from alembic import command
from alembic.config import Config
import pytest
from fastapi.testclient import TestClient

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
def client(monkeypatch, tmp_path) -> TestClient:
    database_url = f"sqlite:///{(tmp_path / 'api.db').as_posix()}"
    monkeypatch.setenv("DATABASE_URL", database_url)

    upgrade_test_database(database_url)

    return TestClient(load_create_app()())
