from sqlalchemy import text

from app.core.config import get_settings
from app.db.session import create_engine_from_settings


def test_settings_support_database_url(monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./phase2-test.db")

    settings = get_settings()

    assert settings.database_url == "sqlite:///./phase2-test.db"


def test_create_engine_from_sqlite_settings(monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "sqlite+pysqlite:///:memory:")

    engine = create_engine_from_settings(get_settings())

    with engine.connect() as connection:
        assert connection.execute(text("select 1")).scalar_one() == 1
