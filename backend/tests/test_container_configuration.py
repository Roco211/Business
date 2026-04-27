from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

from app.core.config import Settings
from app.db.alembic_config import resolve_alembic_database_url


def test_resolve_alembic_database_url_prefers_database_url_env(monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "mysql+pymysql://aism:secret@mysql:3306/ai_store_manager")

    resolved = resolve_alembic_database_url("sqlite:///./aism-dev.db")

    assert resolved == "mysql+pymysql://aism:secret@mysql:3306/ai_store_manager"


def test_resolve_alembic_database_url_falls_back_to_alembic_default(monkeypatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)

    resolved = resolve_alembic_database_url("sqlite:///./aism-dev.db")

    assert resolved == "sqlite:///./aism-dev.db"


def test_resolve_alembic_database_url_builds_mysql_url_from_mysql_env(monkeypatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("MYSQL_USER", "aism")
    monkeypatch.setenv("MYSQL_PASSWORD", "aism_password")
    monkeypatch.setenv("MYSQL_HOST", "mysql")
    monkeypatch.setenv("MYSQL_PORT", "3306")
    monkeypatch.setenv("MYSQL_DATABASE", "ai_store_manager")

    resolved = resolve_alembic_database_url("sqlite:///./aism-dev.db")

    assert resolved == "mysql+pymysql://aism:aism_password@mysql:3306/ai_store_manager?charset=utf8mb4"


def test_backend_dockerfile_preserves_runtime_layout_for_alembic_and_h5() -> None:
    dockerfile = Path("backend/Dockerfile").read_text(encoding="utf-8")

    assert "WORKDIR /app" in dockerfile
    assert "COPY backend/ ." in dockerfile
    assert "COPY --from=h5-builder /workspace/apps/h5/dist /app/app/static/h5" in dockerfile


def test_settings_direct_construction_defaults_pending_poll_seconds() -> None:
    settings = Settings(
        app_env="test",
        app_host="127.0.0.1",
        app_port=8001,
        redis_url="redis://localhost:6379/0",
        database_url="sqlite:///tmp.db",
        session_stream_keepalive_seconds=20.0,
    )

    assert settings.session_stream_pending_poll_seconds == 1.0


def test_alembic_upgrade_uses_database_url_env_override(monkeypatch, tmp_path) -> None:
    database_path = tmp_path / "docker-migrator.db"
    database_url = f"sqlite:///{database_path.as_posix()}"
    monkeypatch.setenv("DATABASE_URL", database_url)

    config = Config("alembic.ini")

    command.upgrade(config, "head")

    engine = create_engine(database_url, future=True)
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())
    assert "v2_shops" in table_names
    assert "v2_accounts" in table_names
    assert "shops" not in table_names
