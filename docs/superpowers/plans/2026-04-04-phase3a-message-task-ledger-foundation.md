# Phase 3A Message and Task Ledger Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the minimum durable `messages` and `task_runs` foundation so the backend can record owner message intake, create an initial task ledger entry in the same transaction, and list message history with cursor pagination.

**Architecture:** Extend the Phase 2 persistence layer with `messages` and `task_runs`, add a small ID helper plus focused message/task services, and expose list/create message endpoints under the existing mock-auth session boundary. Keep the slice strictly pre-runtime by creating every new task run as `pending-classification` with `status = "created"` and by excluding confirmation, inventory, audit, and WebSocket behavior.

**Tech Stack:** Python, FastAPI, SQLAlchemy, Alembic, pytest, SQLite test databases, MySQL-oriented schema design, Docker Compose

---

### Task 1: Add IDs, ORM models, and Alembic migration for the message/task ledger

**Files:**
- Create: `backend/app/core/ids.py`
- Create: `backend/app/models/message.py`
- Create: `backend/app/models/task_run.py`
- Modify: `backend/app/models/__init__.py`
- Create: `backend/alembic/versions/20260404_02_create_messages_and_task_runs.py`
- Modify: `backend/tests/test_alembic_bootstrap.py`

- [ ] **Step 1: Extend the Alembic verification test with failing assertions for the new schema**

`backend/tests/test_alembic_bootstrap.py`

```python
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect


def test_alembic_upgrade_creates_message_and_task_tables(tmp_path) -> None:
    database_path = tmp_path / "alembic.db"
    database_url = f"sqlite:///{database_path.as_posix()}"

    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(config, "head")

    engine = create_engine(database_url, future=True)
    inspector = inspect(engine)

    assert "messages" in inspector.get_table_names()
    assert "task_runs" in inspector.get_table_names()
    assert {"message_id", "session_id", "message_type", "client_request_id", "task_run_id"} <= {
        column["name"] for column in inspector.get_columns("messages")
    }
    assert {"task_run_id", "session_id", "source_message_id", "task_type", "status"} <= {
        column["name"] for column in inspector.get_columns("task_runs")
    }
    message_indexes = {index["name"] for index in inspector.get_indexes("messages")}
    task_indexes = {index["name"] for index in inspector.get_indexes("task_runs")}
    assert "ix_messages_session_created_at" in message_indexes
    assert "ix_task_runs_session_updated_at" in task_indexes
    assert "ix_task_runs_source_message_id" in task_indexes
```

- [ ] **Step 2: Run the migration test to verify it fails before the new migration exists**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_alembic_bootstrap.py -q
```

Expected:

- failure because `messages` and `task_runs` do not exist yet

- [ ] **Step 3: Add a small prefixed ID helper**

`backend/app/core/ids.py`

```python
from uuid import uuid4


def new_prefixed_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"
```

- [ ] **Step 4: Add the new ORM models**

`backend/app/models/message.py`

```python
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Message(Base):
    __tablename__ = "messages"

    message_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.session_id"), nullable=False)
    actor_type: Mapped[str] = mapped_column(String(16), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(40), nullable=False)
    message_type: Mapped[str] = mapped_column(String(32), nullable=False)
    text: Mapped[str | None] = mapped_column(Text, nullable=True)
    media_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    client_request_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    task_run_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False)

    session = relationship("SessionRecord")
```

`backend/app/models/task_run.py`

```python
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class TaskRun(Base):
    __tablename__ = "task_runs"

    task_run_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.session_id"), nullable=False)
    source_message_id: Mapped[str] = mapped_column(ForeignKey("messages.message_id"), nullable=False)
    task_type: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    assigned_employee_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    result_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)

    session = relationship("SessionRecord")
    source_message = relationship("Message")
```

`backend/app/models/__init__.py`

```python
from app.models.message import Message
from app.models.session_record import SessionRecord
from app.models.shop import Shop
from app.models.task_run import TaskRun

__all__ = ["Message", "SessionRecord", "Shop", "TaskRun"]
```

- [ ] **Step 5: Add the migration for `messages` and `task_runs`**

`backend/alembic/versions/20260404_02_create_messages_and_task_runs.py`

```python
"""create messages and task runs tables"""

from alembic import op
import sqlalchemy as sa


