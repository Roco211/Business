from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from app.core.config import Settings


def create_engine_from_settings(settings: Settings) -> Engine:
    connect_args: dict[str, bool] = {}
    if settings.database_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False

    return create_engine(
        settings.database_url,
        future=True,
        pool_pre_ping=True,
        connect_args=connect_args,
    )
