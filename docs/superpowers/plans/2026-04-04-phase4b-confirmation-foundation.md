# Phase 4B Confirmation Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the minimum durable confirmation chain so stock-in runtime work can pause in `awaiting-confirmation`, owners can approve or reject through explicit routes, and the linked `task_run` resolves without introducing inventory, audit, or realtime side effects.

**Architecture:** Keep the current message-intake and worker-dispatch path intact, then extend the backend in four layers: durable confirmation persistence, task lifecycle transitions, runtime policy-driven confirmation creation, and confirmation API resolution. This phase continues to use text-only runtime/system messages as the visible ledger output, while projecting `confirmation_id` into task polling responses instead of adding a physical `task_runs.confirmation_id` column.

**Tech Stack:** Python, FastAPI, SQLAlchemy, Alembic, Celery, pytest, SQLite test databases, MySQL-oriented schema design, Docker Compose

---

### Task 1: Add confirmation schema, model, and service foundation

**Files:**
- Create: `backend/app/models/confirmation.py`
- Modify: `backend/app/models/__init__.py`
- Create: `backend/app/contracts/confirmation.py`
- Create: `backend/app/services/confirmations.py`
- Create: `backend/alembic/versions/20260404_03_create_confirmations.py`
- Create: `backend/tests/test_confirmations_service.py`

- [ ] **Step 1: Write the failing confirmation service tests**

```python
import pytest
from sqlalchemy import select

from app.models import Confirmation, TaskRun
from app.services.confirmations import (
    APPROVED_STATUS,
    PENDING_STATUS,
    REJECTED_STATUS,
    approve_confirmation,
    create_pending_confirmation,
    list_confirmations,
    reject_confirmation,
)
from app.services.messages import create_message


def _create_processing_stock_in_task(db_session) -> TaskRun:
    result = create_message(
        db_session,
        session_id="sess_default",
        actor_type="owner",
        actor_id="owner_default",
        message_type="text",
        text="restock apples today",
        media_ids=[],
        client_request_id="confirmation_seed_001",
    )
    task_run = db_session.get(TaskRun, result.task_run_id)
    assert task_run is not None
    task_run.status = "processing"
    task_run.task_type = "voice-stock-in"
    task_run.assigned_employee_id = "xiaoya"
    db_session.commit()
    return task_run


def test_create_pending_confirmation_is_idempotent_per_task_run(db_session) -> None:
    task_run = _create_processing_stock_in_task(db_session)

    first = create_pending_confirmation(
        db_session,
        task_run_id=task_run.task_run_id,
        confirmation_type="low-confidence-recognition",
        fields={
            "summary": "Please confirm stock-in details before commit.",
            "transcript": "restock apples today",
            "draft_fields": {"item_name": None, "quantity": None, "unit": None, "price": None},
            "required_fields": ["item_name", "quantity", "unit", "price"],
        },
        requested_by_employee_id="xiaoya",
    )
    second = create_pending_confirmation(
        db_session,
        task_run_id=task_run.task_run_id,
        confirmation_type="low-confidence-recognition",
        fields={
            "summary": "Please confirm stock-in details before commit.",
            "transcript": "restock apples today",
            "draft_fields": {"item_name": None, "quantity": None, "unit": None, "price": None},
            "required_fields": ["item_name", "quantity", "unit", "price"],
        },
        requested_by_employee_id="xiaoya",
    )

    assert first.confirmation_id == second.confirmation_id
    assert second.status == PENDING_STATUS
    assert db_session.scalar(select(Confirmation).where(Confirmation.task_run_id == task_run.task_run_id)) is not None


def test_approve_confirmation_records_resolution_payload(db_session) -> None:
    task_run = _create_processing_stock_in_task(db_session)
    confirmation = create_pending_confirmation(
        db_session,
        task_run_id=task_run.task_run_id,
        confirmation_type="low-confidence-recognition",
        fields={
            "summary": "Please confirm stock-in details before commit.",
            "transcript": "restock apples today",
            "draft_fields": {"item_name": None, "quantity": None, "unit": None, "price": None},
            "required_fields": ["item_name", "quantity", "unit", "price"],
        },
        requested_by_employee_id="xiaoya",
    )

    approved = approve_confirmation(
        db_session,
        confirmation_id=confirmation.confirmation_id,
        resolution_payload={
            "fields": {
                "item_name": "Apple",
                "quantity": 3,
                "unit": "box",
                "price": 18.5,
            }
        },
        approved_by_actor_id="owner_default",
    )

    assert approved.status == APPROVED_STATUS
    assert approved.resolution_payload == {
        "fields": {"item_name": "Apple", "quantity": 3, "unit": "box", "price": 18.5}
    }
    assert approved.approved_by_actor_id == "owner_default"
    assert approved.resolved_at is not None


def test_reject_confirmation_marks_record_rejected(db_session) -> None:
    task_run = _create_processing_stock_in_task(db_session)
    confirmation = create_pending_confirmation(
        db_session,
        task_run_id=task_run.task_run_id,
        confirmation_type="low-confidence-recognition",
        fields={
            "summary": "Please confirm stock-in details before commit.",
            "transcript": "restock apples today",
            "draft_fields": {"item_name": None, "quantity": None, "unit": None, "price": None},
            "required_fields": ["item_name", "quantity", "unit", "price"],
        },
        requested_by_employee_id="xiaoya",
    )

    rejected = reject_confirmation(
        db_session,
        confirmation_id=confirmation.confirmation_id,
    )

    assert rejected.status == REJECTED_STATUS
    assert rejected.resolution_payload is None
    assert rejected.resolved_at is not None


def test_resolving_already_resolved_confirmation_raises_conflict(db_session) -> None:
    task_run = _create_processing_stock_in_task(db_session)
    confirmation = create_pending_confirmation(
        db_session,
        task_run_id=task_run.task_run_id,
        confirmation_type="low-confidence-recognition",
        fields={
            "summary": "Please confirm stock-in details before commit.",
            "transcript": "restock apples today",
            "draft_fields": {"item_name": None, "quantity": None, "unit": None, "price": None},
            "required_fields": ["item_name", "quantity", "unit", "price"],
        },
        requested_by_employee_id="xiaoya",
    )
    approve_confirmation(
        db_session,
        confirmation_id=confirmation.confirmation_id,
        resolution_payload={"fields": {"item_name": "Apple", "quantity": 1, "unit": "box", "price": 18.5}},
        approved_by_actor_id="owner_default",
    )

    with pytest.raises(Exception):
        reject_confirmation(db_session, confirmation_id=confirmation.confirmation_id)


def test_list_confirmations_filters_by_status_newest_first(db_session) -> None:
    task_run = _create_processing_stock_in_task(db_session)
    pending = create_pending_confirmation(
        db_session,
        task_run_id=task_run.task_run_id,
        confirmation_type="low-confidence-recognition",
        fields={
            "summary": "Please confirm stock-in details before commit.",
            "transcript": "restock apples today",
            "draft_fields": {"item_name": None, "quantity": None, "unit": None, "price": None},
            "required_fields": ["item_name", "quantity", "unit", "price"],
        },
        requested_by_employee_id="xiaoya",
    )

    page = list_confirmations(db_session, status=PENDING_STATUS, limit=20)

    assert [item.confirmation_id for item in page.items] == [pending.confirmation_id]
```

