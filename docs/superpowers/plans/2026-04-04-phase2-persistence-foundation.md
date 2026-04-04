# Phase 2 Persistence Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the minimum SQLAlchemy + Alembic persistence foundation so the backend can bootstrap a default shop and default workgroup session from the database instead of config-only mocks.

**Architecture:** Introduce a dedicated database layer, first ORM models for `shops` and `sessions`, and an idempotent bootstrap service that materializes default records on demand. Keep the external API stable by rewiring the existing mock auth and session bootstrap routes to use persisted records while leaving runtime, WebSocket, messages, and task orchestration for later phases.

**Tech Stack:** Python, FastAPI, SQLAlchemy, Alembic, pytest, SQLite (tests), MySQL-oriented schema design, Docker Compose

---

### Task 1: Add database settings and session infrastructure

**Files:**
- Modify: `backend/requirements.txt`
- Modify: `backend/app/core/config.py`
- Create: `backend/app/db/__init__.py`
- Create: `backend/app/db/base.py`
- Create: `backend/app/db/session.py`
- Modify: `backend/tests/conftest.py`
- Create: `backend/tests/test_db_session.py`

- [ ] **Step 1: Write the failing DB settings/session tests**

`backend/tests/test_db_session.py`

```python
from sqlalchemy import text

from app.core.config import get_settings
from app.db.session import create_engine_from_settings


def test_settings_support_database_url(monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./phase2-test.db")
    get_settings.cache_clear()

    settings = get_settings()

    assert settings.database_url == "sqlite:///./phase2-test.db"


def test_create_engine_from_sqlite_settings(monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "sqlite+pysqlite:///:memory:")
    get_settings.cache_clear()

    engine = create_engine_from_settings(get_settings())

    with engine.connect() as connection:
        assert connection.execute(text("select 1")).scalar_one() == 1
```

- [ ] **Step 2: Run the new tests to verify they fail before implementation**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_db_session.py -q
```

Expected:

- import failure for `app.db.session`
- or missing `database_url` on settings

- [ ] **Step 3: Add the database dependencies**

`backend/requirements.txt`

```txt
fastapi==0.115.12
uvicorn==0.34.0
pydantic==2.11.3
celery==5.4.0
pytest==8.3.5
httpx==0.28.1
SQLAlchemy==2.0.39
alembic==1.15.2
PyMySQL==1.1.1
```

- [ ] **Step 4: Extend settings with database configuration and cache control**

`backend/app/core/config.py`

```python
from dataclasses import dataclass
from functools import lru_cache
import os


@dataclass(frozen=True)
class Settings:
    app_env: str
    app_host: str
    app_port: int
    redis_url: str
    database_url: str
    default_shop_id: str
    default_owner_actor_id: str
    default_session_id: str


