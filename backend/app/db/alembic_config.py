from __future__ import annotations

import os


def _has_mysql_env() -> bool:
    return any(
        os.getenv(name)
        for name in ("MYSQL_HOST", "MYSQL_DATABASE", "MYSQL_USER", "MYSQL_PASSWORD", "MYSQL_PORT")
    )


def _build_mysql_database_url_from_env() -> str:
    mysql_user = os.getenv("MYSQL_USER", "aism")
    mysql_password = os.getenv("MYSQL_PASSWORD", "aism_password")
    mysql_host = os.getenv("MYSQL_HOST", "mysql")
    mysql_port = os.getenv("MYSQL_PORT", "3306")
    mysql_database = os.getenv("MYSQL_DATABASE", "ai_store_manager")
    return (
        f"mysql+pymysql://{mysql_user}:{mysql_password}"
        f"@{mysql_host}:{mysql_port}/{mysql_database}?charset=utf8mb4"
    )


def resolve_alembic_database_url(default_url: str) -> str:
    configured_url = os.getenv("DATABASE_URL", "").strip()
    if configured_url:
        return configured_url
    if _has_mysql_env():
        return _build_mysql_database_url_from_env()
    return default_url