- [ ] **Step 2: Run the confirmation service tests to verify they fail**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_confirmations_service.py -q
```

Expected:

- import failures for `app.models.Confirmation` or `app.services.confirmations`

- [ ] **Step 3: Add the confirmation model, contract, service, and migration**

`backend/app/models/confirmation.py`

```python
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Confirmation(Base):
    __tablename__ = "confirmations"

    confirmation_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    task_run_id: Mapped[str] = mapped_column(ForeignKey("task_runs.task_run_id"), nullable=False, unique=True)
    confirmation_type: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    fields: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    resolution_payload: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    requested_by_employee_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    approved_by_actor_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)

    task_run = relationship("TaskRun")
```

`backend/app/models/__init__.py`

```python
from app.models.confirmation import Confirmation
from app.models.message import Message
from app.models.session_record import SessionRecord
from app.models.shop import Shop
from app.models.task_run import TaskRun

__all__ = ["Confirmation", "Message", "SessionRecord", "Shop", "TaskRun"]
```

`backend/app/contracts/confirmation.py`

```python
from datetime import datetime

from pydantic import BaseModel, Field


class ConfirmationData(BaseModel):
    confirmation_id: str
    task_run_id: str
    session_id: str
    confirmation_type: str
    status: str
    fields: dict[str, object]
    resolution_payload: dict[str, object] | None
    requested_by_employee_id: str | None
    approved_by_actor_id: str | None
    created_at: datetime
    resolved_at: datetime | None


class ListConfirmationsMeta(BaseModel):
    count: int


class ListConfirmationsResponse(BaseModel):
    data: list[ConfirmationData]
    meta: ListConfirmationsMeta


class ApproveConfirmationRequest(BaseModel):
    fields: dict[str, object] = Field(default_factory=dict)
```

`backend/app/services/confirmations.py`

```python
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.ids import new_prefixed_id
from app.models import Confirmation, TaskRun

PENDING_STATUS = "pending"
APPROVED_STATUS = "approved"
REJECTED_STATUS = "rejected"


class ConfirmationNotPendingError(ValueError):
    pass


@dataclass(frozen=True)
class ConfirmationListPage:
    items: list[Confirmation]


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _require_confirmation(db_session: Session, confirmation_id: str) -> Confirmation:
    confirmation = db_session.get(Confirmation, confirmation_id)
    if confirmation is None:
        raise LookupError(confirmation_id)
    return confirmation


def create_pending_confirmation(
    db_session: Session,
    *,
    task_run_id: str,
    confirmation_type: str,
    fields: dict[str, object],
    requested_by_employee_id: str | None,
) -> Confirmation:
    task_run = db_session.get(TaskRun, task_run_id)
    if task_run is None:
        raise LookupError(task_run_id)
    existing = db_session.scalar(
        select(Confirmation).where(Confirmation.task_run_id == task_run_id)
    )
    if existing is not None:
        return existing

    confirmation = Confirmation(
        confirmation_id=new_prefixed_id("conf"),
        task_run_id=task_run_id,
        confirmation_type=confirmation_type,
        status=PENDING_STATUS,
        fields=fields,
        resolution_payload=None,
        requested_by_employee_id=requested_by_employee_id,
        approved_by_actor_id=None,
        created_at=_now(),
        resolved_at=None,
    )
    db_session.add(confirmation)
    db_session.flush()
    return confirmation