def _build_default_database_url() -> str:
    mysql_user = os.getenv("MYSQL_USER", "aism")
    mysql_password = os.getenv("MYSQL_PASSWORD", "aism_password")
    mysql_host = os.getenv("MYSQL_HOST", "mysql")
    mysql_port = os.getenv("MYSQL_PORT", "3306")
    mysql_database = os.getenv("MYSQL_DATABASE", "ai_store_manager")
    return (
        f"mysql+pymysql://{mysql_user}:{mysql_password}"
        f"@{mysql_host}:{mysql_port}/{mysql_database}?charset=utf8mb4"
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings(
        app_env=os.getenv("APP_ENV", "development"),
        app_host=os.getenv("APP_HOST", "0.0.0.0"),
        app_port=int(os.getenv("APP_PORT", "8001")),
        redis_url=os.getenv("REDIS_URL", "redis://redis:6379/0"),
        database_url=os.getenv("DATABASE_URL", _build_default_database_url()),
        default_shop_id=os.getenv("DEFAULT_SHOP_ID", "shop_default"),
        default_owner_actor_id=os.getenv("DEFAULT_OWNER_ACTOR_ID", "owner_default"),
        default_session_id=os.getenv("DEFAULT_SESSION_ID", "sess_default"),
    )
```

- [ ] **Step 5: Add the DB base and session helpers**

`backend/app/db/base.py`

```python
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base class for ORM models."""
```

`backend/app/db/session.py`

```python
from functools import lru_cache
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings, get_settings


def create_engine_from_settings(settings: Settings) -> Engine:
    connect_args = {}
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
```

`backend/app/db/__init__.py`

```python
"""Database infrastructure package."""
```

- [ ] **Step 6: Refresh the shared test fixture to clear caches between tests**

`backend/tests/conftest.py`

```python
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.db.session import get_engine, get_session_factory
from app.main import create_app


@pytest.fixture(autouse=True)
def clear_cached_settings() -> Iterator[None]:
    get_settings.cache_clear()
    get_engine.cache_clear()
    get_session_factory.cache_clear()
    yield
    get_settings.cache_clear()
    get_engine.cache_clear()
    get_session_factory.cache_clear()


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app())
```

- [ ] **Step 7: Re-run the DB session tests to verify the infrastructure works**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_db_session.py -q
```

Expected:

- `2 passed`

- [ ] **Step 8: Commit**

```bash
git add backend/requirements.txt backend/app/core/config.py backend/app/db backend/tests/conftest.py backend/tests/test_db_session.py
git commit -m "feat: add database session foundation"
```

### Task 2: Add ORM models and the first Alembic migration

**Files:**
- Create: `backend/app/models/__init__.py`
- Create: `backend/app/models/shop.py`
- Create: `backend/app/models/session_record.py`
- Create: `alembic.ini`
- Create: `backend/alembic/env.py`
- Create: `backend/alembic/script.py.mako`
- Create: `backend/alembic/versions/20260404_01_create_shops_and_sessions.py`
- Create: `backend/tests/test_alembic_bootstrap.py`

- [ ] **Step 1: Write the failing migration verification test**

`backend/tests/test_alembic_bootstrap.py`

```python
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect


def test_alembic_upgrade_creates_shops_and_sessions(tmp_path) -> None:
    database_path = tmp_path / "alembic.db"
    database_url = f"sqlite:///{database_path.as_posix()}"

    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", database_url)

    command.upgrade(config, "head")

    engine = create_engine(database_url, future=True)
    inspector = inspect(engine)

    assert "shops" in inspector.get_table_names()
    assert "sessions" in inspector.get_table_names()
```

- [ ] **Step 2: Run the migration test to verify it fails before Alembic exists**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_alembic_bootstrap.py -q
```

Expected:

- `alembic.ini` missing
- or Alembic env import failure

- [ ] **Step 3: Add the initial ORM models**

`backend/app/models/shop.py`

```python
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Shop(Base):
    __tablename__ = "shops"

    shop_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    owner_name: Mapped[str] = mapped_column(String(80), nullable=False)
    industry: Mapped[str] = mapped_column(String(32), nullable=False)
    locale: Mapped[str] = mapped_column(String(16), nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False)
    require_price_confirmation: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    require_new_item_confirmation: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    low_confidence_threshold: Mapped[float] = mapped_column(Numeric(5, 4), nullable=False, default=0.8500)
    default_low_stock_threshold: Mapped[float | None] = mapped_column(Numeric(12, 3), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)
```

`backend/app/models/session_record.py`

```python
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, JSON, BigInteger, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class SessionRecord(Base):
    __tablename__ = "sessions"

    session_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    shop_id: Mapped[str] = mapped_column(ForeignKey("shops.shop_id"), nullable=False)
    session_type: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    participants: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    last_event_seq: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    last_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)

    shop = relationship("Shop")
```

`backend/app/models/__init__.py`

```python
from app.models.session_record import SessionRecord
from app.models.shop import Shop

__all__ = ["SessionRecord", "Shop"]
```

- [ ] **Step 4: Add the Alembic configuration and initial migration**

`alembic.ini`

```ini
[alembic]
script_location = backend/alembic
prepend_sys_path = backend
sqlalchemy.url = sqlite:///./aism-dev.db

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers = console
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
```

`backend/alembic/env.py`

```python
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.db.base import Base
from app.models import Shop, SessionRecord  # noqa: F401

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

`backend/alembic/script.py.mako`

```mako
"""${message}"""

revision = ${repr(up_revision)}
down_revision = ${repr(down_revision)}
branch_labels = ${repr(branch_labels)}
depends_on = ${repr(depends_on)}

from alembic import op
import sqlalchemy as sa


def upgrade() -> None:
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    ${downgrades if downgrades else "pass"}
```

`backend/alembic/versions/20260404_01_create_shops_and_sessions.py`

```python
"""create shops and sessions tables"""

from alembic import op
import sqlalchemy as sa


revision = "20260404_01"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "shops",
        sa.Column("shop_id", sa.String(length=40), primary_key=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("owner_name", sa.String(length=80), nullable=False),
        sa.Column("industry", sa.String(length=32), nullable=False),
        sa.Column("locale", sa.String(length=16), nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        sa.Column("require_price_confirmation", sa.Boolean(), nullable=False),
        sa.Column("require_new_item_confirmation", sa.Boolean(), nullable=False),
        sa.Column("low_confidence_threshold", sa.Numeric(5, 4), nullable=False),
        sa.Column("default_low_stock_threshold", sa.Numeric(12, 3), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "sessions",
        sa.Column("session_id", sa.String(length=40), primary_key=True),
        sa.Column("shop_id", sa.String(length=40), sa.ForeignKey("shops.shop_id"), nullable=False),
        sa.Column("session_type", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("participants", sa.JSON(), nullable=False),
        sa.Column("last_event_seq", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("last_message_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("sessions")
    op.drop_table("shops")
```

- [ ] **Step 5: Re-run the Alembic test to verify the migration works**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_alembic_bootstrap.py -q
```

Expected:

- `1 passed`

- [ ] **Step 6: Commit**

```bash
git add alembic.ini backend/alembic backend/app/models backend/tests/test_alembic_bootstrap.py
git commit -m "feat: add shops and sessions persistence models"
```

### Task 3: Add the default bootstrap service and wire the routes to persistence

**Files:**
- Create: `backend/app/services/__init__.py`
- Create: `backend/app/services/bootstrap.py`
- Modify: `backend/app/api/routes/auth.py`
- Modify: `backend/app/api/routes/sessions.py`
- Modify: `backend/tests/test_auth.py`
- Modify: `backend/tests/test_sessions.py`
- Create: `backend/tests/test_bootstrap_service.py`
- Modify: `backend/tests/conftest.py`

- [ ] **Step 1: Write the failing bootstrap service tests**

`backend/tests/test_bootstrap_service.py`

```python
from sqlalchemy import select

from app.models.session_record import SessionRecord
from app.models.shop import Shop
from app.services.bootstrap import ensure_default_context


def test_ensure_default_context_creates_shop_and_session(db_session) -> None:
    context = ensure_default_context(db_session)

    assert context.shop.shop_id == "shop_default"
    assert context.session.session_id == "sess_default"

    shops = db_session.scalars(select(Shop)).all()
    sessions = db_session.scalars(select(SessionRecord)).all()
    assert len(shops) == 1
    assert len(sessions) == 1


def test_ensure_default_context_is_idempotent(db_session) -> None:
    first = ensure_default_context(db_session)
    second = ensure_default_context(db_session)

    assert first.shop.shop_id == second.shop.shop_id
    assert first.session.session_id == second.session.session_id
```

- [ ] **Step 2: Run the bootstrap tests to verify they fail before the service exists**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_bootstrap_service.py -q
```

Expected:

- import failure for `app.services.bootstrap`

- [ ] **Step 3: Add a database session test fixture and the bootstrap service**

`backend/tests/conftest.py`

```python
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.db.base import Base
from app.db.session import get_engine, get_session_factory
from app.main import create_app
from app.models import SessionRecord, Shop  # noqa: F401


@pytest.fixture(autouse=True)
def clear_cached_settings() -> Iterator[None]:
    get_settings.cache_clear()
    get_engine.cache_clear()
    get_session_factory.cache_clear()
    yield
    get_settings.cache_clear()
    get_engine.cache_clear()
    get_session_factory.cache_clear()


@pytest.fixture
def db_session(monkeypatch, tmp_path) -> Iterator[Session]:
    database_url = f"sqlite:///{(tmp_path / 'test.db').as_posix()}"
    monkeypatch.setenv("DATABASE_URL", database_url)

    engine = create_engine(database_url, future=True, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    session = factory()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture
def client(monkeypatch, tmp_path) -> TestClient:
    database_url = f"sqlite:///{(tmp_path / 'api.db').as_posix()}"
    monkeypatch.setenv("DATABASE_URL", database_url)

    engine = create_engine(database_url, future=True, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    engine.dispose()

    return TestClient(create_app())
```

`backend/app/services/bootstrap.py`

```python
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.session_record import SessionRecord
from app.models.shop import Shop


@dataclass(frozen=True)
class BootstrapContext:
    shop: Shop
    session: SessionRecord


def ensure_default_context(db_session: Session) -> BootstrapContext:
    settings = get_settings()
    now = datetime.now(UTC).replace(tzinfo=None)

    shop = db_session.get(Shop, settings.default_shop_id)
    if shop is None:
        shop = Shop(
            shop_id=settings.default_shop_id,
            name="演示店铺",
            owner_name="默认老板",
            industry="retail",
            locale="zh-CN",
            timezone="Asia/Shanghai",
            require_price_confirmation=True,
            require_new_item_confirmation=True,
            low_confidence_threshold=0.8500,
            default_low_stock_threshold=None,
            created_at=now,
            updated_at=now,
        )
        db_session.add(shop)
        db_session.flush()

    session_record = db_session.get(SessionRecord, settings.default_session_id)
    if session_record is None:
        session_record = SessionRecord(
            session_id=settings.default_session_id,
            shop_id=shop.shop_id,
            session_type="workgroup",
            title="数字员工工作群",
            participants=["xiaoya", "laoli"],
            last_event_seq=0,
            last_message_at=None,
            created_at=now,
            updated_at=now,
        )
        db_session.add(session_record)
        db_session.flush()

    db_session.commit()
    return BootstrapContext(shop=shop, session=session_record)
```

`backend/app/services/__init__.py`

```python
"""Application services."""
```

- [ ] **Step 4: Rewire the auth and session routes to use the DB-backed bootstrap service**

`backend/app/api/routes/auth.py`

```python
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.contracts.auth import MockLoginData, MockLoginRequest
from app.contracts.common import DataEnvelope
from app.core.config import Settings, get_settings
from app.db.session import get_db_session
from app.services.bootstrap import ensure_default_context

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/mock-login", response_model=DataEnvelope[MockLoginData])
def mock_login(
    payload: MockLoginRequest,
    settings: Settings = Depends(get_settings),
    db_session: Session = Depends(get_db_session),
) -> DataEnvelope[MockLoginData]:
    context = ensure_default_context(db_session)
    shop = context.shop

    requested_shop_id = payload.shop_id or settings.default_shop_id
    if requested_shop_id != shop.shop_id:
        requested_shop_id = shop.shop_id

    return DataEnvelope(
        data=MockLoginData(
            access_token="mock_owner_token",
            token_type="Bearer",
            owner_actor_id=settings.default_owner_actor_id,
            shop_id=requested_shop_id,
            shop_name=shop.name,
        )
    )
```

`backend/app/api/routes/sessions.py`

```python
from fastapi import APIRouter, Depends, Header, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.contracts.common import DataEnvelope, ErrorBody, ErrorDetail, ErrorEnvelope
from app.contracts.session import SessionBootstrapData
from app.core.config import Settings, get_settings
from app.db.session import get_db_session
from app.services.bootstrap import ensure_default_context

router = APIRouter(prefix="/api/v1/sessions", tags=["sessions"])


@router.post(
    "/bootstrap",
    response_model=DataEnvelope[SessionBootstrapData],
    responses={
        401: {
            "model": ErrorEnvelope,
            "description": "Unauthorized",
        }
    },
)
def bootstrap_session(
    authorization: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
    db_session: Session = Depends(get_db_session),
) -> DataEnvelope[SessionBootstrapData] | JSONResponse:
    if authorization != "Bearer mock_owner_token":
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content=ErrorEnvelope(
                error=ErrorBody(
                    code="unauthorized",
                    message="Authorization token is missing or invalid.",
                    details=[ErrorDetail(field="Authorization", message="Expected Bearer mock_owner_token")],
                )
            ).model_dump(),
        )

    context = ensure_default_context(db_session)
    session_record = context.session

    return DataEnvelope(
        data=SessionBootstrapData(
            session_id=session_record.session_id,
            session_type=session_record.session_type,
            title=session_record.title,
            participants=session_record.participants,
        )
    )
```

- [ ] **Step 5: Update the route tests to verify persisted bootstrap behavior**

`backend/tests/test_auth.py`

```python
from sqlalchemy import select

from app.models.shop import Shop


def test_mock_login_returns_default_owner_context(client) -> None:
    response = client.post("/api/v1/auth/mock-login", json={"shop_id": "shop_default"})

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["access_token"] == "mock_owner_token"
    assert payload["owner_actor_id"] == "owner_default"
    assert payload["shop_id"] == "shop_default"


def test_mock_login_uses_env_default_when_shop_id_omitted(client) -> None:
    response = client.post("/api/v1/auth/mock-login", json={})

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["shop_id"] == "shop_default"
    assert payload["shop_name"] == "演示店铺"
```

`backend/tests/test_sessions.py`

```python
def test_session_bootstrap_returns_default_workgroup(client) -> None:
    response = client.post(
        "/api/v1/sessions/bootstrap",
        headers={"Authorization": "Bearer mock_owner_token"},
    )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["session_id"] == "sess_default"
    assert payload["session_type"] == "workgroup"
    assert payload["participants"] == ["xiaoya", "laoli"]


def test_session_bootstrap_requires_authorization(client) -> None:
    response = client.post("/api/v1/sessions/bootstrap")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"
```

- [ ] **Step 6: Run the service and route tests**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_bootstrap_service.py backend/tests/test_auth.py backend/tests/test_sessions.py -q
```

Expected:

- all tests pass

- [ ] **Step 7: Commit**

```bash
git add backend/app/services backend/app/api/routes/auth.py backend/app/api/routes/sessions.py backend/tests/conftest.py backend/tests/test_bootstrap_service.py backend/tests/test_auth.py backend/tests/test_sessions.py
git commit -m "feat: persist default shop and bootstrap session"
```

### Task 4: Verify the full Phase 2 slice

**Files:**
- Modify: `infra/docker/README.md`
- Modify: `.env.example`

- [ ] **Step 1: Add the DB URL note to environment docs**

`.env.example`

```dotenv
APP_ENV=development
APP_HOST=0.0.0.0
APP_PORT=8001

DATABASE_URL=mysql+pymysql://aism:aism_password@mysql:3306/ai_store_manager?charset=utf8mb4

MYSQL_DATABASE=ai_store_manager
MYSQL_USER=aism
MYSQL_PASSWORD=aism_password
MYSQL_ROOT_PASSWORD=root_password
MYSQL_PORT=3306
MYSQL_HOST=mysql

REDIS_PORT=6379
REDIS_URL=redis://redis:6379/0
```

`infra/docker/README.md`

```md
# Infra Docker

This directory currently defines the local infrastructure needed for the MVP backend skeleton:

- MySQL
- Redis
- MinIO
- API service
- Worker service

Phase 2 adds SQLAlchemy and Alembic-backed persistence. The backend now expects a working database URL and migration-managed schema before DB-backed routes are exercised.
```

- [ ] **Step 2: Run the full backend test suite**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests -q
```

Expected:

- all backend tests pass

- [ ] **Step 3: Verify Alembic can upgrade in a temporary SQLite database**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_alembic_bootstrap.py -q
```

Expected:

- `1 passed`

- [ ] **Step 4: Re-check Docker configuration**

Run:

```powershell
docker compose -f infra/docker/docker-compose.yml --env-file .env.example config
```

Expected:

- exit code `0`

- [ ] **Step 5: Confirm git status only contains this phase's expected files**

Run:

```powershell
git status --short
```

Expected:

- only the persistence-foundation files are listed

- [ ] **Step 6: Commit the verification/docs finish**

```bash
git add .env.example infra/docker/README.md
git commit -m "test: verify phase 2 persistence foundation"
```