revision = "20260404_02"
down_revision = "20260404_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "messages",
        sa.Column("message_id", sa.String(length=40), primary_key=True),
        sa.Column("session_id", sa.String(length=40), sa.ForeignKey("sessions.session_id"), nullable=False),
        sa.Column("actor_type", sa.String(length=16), nullable=False),
        sa.Column("actor_id", sa.String(length=40), nullable=False),
        sa.Column("message_type", sa.String(length=32), nullable=False),
        sa.Column("text", sa.Text(), nullable=True),
        sa.Column("media_ids", sa.JSON(), nullable=False),
        sa.Column("client_request_id", sa.String(length=64), nullable=True),
        sa.Column("task_run_id", sa.String(length=40), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_messages_session_created_at", "messages", ["session_id", "created_at"])
    op.create_unique_constraint(
        "uq_messages_session_actor_client_request",
        "messages",
        ["session_id", "actor_type", "actor_id", "client_request_id"],
    )

    op.create_table(
        "task_runs",
        sa.Column("task_run_id", sa.String(length=40), primary_key=True),
        sa.Column("session_id", sa.String(length=40), sa.ForeignKey("sessions.session_id"), nullable=False),
        sa.Column("source_message_id", sa.String(length=40), sa.ForeignKey("messages.message_id"), nullable=False),
        sa.Column("task_type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("assigned_employee_id", sa.String(length=40), nullable=True),
        sa.Column("result_summary", sa.Text(), nullable=True),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("error_message", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_task_runs_session_updated_at", "task_runs", ["session_id", "updated_at"])
    op.create_index("ix_task_runs_source_message_id", "task_runs", ["source_message_id"])


def downgrade() -> None:
    op.drop_index("ix_task_runs_source_message_id", table_name="task_runs")
    op.drop_index("ix_task_runs_session_updated_at", table_name="task_runs")
    op.drop_table("task_runs")
    op.drop_constraint("uq_messages_session_actor_client_request", "messages", type_="unique")
    op.drop_index("ix_messages_session_created_at", table_name="messages")
    op.drop_table("messages")
```

- [ ] **Step 6: Re-run the migration test to verify the schema lands cleanly**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_alembic_bootstrap.py -q
```

Expected:

- all Alembic assertions pass

- [ ] **Step 7: Commit**

```bash
git add backend/app/core/ids.py backend/app/models/message.py backend/app/models/task_run.py backend/app/models/__init__.py backend/alembic/versions/20260404_02_create_messages_and_task_runs.py backend/tests/test_alembic_bootstrap.py
git commit -m "feat: add message and task ledger schema"
```

### Task 2: Add message/task services with idempotent write behavior

**Files:**
- Modify: `backend/tests/conftest.py`
- Create: `backend/tests/test_message_service.py`
- Create: `backend/app/services/messages.py`
- Create: `backend/app/services/task_runs.py`

- [ ] **Step 1: Add a DB-session fixture that upgrades a temp SQLite database through Alembic**

`backend/tests/conftest.py`

```python
from pathlib import Path

from sqlalchemy.orm import Session


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
```

- [ ] **Step 2: Write the failing message service tests**

`backend/tests/test_message_service.py`

```python
from sqlalchemy import select

from app.models import Message, TaskRun
from app.services.bootstrap import ensure_default_context
from app.services.messages import (
    IdempotencyConflictError,
    SessionNotFoundError,
    create_message,
    list_messages,
)


def test_create_message_persists_message_task_and_last_message_at(db_session) -> None:
    context = ensure_default_context(db_session)

    result = create_message(
        db_session,
        session_id=context.session.session_id,
        actor_type="owner",
        actor_id="owner_default",
        message_type="text",
        text="补一箱矿泉水",
        media_ids=[],
        client_request_id="msg_local_001",
    )

    message = db_session.get(Message, result.message_id)
    task_run = db_session.get(TaskRun, result.task_run_id)
    refreshed_session = db_session.get(type(context.session), context.session.session_id)

    assert message is not None
    assert task_run is not None
    assert task_run.source_message_id == message.message_id
    assert task_run.task_type == "pending-classification"
    assert task_run.status == "created"
    assert refreshed_session.last_message_at == message.created_at


def test_create_message_replays_same_ids_for_same_idempotency_key(db_session) -> None:
    context = ensure_default_context(db_session)

    first = create_message(
        db_session,
        session_id=context.session.session_id,
        actor_type="owner",
        actor_id="owner_default",
        message_type="text",
        text="盘点一下红牛",
        media_ids=[],
        client_request_id="msg_local_002",
    )
    second = create_message(
        db_session,
        session_id=context.session.session_id,
        actor_type="owner",
        actor_id="owner_default",
        message_type="text",
        text="盘点一下红牛",
        media_ids=[],
        client_request_id="msg_local_002",
    )

    assert first.message_id == second.message_id
    assert first.task_run_id == second.task_run_id
    assert len(db_session.scalars(select(Message)).all()) == 1
    assert len(db_session.scalars(select(TaskRun)).all()) == 1


def test_create_message_raises_on_idempotency_conflict(db_session) -> None:
    context = ensure_default_context(db_session)

    create_message(
        db_session,
        session_id=context.session.session_id,
        actor_type="owner",
        actor_id="owner_default",
        message_type="text",
        text="第一次内容",
        media_ids=[],
        client_request_id="msg_local_003",
    )

    with pytest.raises(IdempotencyConflictError):
        create_message(
            db_session,
            session_id=context.session.session_id,
            actor_type="owner",
            actor_id="owner_default",
            message_type="text",
            text="第二次内容",
            media_ids=[],
            client_request_id="msg_local_003",
        )


def test_create_message_rejects_missing_session(db_session) -> None:
    with pytest.raises(SessionNotFoundError):
        create_message(
            db_session,
            session_id="sess_missing",
            actor_type="owner",
            actor_id="owner_default",
            message_type="text",
            text="找不到会话",
            media_ids=[],
            client_request_id="msg_missing",
        )


def test_list_messages_returns_newest_first_with_cursor(db_session) -> None:
    context = ensure_default_context(db_session)

    first = create_message(
        db_session,
        session_id=context.session.session_id,
        actor_type="owner",
        actor_id="owner_default",
        message_type="text",
        text="第一条",
        media_ids=[],
        client_request_id="msg_page_1",
    )
    second = create_message(
        db_session,
        session_id=context.session.session_id,
        actor_type="owner",
        actor_id="owner_default",
        message_type="text",
        text="第二条",
        media_ids=[],
        client_request_id="msg_page_2",
    )

    page_one = list_messages(db_session, session_id=context.session.session_id, limit=1, cursor=None)
    page_two = list_messages(
        db_session,
        session_id=context.session.session_id,
        limit=1,
        cursor=page_one.next_cursor,
    )

    assert page_one.items[0].message_id == second.message_id
    assert page_two.items[0].message_id == first.message_id
```

- [ ] **Step 3: Run the service tests to verify they fail before the services exist**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_message_service.py -q
```

Expected:

- import failures for `app.services.messages`

- [ ] **Step 4: Add the minimal task-run creation helper**

`backend/app/services/task_runs.py`

```python
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.core.ids import new_prefixed_id
from app.models.task_run import TaskRun


PENDING_CLASSIFICATION_TASK_TYPE = "pending-classification"
CREATED_STATUS = "created"


@dataclass(frozen=True)
class CreatedTaskRun:
    task_run_id: str


def create_initial_task_run(
    db_session: Session,
    *,
    session_id: str,
    source_message_id: str,
) -> TaskRun:
    now = datetime.now(UTC).replace(tzinfo=None)
    task_run = TaskRun(
        task_run_id=new_prefixed_id("task"),
        session_id=session_id,
        source_message_id=source_message_id,
        task_type=PENDING_CLASSIFICATION_TASK_TYPE,
        status=CREATED_STATUS,
        assigned_employee_id=None,
        result_summary=None,
        error_code=None,
        error_message=None,
        created_at=now,
        updated_at=now,
        completed_at=None,
    )
    db_session.add(task_run)
    db_session.flush()
    return task_run
```

- [ ] **Step 5: Add the message write/query service**

`backend/app/services/messages.py`

```python
from base64 import urlsafe_b64decode, urlsafe_b64encode
from dataclasses import dataclass
from datetime import UTC, datetime
import json

from sqlalchemy import and_, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.ids import new_prefixed_id
from app.models import Message, SessionRecord
from app.services.task_runs import create_initial_task_run


class SessionNotFoundError(Exception):
    pass


class IdempotencyConflictError(Exception):
    pass


class MessageValidationError(Exception):
    pass


@dataclass(frozen=True)
class MessageWriteResult:
    message_id: str
    task_run_id: str
    replayed: bool


@dataclass(frozen=True)
class MessageListItem:
    message_id: str
    session_id: str
    actor_type: str
    actor_id: str
    message_type: str
    text: str | None
    media_ids: list[str]
    task_run_id: str | None
    created_at: datetime


@dataclass(frozen=True)
class MessageListPage:
    items: list[MessageListItem]
    next_cursor: str | None


def _normalize_payload(*, message_type: str, text: str | None, media_ids: list[str]) -> tuple[str, str | None, list[str]]:
    trimmed = text.strip() if text is not None else None
    return message_type, trimmed, list(media_ids)


def _encode_cursor(created_at: datetime, message_id: str) -> str:
    payload = json.dumps({"created_at": created_at.isoformat(), "message_id": message_id})
    return urlsafe_b64encode(payload.encode("utf-8")).decode("ascii")


def _decode_cursor(cursor: str) -> tuple[datetime, str]:
    payload = json.loads(urlsafe_b64decode(cursor.encode("ascii")).decode("utf-8"))
    return datetime.fromisoformat(payload["created_at"]), payload["message_id"]


def _load_session(db_session: Session, session_id: str) -> SessionRecord:
    session = db_session.get(SessionRecord, session_id)
    if session is None:
        raise SessionNotFoundError(session_id)
    return session


def _validate_message_payload(
    *,
    message_type: str,
    text: str | None,
    media_ids: list[str],
    client_request_id: str,
) -> tuple[str | None, list[str]]:
    supported_types = {"text", "voice", "image", "receipt-image"}
    if message_type not in supported_types:
        raise MessageValidationError("Unsupported message_type")
    if not client_request_id.strip():
        raise MessageValidationError("client_request_id is required")

    normalized_text = text.strip() if text is not None else None
    normalized_media_ids = list(media_ids)
    if not normalized_text and not normalized_media_ids:
        raise MessageValidationError("text or media_ids is required")
    return normalized_text, normalized_media_ids


def _get_existing_message(
    db_session: Session,
    *,
    session_id: str,
    actor_type: str,
    actor_id: str,
    client_request_id: str,
) -> Message | None:
    query = select(Message).where(
        Message.session_id == session_id,
        Message.actor_type == actor_type,
        Message.actor_id == actor_id,
        Message.client_request_id == client_request_id,
    )
    return db_session.scalar(query)


def create_message(
    db_session: Session,
    *,
    session_id: str,
    actor_type: str,
    actor_id: str,
    message_type: str,
    text: str | None,
    media_ids: list[str],
    client_request_id: str,
) -> MessageWriteResult:
    session = _load_session(db_session, session_id)
    normalized_text, normalized_media_ids = _validate_message_payload(
        message_type=message_type,
        text=text,
        media_ids=media_ids,
        client_request_id=client_request_id,
    )

    existing = _get_existing_message(
        db_session,
        session_id=session_id,
        actor_type=actor_type,
        actor_id=actor_id,
        client_request_id=client_request_id,
    )
    if existing is not None:
        if _normalize_payload(
            message_type=existing.message_type,
            text=existing.text,
            media_ids=existing.media_ids,
        ) != _normalize_payload(
            message_type=message_type,
            text=normalized_text,
            media_ids=normalized_media_ids,
        ):
            raise IdempotencyConflictError(client_request_id)
        return MessageWriteResult(
            message_id=existing.message_id,
            task_run_id=existing.task_run_id or "",
            replayed=True,
        )

    now = datetime.now(UTC).replace(tzinfo=None)
    message = Message(
        message_id=new_prefixed_id("msg"),
        session_id=session_id,
        actor_type=actor_type,
        actor_id=actor_id,
        message_type=message_type,
        text=normalized_text,
        media_ids=normalized_media_ids,
        client_request_id=client_request_id,
        task_run_id=None,
        created_at=now,
    )
    db_session.add(message)
    db_session.flush()

    task_run = create_initial_task_run(
        db_session,
        session_id=session.session_id,
        source_message_id=message.message_id,
    )
    message.task_run_id = task_run.task_run_id
    session.last_message_at = message.created_at

    try:
        db_session.commit()
    except IntegrityError:
        db_session.rollback()
        existing = _get_existing_message(
            db_session,
            session_id=session_id,
            actor_type=actor_type,
            actor_id=actor_id,
            client_request_id=client_request_id,
        )
        if existing is None:
            raise
        if _normalize_payload(
            message_type=existing.message_type,
            text=existing.text,
            media_ids=existing.media_ids,
        ) != _normalize_payload(
            message_type=message_type,
            text=normalized_text,
            media_ids=normalized_media_ids,
        ):
            raise IdempotencyConflictError(client_request_id)
        return MessageWriteResult(
            message_id=existing.message_id,
            task_run_id=existing.task_run_id or "",
            replayed=True,
        )

    return MessageWriteResult(
        message_id=message.message_id,
        task_run_id=task_run.task_run_id,
        replayed=False,
    )


def list_messages(
    db_session: Session,
    *,
    session_id: str,
    limit: int,
    cursor: str | None,
) -> MessageListPage:
    _load_session(db_session, session_id)

    safe_limit = max(1, min(limit, 50))
    query = select(Message).where(Message.session_id == session_id)
    if cursor is not None:
        cursor_created_at, cursor_message_id = _decode_cursor(cursor)
        query = query.where(
            or_(
                Message.created_at < cursor_created_at,
                and_(
                    Message.created_at == cursor_created_at,
                    Message.message_id < cursor_message_id,
                ),
            )
        )

    query = query.order_by(Message.created_at.desc(), Message.message_id.desc()).limit(safe_limit + 1)
    records = list(db_session.scalars(query))
    has_more = len(records) > safe_limit
    page_records = records[:safe_limit]
    next_cursor = None
    if has_more and page_records:
        last = page_records[-1]
        next_cursor = _encode_cursor(last.created_at, last.message_id)

    return MessageListPage(
        items=[
            MessageListItem(
                message_id=record.message_id,
                session_id=record.session_id,
                actor_type=record.actor_type,
                actor_id=record.actor_id,
                message_type=record.message_type,
                text=record.text,
                media_ids=record.media_ids,
                task_run_id=record.task_run_id,
                created_at=record.created_at,
            )
            for record in page_records
        ],
        next_cursor=next_cursor,
    )
```

- [ ] **Step 6: Re-run the service tests until they pass**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_message_service.py -q
```

Expected:

- all message service tests pass

- [ ] **Step 7: Commit**

```bash
git add backend/tests/conftest.py backend/tests/test_message_service.py backend/app/services/messages.py backend/app/services/task_runs.py
git commit -m "feat: add message ledger services"
```

### Task 3: Add message contracts, routes, and API tests

**Files:**
- Create: `backend/app/contracts/message.py`
- Create: `backend/app/api/routes/messages.py`
- Modify: `backend/app/api/router.py`
- Create: `backend/tests/test_messages.py`

- [ ] **Step 1: Write the failing route tests**

`backend/tests/test_messages.py`

```python
def test_create_message_requires_authorization(client) -> None:
    response = client.post(
        "/api/v1/sessions/sess_default/messages",
        json={
            "message_type": "text",
            "text": "未授权",
            "media_ids": [],
            "client_request_id": "route_unauthorized",
        },
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


def test_create_message_returns_message_and_task_ids(client) -> None:
    response = client.post(
        "/api/v1/sessions/sess_default/messages",
        headers={"Authorization": "Bearer mock_owner_token"},
        json={
            "message_type": "text",
            "text": "来一箱可乐",
            "media_ids": [],
            "client_request_id": "route_create_001",
        },
    )

    assert response.status_code == 201
    payload = response.json()["data"]
    assert payload["message_id"].startswith("msg_")
    assert payload["task_run_id"].startswith("task_")
    assert payload["status"] == "created"


def test_create_message_returns_same_ids_on_idempotent_retry(client) -> None:
    headers = {"Authorization": "Bearer mock_owner_token"}
    body = {
        "message_type": "text",
        "text": "重复提交",
        "media_ids": [],
        "client_request_id": "route_retry_001",
    }

    first = client.post("/api/v1/sessions/sess_default/messages", headers=headers, json=body)
    second = client.post("/api/v1/sessions/sess_default/messages", headers=headers, json=body)

    assert first.status_code == 201
    assert second.status_code == 200
    assert first.json()["data"]["message_id"] == second.json()["data"]["message_id"]
    assert first.json()["data"]["task_run_id"] == second.json()["data"]["task_run_id"]


def test_create_message_returns_conflict_for_payload_drift(client) -> None:
    headers = {"Authorization": "Bearer mock_owner_token"}

    first = client.post(
        "/api/v1/sessions/sess_default/messages",
        headers=headers,
        json={
            "message_type": "text",
            "text": "第一次",
            "media_ids": [],
            "client_request_id": "route_conflict_001",
        },
    )
    second = client.post(
        "/api/v1/sessions/sess_default/messages",
        headers=headers,
        json={
            "message_type": "text",
            "text": "第二次",
            "media_ids": [],
            "client_request_id": "route_conflict_001",
        },
    )

    assert first.status_code == 201
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "idempotency_conflict"


def test_list_messages_returns_newest_first_with_next_cursor(client) -> None:
    headers = {"Authorization": "Bearer mock_owner_token"}
    client.post(
        "/api/v1/sessions/sess_default/messages",
        headers=headers,
        json={"message_type": "text", "text": "一", "media_ids": [], "client_request_id": "route_page_1"},
    )
    client.post(
        "/api/v1/sessions/sess_default/messages",
        headers=headers,
        json={"message_type": "text", "text": "二", "media_ids": [], "client_request_id": "route_page_2"},
    )

    first_page = client.get(
        "/api/v1/sessions/sess_default/messages?limit=1",
        headers=headers,
    )

    assert first_page.status_code == 200
    assert first_page.json()["data"][0]["text"] == "二"
    assert first_page.json()["meta"]["next_cursor"] is not None
```

- [ ] **Step 2: Run the route tests to verify they fail before the route exists**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_messages.py -q
```

Expected:

- 404 for missing route or import failures for `app.api.routes.messages`

- [ ] **Step 3: Add the message route contracts**

`backend/app/contracts/message.py`

```python
from datetime import datetime

from pydantic import BaseModel, Field


class CreateSessionMessageRequest(BaseModel):
    message_type: str
    text: str | None = None
    media_ids: list[str] = Field(default_factory=list)
    client_request_id: str


class CreateSessionMessageData(BaseModel):
    message_id: str
    task_run_id: str
    status: str


class SessionMessageItem(BaseModel):
    message_id: str
    session_id: str
    actor_type: str
    actor_id: str
    message_type: str
    text: str | None
    media_ids: list[str]
    task_run_id: str | None
    created_at: datetime


class SessionMessagesMeta(BaseModel):
    next_cursor: str | None = None


class SessionMessagesResponse(BaseModel):
    data: list[SessionMessageItem]
    meta: SessionMessagesMeta
```

- [ ] **Step 4: Add the route and wire it into the API router**

`backend/app/api/routes/messages.py`

```python
from fastapi import APIRouter, Depends, Header, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.contracts.common import DataEnvelope, ErrorBody, ErrorEnvelope
from app.contracts.message import (
    CreateSessionMessageData,
    CreateSessionMessageRequest,
    SessionMessageItem,
    SessionMessagesMeta,
    SessionMessagesResponse,
)
from app.core.config import Settings, get_settings
from app.db.session import get_db_session
from app.services.bootstrap import ensure_default_context
from app.services.messages import (
    IdempotencyConflictError,
    MessageValidationError,
    SessionNotFoundError,
    create_message,
    list_messages,
)

router = APIRouter(prefix="/api/v1/sessions", tags=["messages"])


def _unauthorized() -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content=ErrorEnvelope(
            error=ErrorBody(code="unauthorized", message="Unauthorized", details=[])
        ).model_dump(),
    )


def _error_response(status_code: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=ErrorEnvelope(
            error=ErrorBody(code=code, message=message, details=[])
        ).model_dump(),
    )


@router.get("/{session_id}/messages", response_model=SessionMessagesResponse)
def get_session_messages(
    session_id: str,
    authorization: str | None = Header(default=None),
    limit: int = Query(default=20, ge=1, le=50),
    cursor: str | None = Query(default=None),
    db_session: Session = Depends(get_db_session),
) -> SessionMessagesResponse | JSONResponse:
    if authorization != "Bearer mock_owner_token":
        return _unauthorized()

    ensure_default_context(db_session)

    try:
        page = list_messages(
            db_session,
            session_id=session_id,
            limit=limit,
            cursor=cursor,
        )
    except SessionNotFoundError:
        return _error_response(status.HTTP_404_NOT_FOUND, "session_not_found", "Session not found")

    return SessionMessagesResponse(
        data=[
            SessionMessageItem(
                message_id=item.message_id,
                session_id=item.session_id,
                actor_type=item.actor_type,
                actor_id=item.actor_id,
                message_type=item.message_type,
                text=item.text,
                media_ids=item.media_ids,
                task_run_id=item.task_run_id,
                created_at=item.created_at,
            )
            for item in page.items
        ],
        meta=SessionMessagesMeta(next_cursor=page.next_cursor),
    )


@router.post(
    "/{session_id}/messages",
    response_model=DataEnvelope[CreateSessionMessageData],
)
def post_session_message(
    session_id: str,
    payload: CreateSessionMessageRequest,
    authorization: str | None = Header(default=None),
    db_session: Session = Depends(get_db_session),
) -> DataEnvelope[CreateSessionMessageData] | JSONResponse:
    if authorization != "Bearer mock_owner_token":
        return _unauthorized()

    ensure_default_context(db_session)

    try:
        result = create_message(
            db_session,
            session_id=session_id,
            actor_type="owner",
            actor_id="owner_default",
            message_type=payload.message_type,
            text=payload.text,
            media_ids=payload.media_ids,
            client_request_id=payload.client_request_id,
        )
    except SessionNotFoundError:
        return _error_response(status.HTTP_404_NOT_FOUND, "session_not_found", "Session not found")
    except IdempotencyConflictError:
        return _error_response(status.HTTP_409_CONFLICT, "idempotency_conflict", "Request payload conflicts with prior submission")
    except MessageValidationError as exc:
        return _error_response(status.HTTP_422_UNPROCESSABLE_ENTITY, "validation_error", str(exc))

    response_payload = DataEnvelope(
        data=CreateSessionMessageData(
            message_id=result.message_id,
            task_run_id=result.task_run_id,
            status="created",
        )
    )
    if result.replayed:
        return response_payload

    return JSONResponse(
        status_code=status.HTTP_201_CREATED,
        content=response_payload.model_dump(mode="json"),
    )
```

Route requirements:

- reject missing/invalid auth with the existing error envelope
- call `ensure_default_context(db_session)` so the default session exists before reads/writes
- map `SessionNotFoundError` to `404 session_not_found`
- map `IdempotencyConflictError` to `409 idempotency_conflict`
- map `MessageValidationError` to `422 validation_error`
- return `201` for fresh create and `200` for replay
- serialize service objects through the contract models

`backend/app/api/router.py`

```python
from app.api.routes.messages import router as messages_router

api_router.include_router(messages_router)
```

- [ ] **Step 5: Re-run the route tests until they pass**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_messages.py -q
```

Expected:

- all message route tests pass

- [ ] **Step 6: Commit**

```bash
git add backend/app/contracts/message.py backend/app/api/routes/messages.py backend/app/api/router.py backend/tests/test_messages.py
git commit -m "feat: add session message APIs"
```

### Task 4: Verify the full Phase 3A slice

**Files:**
- Modify: `infra/docker/README.md`

- [ ] **Step 1: Note the new message/task ledger slice in infra documentation**

`infra/docker/README.md`

```md
Phase 3A extends the backend schema with the message and task ledger foundation. The local stack still brings up MySQL, Redis, MinIO, API, and worker services, but this phase only exercises the DB-backed intake path and does not yet introduce runtime consumers, confirmations, or WebSocket session events.
```

- [ ] **Step 2: Run the focused backend tests for this slice**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_alembic_bootstrap.py backend/tests/test_message_service.py backend/tests/test_messages.py -q
```

Expected:

- all focused tests pass

- [ ] **Step 3: Run the full backend test suite**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests -q
```

Expected:

- all backend tests pass

- [ ] **Step 4: Re-check Docker Compose configuration**

Run:

```powershell
docker compose -f infra/docker/docker-compose.yml --env-file .env.example config
```

Expected:

- exit code `0`

- [ ] **Step 5: Confirm git status only contains the Phase 3A changes**

Run:

```powershell
git status --short
```

Expected:

- only the message/task-ledger files are listed

- [ ] **Step 6: Commit the verification/docs finish**

```bash
git add infra/docker/README.md
git commit -m "test: verify phase 3a message ledger"
```