def approve_confirmation(
    db_session: Session,
    *,
    confirmation_id: str,
    resolution_payload: dict[str, object],
    approved_by_actor_id: str,
) -> Confirmation:
    confirmation = _require_confirmation(db_session, confirmation_id)
    if confirmation.status != PENDING_STATUS:
        raise ConfirmationNotPendingError(confirmation_id)
    confirmation.status = APPROVED_STATUS
    confirmation.resolution_payload = resolution_payload
    confirmation.approved_by_actor_id = approved_by_actor_id
    confirmation.resolved_at = _now()
    db_session.flush()
    return confirmation


def reject_confirmation(db_session: Session, *, confirmation_id: str) -> Confirmation:
    confirmation = _require_confirmation(db_session, confirmation_id)
    if confirmation.status != PENDING_STATUS:
        raise ConfirmationNotPendingError(confirmation_id)
    confirmation.status = REJECTED_STATUS
    confirmation.resolution_payload = None
    confirmation.approved_by_actor_id = None
    confirmation.resolved_at = _now()
    db_session.flush()
    return confirmation


def list_confirmations(db_session: Session, *, status: str, limit: int) -> ConfirmationListPage:
    records = list(
        db_session.scalars(
            select(Confirmation)
            .where(Confirmation.status == status)
            .order_by(Confirmation.created_at.desc(), Confirmation.confirmation_id.desc())
            .limit(max(1, min(limit, 50)))
        )
    )
    return ConfirmationListPage(items=records)
```

`backend/alembic/versions/20260404_03_create_confirmations.py`

```python
from alembic import op
import sqlalchemy as sa


