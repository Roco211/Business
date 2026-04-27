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


def test_settings_build_default_database_url_from_postgres_parts(monkeypatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("POSTGRES_USER", "tester")
    monkeypatch.setenv("POSTGRES_PASSWORD", "secret")
    monkeypatch.setenv("POSTGRES_HOST", "postgres-db")
    monkeypatch.setenv("POSTGRES_PORT", "5433")
    monkeypatch.setenv("POSTGRES_DB", "business_test")

    settings = get_settings()

    assert settings.database_url == (
        "postgresql+psycopg://tester:secret@postgres-db:5433/business_test"
    )
