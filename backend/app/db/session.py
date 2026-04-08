from functools import lru_cache
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings, get_settings


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


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    return create_engine_from_settings(get_settings())


@lru_cache(maxsize=1)
def get_session_factory() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False)


def get_db_session() -> Generator[Session, None, None]:
    session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()