revision = "20260404_03"
down_revision = "20260404_02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "confirmations",
        sa.Column("confirmation_id", sa.String(length=40), nullable=False),
        sa.Column("task_run_id", sa.String(length=40), nullable=False),
        sa.Column("confirmation_type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("fields", sa.JSON(), nullable=False),
        sa.Column("resolution_payload", sa.JSON(), nullable=True),
        sa.Column("requested_by_employee_id", sa.String(length=40), nullable=True),
        sa.Column("approved_by_actor_id", sa.String(length=40), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["task_run_id"], ["task_runs.task_run_id"]),
        sa.PrimaryKeyConstraint("confirmation_id"),
        sa.UniqueConstraint("task_run_id"),
    )
    op.create_index(
        "ix_confirmations_status_created_at",
        "confirmations",
        ["status", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_confirmations_status_created_at", table_name="confirmations")
    op.drop_table("confirmations")
```

- [ ] **Step 4: Re-run the confirmation service tests to verify they pass**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_confirmations_service.py -q
```

Expected:

- all confirmation service tests pass

- [ ] **Step 5: Commit**

```bash
git add backend/app/models/confirmation.py backend/app/models/__init__.py backend/app/contracts/confirmation.py backend/app/services/confirmations.py backend/alembic/versions/20260404_03_create_confirmations.py backend/tests/test_confirmations_service.py
git commit -m "feat: add confirmation persistence foundation"
```

### Task 2: Extend task lifecycle transitions for confirmation states

**Files:**
- Modify: `backend/app/services/task_runs.py`
- Modify: `backend/app/contracts/task_run.py`
- Create: `backend/tests/test_task_run_transitions.py`

- [ ] **Step 1: Write the failing task lifecycle tests**

```python
import pytest

from app.models import TaskRun
from app.services.messages import create_message
from app.services.task_runs import (
    mark_task_run_awaiting_confirmation,
    reject_awaiting_confirmation_task_run,
    resolve_awaiting_confirmation_task_run,
)


def _create_processing_task(db_session, *, client_request_id: str) -> TaskRun:
    result = create_message(
        db_session,
        session_id="sess_default",
        actor_type="owner",
        actor_id="owner_default",
        message_type="text",
        text="restock apples today",
        media_ids=[],
        client_request_id=client_request_id,
    )
    task_run = db_session.get(TaskRun, result.task_run_id)
    assert task_run is not None
    task_run.status = "processing"
    task_run.task_type = "voice-stock-in"
    task_run.assigned_employee_id = "xiaoya"
    db_session.commit()
    return task_run


def test_mark_task_run_awaiting_confirmation_moves_processing_task(db_session) -> None:
    task_run = _create_processing_task(db_session, client_request_id="task_transition_001")

    updated = mark_task_run_awaiting_confirmation(
        db_session,
        task_run_id=task_run.task_run_id,
        result_summary="Awaiting owner confirmation for stock-in details.",
    )

    assert updated.status == "awaiting-confirmation"
    assert updated.result_summary == "Awaiting owner confirmation for stock-in details."
    assert updated.completed_at is None


def test_resolve_awaiting_confirmation_task_run_completes_task(db_session) -> None:
    task_run = _create_processing_task(db_session, client_request_id="task_transition_002")
    mark_task_run_awaiting_confirmation(
        db_session,
        task_run_id=task_run.task_run_id,
        result_summary="Awaiting owner confirmation for stock-in details.",
    )

    updated = resolve_awaiting_confirmation_task_run(
        db_session,
        task_run_id=task_run.task_run_id,
        result_summary="Owner approved confirmation. Business commit is deferred to a later phase.",
    )

    assert updated.status == "completed"
    assert updated.completed_at is not None
    assert updated.result_summary.startswith("Owner approved confirmation.")


def test_reject_awaiting_confirmation_task_run_marks_task_rejected(db_session) -> None:
    task_run = _create_processing_task(db_session, client_request_id="task_transition_003")
    mark_task_run_awaiting_confirmation(
        db_session,
        task_run_id=task_run.task_run_id,
        result_summary="Awaiting owner confirmation for stock-in details.",
    )

    updated = reject_awaiting_confirmation_task_run(
        db_session,
        task_run_id=task_run.task_run_id,
        result_summary="Owner rejected the pending stock-in confirmation.",
    )

    assert updated.status == "rejected"
    assert updated.completed_at is not None


def test_mark_task_run_awaiting_confirmation_requires_processing_state(db_session) -> None:
    task_run = _create_processing_task(db_session, client_request_id="task_transition_004")
    task_run.status = "created"
    db_session.commit()

    with pytest.raises(Exception):
        mark_task_run_awaiting_confirmation(
            db_session,
            task_run_id=task_run.task_run_id,
            result_summary="Awaiting owner confirmation for stock-in details.",
        )
```

- [ ] **Step 2: Run the task lifecycle tests to verify they fail**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_task_run_transitions.py -q
```

Expected:

- import failures for the new transition helpers

- [ ] **Step 3: Add the new task lifecycle transitions and contract projection**

`backend/app/services/task_runs.py`

```python
AWAITING_CONFIRMATION_STATUS = "awaiting-confirmation"
REJECTED_STATUS = "rejected"


def mark_task_run_awaiting_confirmation(
    db_session: Session,
    *,
    task_run_id: str,
    result_summary: str,
) -> TaskRun:
    now = _now()
    result = db_session.execute(
        update(TaskRun)
        .where(
            TaskRun.task_run_id == task_run_id,
            TaskRun.status == PROCESSING_STATUS,
        )
        .values(
            status=AWAITING_CONFIRMATION_STATUS,
            result_summary=result_summary,
            error_code=None,
            error_message=None,
            updated_at=now,
            completed_at=None,
        )
        .execution_options(synchronize_session=False)
    )
    task_run = _require_task_run(db_session, task_run_id)
    if result.rowcount != 1:
        raise TaskRunTransitionError(
            f"Task run {task_run_id} must be in '{PROCESSING_STATUS}' status to await confirmation; found '{task_run.status}'."
        )
    return task_run


def resolve_awaiting_confirmation_task_run(
    db_session: Session,
    *,
    task_run_id: str,
    result_summary: str,
) -> TaskRun:
    now = _now()
    result = db_session.execute(
        update(TaskRun)
        .where(
            TaskRun.task_run_id == task_run_id,
            TaskRun.status == AWAITING_CONFIRMATION_STATUS,
        )
        .values(
            status=COMPLETED_STATUS,
            result_summary=result_summary,
            error_code=None,
            error_message=None,
            updated_at=now,
            completed_at=now,
        )
        .execution_options(synchronize_session=False)
    )
    task_run = _require_task_run(db_session, task_run_id)
    if result.rowcount != 1:
        raise TaskRunTransitionError(
            f"Task run {task_run_id} must be in '{AWAITING_CONFIRMATION_STATUS}' status to complete; found '{task_run.status}'."
        )
    return task_run


def reject_awaiting_confirmation_task_run(
    db_session: Session,
    *,
    task_run_id: str,
    result_summary: str,
) -> TaskRun:
    now = _now()
    result = db_session.execute(
        update(TaskRun)
        .where(
            TaskRun.task_run_id == task_run_id,
            TaskRun.status == AWAITING_CONFIRMATION_STATUS,
        )
        .values(
            status=REJECTED_STATUS,
            result_summary=result_summary,
            error_code=None,
            error_message=None,
            updated_at=now,
            completed_at=now,
        )
        .execution_options(synchronize_session=False)
    )
    task_run = _require_task_run(db_session, task_run_id)
    if result.rowcount != 1:
        raise TaskRunTransitionError(
            f"Task run {task_run_id} must be in '{AWAITING_CONFIRMATION_STATUS}' status to reject; found '{task_run.status}'."
        )
    return task_run
```

`backend/app/contracts/task_run.py`

```python
from datetime import datetime

from pydantic import BaseModel


class TaskRunData(BaseModel):
    task_run_id: str
    session_id: str
    source_message_id: str
    task_type: str
    status: str
    assigned_employee_id: str | None
    confirmation_id: str | None = None
    result_summary: str | None
    error_code: str | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None
```

- [ ] **Step 4: Re-run the task lifecycle tests to verify they pass**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_task_run_transitions.py -q
```

Expected:

- all task lifecycle tests pass

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/task_runs.py backend/app/contracts/task_run.py backend/tests/test_task_run_transitions.py
git commit -m "feat: add confirmation task lifecycle transitions"
```

### Task 3: Add runtime policy and awaiting-confirmation processing

**Files:**
- Create: `backend/app/runtime/policy.py`
- Modify: `backend/app/runtime/processor.py`
- Modify: `backend/app/runtime/context.py`
- Modify: `backend/tests/test_runtime_processor.py`
- Modify: `backend/tests/test_runtime_tasks.py`

- [ ] **Step 1: Write the failing runtime confirmation tests**

```python
from sqlalchemy import select

from app.models import Confirmation, Message, TaskRun
from app.runtime.processor import process_task_run
from app.services.messages import create_message


def test_process_task_run_pauses_stock_in_for_confirmation(db_session) -> None:
    result = create_message(
        db_session,
        session_id="sess_default",
        actor_type="owner",
        actor_id="owner_default",
        message_type="text",
        text="restock apples today",
        media_ids=[],
        client_request_id="runtime_confirmation_001",
    )

    runtime_result = process_task_run(db_session, result.task_run_id)
    task_run = db_session.get(TaskRun, result.task_run_id)
    confirmation = db_session.scalar(
        select(Confirmation).where(Confirmation.task_run_id == result.task_run_id)
    )
    runtime_messages = db_session.scalars(
        select(Message).where(Message.task_run_id == result.task_run_id, Message.actor_type == "system")
    ).all()

    assert runtime_result.status == "awaiting-confirmation"
    assert runtime_result.task_type == "voice-stock-in"
    assert task_run is not None
    assert task_run.status == "awaiting-confirmation"
    assert confirmation is not None
    assert confirmation.status == "pending"
    assert len(runtime_messages) == 1
    assert "confirm" in (runtime_messages[0].text or "").lower()


def test_process_task_run_keeps_query_path_completed(db_session) -> None:
    result = create_message(
        db_session,
        session_id="sess_default",
        actor_type="owner",
        actor_id="owner_default",
        message_type="text",
        text="check stock left for cola",
        media_ids=[],
        client_request_id="runtime_confirmation_002",
    )

    runtime_result = process_task_run(db_session, result.task_run_id)
    task_run = db_session.get(TaskRun, result.task_run_id)

    assert runtime_result.status == "completed"
    assert task_run is not None
    assert task_run.status == "completed"
```

- [ ] **Step 2: Run the runtime processor tests to verify they fail**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_runtime_processor.py backend/tests/test_runtime_tasks.py -q
```

Expected:

- assertions fail because stock-in currently completes instead of awaiting confirmation

- [ ] **Step 3: Add runtime policy and confirmation-aware processor behavior**

`backend/app/runtime/policy.py`

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class PolicyDecision:
    outcome: str
    confirmation_type: str | None


def evaluate_runtime_policy(*, task_type: str) -> PolicyDecision:
    if task_type == "voice-stock-in":
        return PolicyDecision(
            outcome="require-confirmation",
            confirmation_type="low-confidence-recognition",
        )
    return PolicyDecision(outcome="allow", confirmation_type=None)
```

`backend/app/runtime/context.py`

```python
from sqlalchemy import select

from app.models import Confirmation


def _lookup_pending_confirmation_id(db_session: Session, *, task_run_id: str) -> str | None:
    return db_session.scalar(
        select(Confirmation.confirmation_id)
        .where(
            Confirmation.task_run_id == task_run_id,
            Confirmation.status == "pending",
        )
    )
```

and set:

```python
pending_confirmation_id=_lookup_pending_confirmation_id(
    db_session,
    task_run_id=task_run.task_run_id,
),
```

`backend/app/runtime/processor.py`

```python
from app.runtime.policy import evaluate_runtime_policy
from app.services.confirmations import create_pending_confirmation
from app.services.task_runs import mark_task_run_awaiting_confirmation


def _build_confirmation_fields(transcript: str | None) -> dict[str, object]:
    return {
        "summary": "Please confirm the stock-in details before commit.",
        "transcript": (transcript or "").strip(),
        "draft_fields": {
            "item_name": None,
            "quantity": None,
            "unit": None,
            "price": None,
        },
        "required_fields": ["item_name", "quantity", "unit", "price"],
    }


def process_task_run(db_session: Session, task_run_id: str) -> RuntimeProcessResult:
    claim = claim_task_run_for_runtime(db_session, task_run_id=task_run_id)
    if not claim.changed:
        return RuntimeProcessResult(
            status="skipped",
            task_run_id=claim.task_run.task_run_id,
            task_type=claim.task_run.task_type,
            error_code=claim.task_run.error_code,
        )

    try:
        context = build_runtime_turn_context(db_session, task_run_id=task_run_id)
        decision = route_runtime_input(context)
        policy = evaluate_runtime_policy(task_type=decision.task_type)
        if policy.outcome == "require-confirmation":
            create_pending_confirmation(
                db_session,
                task_run_id=task_run_id,
                confirmation_type=policy.confirmation_type or "low-confidence-recognition",
                fields=_build_confirmation_fields(decision.transcript),
                requested_by_employee_id=decision.assigned_employee_id,
            )
            mark_task_run_awaiting_confirmation(
                db_session,
                task_run_id=task_run_id,
                result_summary="Awaiting owner confirmation for stock-in details.",
            )
            write_runtime_message(
                db_session,
                session_id=context.session_id,
                task_run_id=task_run_id,
                text="Please confirm the stock-in details before commit.",
            )
            db_session.commit()
            return RuntimeProcessResult(
                status="awaiting-confirmation",
                task_run_id=task_run_id,
                task_type=decision.task_type,
                error_code=None,
            )

        result_summary, runtime_text = summarize_completed_task(
            task_type=decision.task_type,
            transcript=decision.transcript,
        )
        complete_task_run(
            db_session,
            task_run_id=task_run_id,
            task_type=decision.task_type,
            assigned_employee_id=decision.assigned_employee_id,
            result_summary=result_summary,
        )
        write_runtime_message(
            db_session,
            session_id=context.session_id,
            task_run_id=task_run_id,
            text=runtime_text,
        )
        db_session.commit()
        return RuntimeProcessResult(
            status="completed",
            task_run_id=task_run_id,
            task_type=decision.task_type,
            error_code=None,
        )
```

`backend/tests/test_runtime_tasks.py`

```python
def test_runtime_task_wrapper_returns_awaiting_confirmation_payload(monkeypatch) -> None:
    fake_session = _FakeSession()

    def fake_get_session_factory():
        return lambda: fake_session

    def fake_process_task_run(db_session, task_run_id: str) -> RuntimeProcessResult:
        assert db_session is fake_session
        assert task_run_id == "task_awaiting_123"
        return RuntimeProcessResult(
            status="awaiting-confirmation",
            task_run_id=task_run_id,
            task_type="voice-stock-in",
            error_code=None,
        )

    monkeypatch.setattr(runtime_tasks, "get_session_factory", fake_get_session_factory)
    monkeypatch.setattr(runtime_tasks, "run_runtime_processor", fake_process_task_run)

    result = runtime_tasks.process_task_run("task_awaiting_123")

    assert result == {
        "status": "awaiting-confirmation",
        "task_run_id": "task_awaiting_123",
        "task_type": "voice-stock-in",
        "error_code": None,
    }
```

- [ ] **Step 4: Re-run the runtime confirmation tests to verify they pass**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_runtime_processor.py backend/tests/test_runtime_tasks.py -q
```

Expected:

- stock-in runtime tests now pass with `awaiting-confirmation`
- wrapper tests still pass

- [ ] **Step 5: Commit**

```bash
git add backend/app/runtime/policy.py backend/app/runtime/processor.py backend/app/runtime/context.py backend/tests/test_runtime_processor.py backend/tests/test_runtime_tasks.py
git commit -m "feat: pause stock-in runtime for confirmation"
```

### Task 4: Add confirmation API routes and task-run projection

**Files:**
- Create: `backend/app/api/routes/confirmations.py`
- Modify: `backend/app/api/router.py`
- Modify: `backend/app/api/routes/task_runs.py`
- Modify: `backend/tests/test_task_runs.py`
- Create: `backend/tests/test_confirmations_api.py`

- [ ] **Step 1: Write the failing confirmation API tests**

```python
from app.api.routes import messages as message_routes


def test_list_pending_confirmations_returns_runtime_created_confirmation(client, monkeypatch) -> None:
    monkeypatch.setattr(message_routes, "enqueue_runtime_task", lambda _task_run_id: True)

    create_response = client.post(
        "/api/v1/sessions/sess_default/messages",
        headers={"Authorization": "Bearer mock_owner_token"},
        json={
            "message_type": "text",
            "text": "restock apples today",
            "media_ids": [],
            "client_request_id": "confirmations_api_001",
        },
    )
    task_run_id = create_response.json()["data"]["task_run_id"]

    from app.db.session import get_session_factory
    from app.runtime.processor import process_task_run

    db_session = get_session_factory()()
    try:
        process_task_run(db_session, task_run_id)
    finally:
        db_session.close()

    response = client.get(
        "/api/v1/confirmations?status=pending&limit=20",
        headers={"Authorization": "Bearer mock_owner_token"},
    )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert len(payload) == 1
    assert payload[0]["task_run_id"] == task_run_id
    assert payload[0]["status"] == "pending"
    assert payload[0]["confirmation_type"] == "low-confidence-recognition"


def test_approve_confirmation_completes_task_run_and_writes_resolution(client, monkeypatch) -> None:
    monkeypatch.setattr(message_routes, "enqueue_runtime_task", lambda _task_run_id: True)

    create_response = client.post(
        "/api/v1/sessions/sess_default/messages",
        headers={"Authorization": "Bearer mock_owner_token"},
        json={
            "message_type": "text",
            "text": "restock apples today",
            "media_ids": [],
            "client_request_id": "confirmations_api_002",
        },
    )
    task_run_id = create_response.json()["data"]["task_run_id"]

    from app.db.session import get_session_factory
    from app.runtime.processor import process_task_run

    db_session = get_session_factory()()
    try:
        process_task_run(db_session, task_run_id)
    finally:
        db_session.close()

    pending = client.get(
        "/api/v1/confirmations?status=pending&limit=20",
        headers={"Authorization": "Bearer mock_owner_token"},
    ).json()["data"][0]

    approve_response = client.post(
        f"/api/v1/confirmations/{pending['confirmation_id']}/approve",
        headers={"Authorization": "Bearer mock_owner_token"},
        json={"fields": {"item_name": "Apple", "quantity": 3, "unit": "box", "price": 18.5}},
    )
    task_run_response = client.get(
        f"/api/v1/task-runs/{task_run_id}",
        headers={"Authorization": "Bearer mock_owner_token"},
    )

    assert approve_response.status_code == 200
    assert approve_response.json()["data"]["status"] == "approved"
    assert task_run_response.status_code == 200
    assert task_run_response.json()["data"]["status"] == "completed"
    assert task_run_response.json()["data"]["confirmation_id"] == pending["confirmation_id"]


def test_reject_confirmation_marks_task_run_rejected(client, monkeypatch) -> None:
    monkeypatch.setattr(message_routes, "enqueue_runtime_task", lambda _task_run_id: True)

    create_response = client.post(
        "/api/v1/sessions/sess_default/messages",
        headers={"Authorization": "Bearer mock_owner_token"},
        json={
            "message_type": "text",
            "text": "restock apples today",
            "media_ids": [],
            "client_request_id": "confirmations_api_003",
        },
    )
    task_run_id = create_response.json()["data"]["task_run_id"]

    from app.db.session import get_session_factory
    from app.runtime.processor import process_task_run

    db_session = get_session_factory()()
    try:
        process_task_run(db_session, task_run_id)
    finally:
        db_session.close()

    pending = client.get(
        "/api/v1/confirmations?status=pending&limit=20",
        headers={"Authorization": "Bearer mock_owner_token"},
    ).json()["data"][0]

    reject_response = client.post(
        f"/api/v1/confirmations/{pending['confirmation_id']}/reject",
        headers={"Authorization": "Bearer mock_owner_token"},
    )
    task_run_response = client.get(
        f"/api/v1/task-runs/{task_run_id}",
        headers={"Authorization": "Bearer mock_owner_token"},
    )

    assert reject_response.status_code == 200
    assert reject_response.json()["data"]["status"] == "rejected"
    assert task_run_response.status_code == 200
    assert task_run_response.json()["data"]["status"] == "rejected"
```

- [ ] **Step 2: Run the confirmation API tests to verify they fail**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_confirmations_api.py backend/tests/test_task_runs.py -q
```

Expected:

- import failures for `app.api.routes.confirmations` or assertion failures because task-run payload lacks `confirmation_id`

- [ ] **Step 3: Add confirmation routes and enrich task-run projection**

`backend/app/api/routes/confirmations.py`

```python
from fastapi import APIRouter, Depends, Header, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.contracts.common import DataEnvelope, ErrorBody, ErrorEnvelope
from app.contracts.confirmation import (
    ApproveConfirmationRequest,
    ConfirmationData,
    ListConfirmationsMeta,
    ListConfirmationsResponse,
)
from app.db.session import get_db_session
from app.models import Confirmation, TaskRun
from app.services.confirmations import (
    ConfirmationNotPendingError,
    approve_confirmation,
    list_confirmations,
    reject_confirmation,
)
from app.services.runtime_messages import write_runtime_message
from app.services.task_runs import (
    reject_awaiting_confirmation_task_run,
    resolve_awaiting_confirmation_task_run,
)

router = APIRouter(prefix="/api/v1/confirmations", tags=["confirmations"])


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


def _to_confirmation_data(db_session: Session, confirmation: Confirmation) -> ConfirmationData:
    task_run = db_session.get(TaskRun, confirmation.task_run_id)
    if task_run is None:
        raise LookupError(confirmation.task_run_id)
    return ConfirmationData(
        confirmation_id=confirmation.confirmation_id,
        task_run_id=confirmation.task_run_id,
        session_id=task_run.session_id,
        confirmation_type=confirmation.confirmation_type,
        status=confirmation.status,
        fields=confirmation.fields,
        resolution_payload=confirmation.resolution_payload,
        requested_by_employee_id=confirmation.requested_by_employee_id,
        approved_by_actor_id=confirmation.approved_by_actor_id,
        created_at=confirmation.created_at,
        resolved_at=confirmation.resolved_at,
    )
```

Continue the same file with:

```python
@router.get("", response_model=ListConfirmationsResponse)
def get_confirmations(
    authorization: str | None = Header(default=None),
    status_value: str = Query(alias="status", default="pending"),
    limit: int = Query(default=20, ge=1, le=50),
    db_session: Session = Depends(get_db_session),
) -> ListConfirmationsResponse | JSONResponse:
    if authorization != "Bearer mock_owner_token":
        return _unauthorized()

    page = list_confirmations(db_session, status=status_value, limit=limit)
    return ListConfirmationsResponse(
        data=[_to_confirmation_data(db_session, item) for item in page.items],
        meta=ListConfirmationsMeta(count=len(page.items)),
    )


@router.post("/{confirmation_id}/approve", response_model=DataEnvelope[ConfirmationData])
def post_approve_confirmation(
    confirmation_id: str,
    payload: ApproveConfirmationRequest,
    authorization: str | None = Header(default=None),
    db_session: Session = Depends(get_db_session),
) -> DataEnvelope[ConfirmationData] | JSONResponse:
    if authorization != "Bearer mock_owner_token":
        return _unauthorized()
    if not payload.fields:
        return _error_response(status.HTTP_422_UNPROCESSABLE_ENTITY, "validation_error", "fields is required")

    try:
        confirmation = approve_confirmation(
            db_session,
            confirmation_id=confirmation_id,
            resolution_payload={"fields": payload.fields},
            approved_by_actor_id="owner_default",
        )
    except LookupError:
        return _error_response(status.HTTP_404_NOT_FOUND, "confirmation_not_found", "Confirmation not found")
    except ConfirmationNotPendingError:
        return _error_response(status.HTTP_409_CONFLICT, "confirmation_not_pending", "Confirmation is not pending")

    task_run = resolve_awaiting_confirmation_task_run(
        db_session,
        task_run_id=confirmation.task_run_id,
        result_summary="Owner approved confirmation. Business commit is deferred to a later phase.",
    )
    write_runtime_message(
        db_session,
        session_id=task_run.session_id,
        task_run_id=task_run.task_run_id,
        text="Confirmation approved. Inventory and audit commit are deferred to a later phase.",
    )
    db_session.commit()
    return DataEnvelope(data=_to_confirmation_data(db_session, confirmation))


@router.post("/{confirmation_id}/reject", response_model=DataEnvelope[ConfirmationData])
def post_reject_confirmation(
    confirmation_id: str,
    authorization: str | None = Header(default=None),
    db_session: Session = Depends(get_db_session),
) -> DataEnvelope[ConfirmationData] | JSONResponse:
    if authorization != "Bearer mock_owner_token":
        return _unauthorized()

    try:
        confirmation = reject_confirmation(db_session, confirmation_id=confirmation_id)
    except LookupError:
        return _error_response(status.HTTP_404_NOT_FOUND, "confirmation_not_found", "Confirmation not found")
    except ConfirmationNotPendingError:
        return _error_response(status.HTTP_409_CONFLICT, "confirmation_not_pending", "Confirmation is not pending")

    task_run = reject_awaiting_confirmation_task_run(
        db_session,
        task_run_id=confirmation.task_run_id,
        result_summary="Owner rejected the pending stock-in confirmation.",
    )
    write_runtime_message(
        db_session,
        session_id=task_run.session_id,
        task_run_id=task_run.task_run_id,
        text="Confirmation rejected. No business changes were committed.",
    )
    db_session.commit()
    return DataEnvelope(data=_to_confirmation_data(db_session, confirmation))
```

`backend/app/api/routes/task_runs.py`

```python
from sqlalchemy import select

from app.models import Confirmation, TaskRun


def _load_confirmation_id(db_session: Session, task_run_id: str) -> str | None:
    return db_session.scalar(
        select(Confirmation.confirmation_id).where(Confirmation.task_run_id == task_run_id)
    )
```

and return:

```python
TaskRunData(
    task_run_id=task_run.task_run_id,
    session_id=task_run.session_id,
    source_message_id=task_run.source_message_id,
    task_type=task_run.task_type,
    status=task_run.status,
    assigned_employee_id=task_run.assigned_employee_id,
    confirmation_id=_load_confirmation_id(db_session, task_run.task_run_id),
    result_summary=task_run.result_summary,
    error_code=task_run.error_code,
    error_message=task_run.error_message,
    created_at=task_run.created_at,
    updated_at=task_run.updated_at,
    completed_at=task_run.completed_at,
)
```

`backend/app/api/router.py`

```python
from app.api.routes.confirmations import router as confirmations_router

api_router.include_router(confirmations_router)
```

Update `backend/tests/test_task_runs.py` to assert `confirmation_id is None` for fresh created tasks, and add a new case that shows `confirmation_id` appears after runtime creates a pending confirmation.

- [ ] **Step 4: Re-run the confirmation API tests to verify they pass**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_confirmations_api.py backend/tests/test_task_runs.py -q
```

Expected:

- all confirmation API and task-run projection tests pass

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/routes/confirmations.py backend/app/api/router.py backend/app/api/routes/task_runs.py backend/tests/test_confirmations_api.py backend/tests/test_task_runs.py
git commit -m "feat: add confirmation approval and rejection routes"
```

### Task 5: Verify the full Phase 4B slice and refresh runtime docs

**Files:**
- Modify: `backend/app/runtime/README.md`
- Modify: `infra/docker/README.md`

- [ ] **Step 1: Update runtime and infra docs**

`backend/app/runtime/README.md`

```md
# Runtime Skeleton

Phase 4B extends the runtime with a minimal policy boundary and explicit confirmation creation. Stock-in tasks can now pause in `awaiting-confirmation`, while query tasks still complete as read-only dry-run outcomes.

This package still does not write inventory truth, audit truth, alerts, session stream events, or WebSocket fanout.
```

`infra/docker/README.md`

```md
Phase 4B adds durable confirmation persistence and owner approval/rejection routes on top of the Phase 4A runtime worker. Approval in this phase records human resolution only; inventory, audit, and realtime fanout remain future work.
```

- [ ] **Step 2: Run the confirmation-focused backend tests**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_confirmations_service.py backend/tests/test_task_run_transitions.py backend/tests/test_runtime_processor.py backend/tests/test_runtime_tasks.py backend/tests/test_confirmations_api.py backend/tests/test_task_runs.py -q
```

Expected:

- all confirmation-focused tests pass

- [ ] **Step 3: Run the full verification suite**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests -q
npm --prefix apps/mobile test -- --runInBand
docker compose -f infra/docker/docker-compose.yml --env-file .env.example config
git status --short
```

Expected:

- backend tests all pass
- mobile tests pass
- compose config exits `0`
- git status only shows the Phase 4B files before the final docs commit

- [ ] **Step 4: Commit the verification/docs finish**

```bash
git add backend/app/runtime/README.md infra/docker/README.md
git commit -m "test: verify phase 4b confirmation foundation"
```
