# Phase 5A Inventory and Audit Commit Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn confirmation approval for `voice-stock-in` into a real transactional inventory commit that persists `inventory_items`, `inventory_events`, and `audit_logs`, updates `current_stock`, and completes the linked task only after business truth is written.

**Architecture:** Keep the existing runtime and pending-confirmation flow unchanged, then add three layers beneath approval: durable inventory/audit persistence, a stock-in commit orchestrator that validates approved fields and writes truth in one transaction, and a thin confirmation-approve route that maps domain errors to HTTP responses. Rejection stays as-is and remains non-mutating for inventory truth.

**Tech Stack:** Python, FastAPI, SQLAlchemy, Alembic, Celery, pytest, SQLite test databases, MySQL-oriented schema design, Docker Compose

---

### Task 1: Add inventory and audit persistence primitives

**Files:**
- Create: `backend/app/models/inventory_item.py`
- Create: `backend/app/models/inventory_event.py`
- Create: `backend/app/models/audit_log.py`
- Modify: `backend/app/models/__init__.py`
- Create: `backend/app/services/inventory_items.py`
- Create: `backend/app/services/inventory_events.py`
- Create: `backend/app/services/audit_logs.py`
- Create: `backend/alembic/versions/20260404_04_create_inventory_and_audit_truth.py`
- Modify: `backend/tests/test_alembic_bootstrap.py`
- Create: `backend/tests/test_inventory_items_service.py`

- [ ] **Step 1: Write the failing schema and inventory item service tests**

`backend/tests/test_inventory_items_service.py`

```python
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models import InventoryItem
from app.services.bootstrap import ensure_default_context
from app.services.inventory_items import (
    ApprovedFieldsValidationError,
    ApprovedStockInFields,
    InventoryItemAmbiguousError,
    InventoryItemInactiveError,
    InventoryItemNotFoundError,
    InventoryUnitMismatchError,
    parse_approved_stock_in_fields,
    resolve_inventory_item_for_stock_in,
)


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _insert_item(db_session, *, item_id: str, name: str, unit: str, is_active: bool = True) -> InventoryItem:
    context = ensure_default_context(db_session)
    item = InventoryItem(
        item_id=item_id,
        shop_id=context.shop.shop_id,
        sku=None,
        name=name,
        category=None,
        barcode=None,
        default_unit=unit,
        current_stock=Decimal("0"),
        current_price=Decimal("12.50"),
        low_stock_threshold=context.shop.default_low_stock_threshold,
        image_media_id=None,
        is_active=is_active,
        created_at=_now(),
        updated_at=_now(),
    )
    db_session.add(item)
    db_session.commit()
    return item


def test_parse_approved_stock_in_fields_accepts_current_owner_payload() -> None:
    assert parse_approved_stock_in_fields(
        {"item_name": "Apple", "quantity": 3, "unit": "box", "price": 18.5}
    ) == ApprovedStockInFields(
        item_id=None,
        item_name="Apple",
        quantity=Decimal("3"),
        unit="box",
        price=Decimal("18.5"),
    )


def test_parse_approved_stock_in_fields_rejects_missing_item_reference() -> None:
    with pytest.raises(ApprovedFieldsValidationError, match="item_name"):
        parse_approved_stock_in_fields({"quantity": 3, "unit": "box", "price": 18.5})


def test_resolve_inventory_item_creates_new_item_when_name_missing(db_session) -> None:
    context = ensure_default_context(db_session)
    item = resolve_inventory_item_for_stock_in(
        db_session,
        shop=context.shop,
        fields=ApprovedStockInFields(
            item_id=None,
            item_name="Apple",
            quantity=Decimal("3"),
            unit="box",
            price=Decimal("18.5"),
        ),
    )
    assert item.shop_id == context.shop.shop_id
    assert item.name == "Apple"
    assert item.default_unit == "box"
    assert item.current_stock == Decimal("0")


def test_resolve_inventory_item_reuses_existing_item_by_item_id(db_session) -> None:
    context = ensure_default_context(db_session)
    existing = _insert_item(db_session, item_id="item_existing", name="Apple", unit="box")
    item = resolve_inventory_item_for_stock_in(
        db_session,
        shop=context.shop,
        fields=ApprovedStockInFields(
            item_id=existing.item_id,
            item_name=None,
            quantity=Decimal("2"),
            unit="box",
            price=Decimal("20"),
        ),
    )
    assert item.item_id == existing.item_id


def test_resolve_inventory_item_reuses_existing_item_by_exact_name(db_session) -> None:
    context = ensure_default_context(db_session)
    existing = _insert_item(db_session, item_id="item_by_name", name="Apple", unit="box")
    item = resolve_inventory_item_for_stock_in(
        db_session,
        shop=context.shop,
        fields=ApprovedStockInFields(
            item_id=None,
            item_name="Apple",
            quantity=Decimal("2"),
            unit="box",
            price=Decimal("20"),
        ),
    )
    assert item.item_id == existing.item_id


def test_resolve_inventory_item_rejects_unknown_item_id(db_session) -> None:
    context = ensure_default_context(db_session)
    with pytest.raises(InventoryItemNotFoundError):
        resolve_inventory_item_for_stock_in(
            db_session,
            shop=context.shop,
            fields=ApprovedStockInFields(
                item_id="item_missing",
                item_name=None,
                quantity=Decimal("2"),
                unit="box",
                price=Decimal("20"),
            ),
        )


def test_resolve_inventory_item_rejects_inactive_item_id(db_session) -> None:
    context = ensure_default_context(db_session)
    existing = _insert_item(db_session, item_id="item_inactive", name="Apple", unit="box", is_active=False)
    with pytest.raises(InventoryItemInactiveError):
        resolve_inventory_item_for_stock_in(
            db_session,
            shop=context.shop,
            fields=ApprovedStockInFields(
                item_id=existing.item_id,
                item_name=None,
                quantity=Decimal("2"),
                unit="box",
                price=Decimal("20"),
            ),
        )


def test_resolve_inventory_item_rejects_ambiguous_name_match(db_session) -> None:
    context = ensure_default_context(db_session)
    _insert_item(db_session, item_id="item_a", name="Apple", unit="box")
    _insert_item(db_session, item_id="item_b", name="Apple", unit="box")
    with pytest.raises(InventoryItemAmbiguousError):
        resolve_inventory_item_for_stock_in(
            db_session,
            shop=context.shop,
            fields=ApprovedStockInFields(
                item_id=None,
                item_name="Apple",
                quantity=Decimal("2"),
                unit="box",
                price=Decimal("20"),
            ),
        )


def test_resolve_inventory_item_rejects_unit_mismatch_for_existing_item(db_session) -> None:
    context = ensure_default_context(db_session)
    existing = _insert_item(db_session, item_id="item_unit_mismatch", name="Apple", unit="box")
    with pytest.raises(InventoryUnitMismatchError):
        resolve_inventory_item_for_stock_in(
            db_session,
            shop=context.shop,
            fields=ApprovedStockInFields(
                item_id=existing.item_id,
                item_name=None,
                quantity=Decimal("2"),
                unit="bottle",
                price=Decimal("20"),
            ),
        )
```

Modify `backend/tests/test_alembic_bootstrap.py`:

```python
    assert "inventory_items" in inspector.get_table_names()
    assert "inventory_events" in inspector.get_table_names()
    assert "audit_logs" in inspector.get_table_names()
    assert {"item_id", "shop_id", "name", "default_unit", "current_stock"} <= {
        column["name"] for column in inspector.get_columns("inventory_items")
    }
    assert {"inventory_event_id", "shop_id", "item_id", "event_type", "quantity_after"} <= {
        column["name"] for column in inspector.get_columns("inventory_events")
    }
    assert {"audit_log_id", "shop_id", "scope", "action", "metadata"} <= {
        column["name"] for column in inspector.get_columns("audit_logs")
    }
    assert "ix_inventory_items_shop_id_name" in {index["name"] for index in inspector.get_indexes("inventory_items")}
    assert "ix_inventory_events_shop_id_item_created_at" in {
        index["name"] for index in inspector.get_indexes("inventory_events")
    }
    assert "ix_audit_logs_shop_id_created_at" in {index["name"] for index in inspector.get_indexes("audit_logs")}
```

- [ ] **Step 2: Run the schema and inventory item tests to verify they fail**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_alembic_bootstrap.py backend/tests/test_inventory_items_service.py -q
```

Expected:

- import failures for `InventoryItem` or `app.services.inventory_items`
- migration assertions fail because the new tables do not exist yet

- [ ] **Step 3: Add the inventory/audit models, migration, and primitive services**

`backend/app/models/inventory_item.py`

```python
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class InventoryItem(Base):
    __tablename__ = "inventory_items"

    item_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    shop_id: Mapped[str] = mapped_column(ForeignKey("shops.shop_id"), nullable=False)
    sku: Mapped[str | None] = mapped_column(String(64), nullable=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    category: Mapped[str | None] = mapped_column(String(64), nullable=True)
    barcode: Mapped[str | None] = mapped_column(String(64), nullable=True)
    default_unit: Mapped[str] = mapped_column(String(24), nullable=False)
    current_stock: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False, default=Decimal("0"))
    current_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    low_stock_threshold: Mapped[Decimal | None] = mapped_column(Numeric(12, 3), nullable=True)
    image_media_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False)
```

`backend/app/models/inventory_event.py`

```python
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class InventoryEvent(Base):
    __tablename__ = "inventory_events"

    inventory_event_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    shop_id: Mapped[str] = mapped_column(ForeignKey("shops.shop_id"), nullable=False)
    item_id: Mapped[str] = mapped_column(ForeignKey("inventory_items.item_id"), nullable=False)
    event_type: Mapped[str] = mapped_column(String(24), nullable=False)
    quantity_delta: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    quantity_after: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    unit: Mapped[str] = mapped_column(String(24), nullable=False)
    price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    task_run_id: Mapped[str | None] = mapped_column(ForeignKey("task_runs.task_run_id"), nullable=True)
    created_by: Mapped[str] = mapped_column(String(40), nullable=False)
    reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False)
```

`backend/app/models/audit_log.py`

```python
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    audit_log_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    shop_id: Mapped[str] = mapped_column(ForeignKey("shops.shop_id"), nullable=False)
    scope: Mapped[str] = mapped_column(String(32), nullable=False)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    actor_type: Mapped[str] = mapped_column(String(16), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(40), nullable=False)
    task_run_id: Mapped[str | None] = mapped_column(ForeignKey("task_runs.task_run_id"), nullable=True)
    target_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    target_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    metadata: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False)
```

`backend/app/models/__init__.py`

```python
from app.models.audit_log import AuditLog
from app.models.confirmation import Confirmation
from app.models.inventory_event import InventoryEvent
from app.models.inventory_item import InventoryItem
from app.models.message import Message
from app.models.session_record import SessionRecord
from app.models.shop import Shop
from app.models.task_run import TaskRun
```

`backend/app/services/inventory_items.py`

```python
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.ids import new_prefixed_id
from app.models import InventoryItem, Shop


class ApprovedFieldsValidationError(ValueError):
    pass


class InventoryItemNotFoundError(LookupError):
    pass


class InventoryItemAmbiguousError(ValueError):
    pass


class InventoryItemInactiveError(ValueError):
    pass


class InventoryUnitMismatchError(ValueError):
    pass


@dataclass(frozen=True)
class ApprovedStockInFields:
    item_id: str | None
    item_name: str | None
    quantity: Decimal
    unit: str
    price: Decimal


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def parse_approved_stock_in_fields(payload: dict[str, Any]) -> ApprovedStockInFields:
    item_id = str(payload.get("item_id")).strip() or None if payload.get("item_id") is not None else None
    item_name = payload.get("item_name")
    normalized_item_name = item_name.strip() if isinstance(item_name, str) and item_name.strip() else None
    unit = payload.get("unit")
    normalized_unit = unit.strip() if isinstance(unit, str) and unit.strip() else None
    if item_id is None and normalized_item_name is None:
        raise ApprovedFieldsValidationError("item_name is required when item_id is absent")
    if normalized_unit is None:
        raise ApprovedFieldsValidationError("unit is required")
    try:
        quantity = Decimal(str(payload.get("quantity")))
        price = Decimal(str(payload.get("price")))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ApprovedFieldsValidationError("quantity and price must be numeric") from exc
    if quantity <= 0:
        raise ApprovedFieldsValidationError("quantity must be > 0")
    if price < 0:
        raise ApprovedFieldsValidationError("price must be >= 0")
    return ApprovedStockInFields(item_id=item_id, item_name=normalized_item_name, quantity=quantity, unit=normalized_unit, price=price)


def resolve_inventory_item_for_stock_in(db_session: Session, *, shop: Shop, fields: ApprovedStockInFields) -> InventoryItem:
    if fields.item_id is not None:
        item = db_session.get(InventoryItem, fields.item_id)
        if item is None or item.shop_id != shop.shop_id:
            raise InventoryItemNotFoundError(fields.item_id)
        if not item.is_active:
            raise InventoryItemInactiveError(fields.item_id)
    else:
        matches = list(
            db_session.scalars(
                select(InventoryItem).where(
                    InventoryItem.shop_id == shop.shop_id,
                    InventoryItem.name == (fields.item_name or ""),
                    InventoryItem.is_active.is_(True),
                )
            )
        )
        if len(matches) > 1:
            raise InventoryItemAmbiguousError(fields.item_name or "")
        if matches:
            item = matches[0]
        else:
            now = _now()
            item = InventoryItem(
                item_id=new_prefixed_id("item"),
                shop_id=shop.shop_id,
                sku=None,
                name=fields.item_name or "",
                category=None,
                barcode=None,
                default_unit=fields.unit,
                current_stock=Decimal("0"),
                current_price=fields.price,
                low_stock_threshold=shop.default_low_stock_threshold,
                image_media_id=None,
                is_active=True,
                created_at=now,
                updated_at=now,
            )
            db_session.add(item)
            db_session.flush()
    if item.default_unit != fields.unit:
        raise InventoryUnitMismatchError(item.item_id)
    return item
```

`backend/app/services/inventory_events.py`

```python
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.ids import new_prefixed_id
from app.models import InventoryEvent, InventoryItem


def append_stock_in_event(db_session: Session, *, item: InventoryItem, quantity: Decimal, price: Decimal, task_run_id: str, created_by: str) -> InventoryEvent:
    now = datetime.now(UTC).replace(tzinfo=None)
    quantity_after = Decimal(item.current_stock) + quantity
    event = InventoryEvent(
        inventory_event_id=new_prefixed_id("inv_evt"),
        shop_id=item.shop_id,
        item_id=item.item_id,
        event_type="stock-in",
        quantity_delta=quantity,
        quantity_after=quantity_after,
        unit=item.default_unit,
        price=price,
        source="voice-confirmed",
        task_run_id=task_run_id,
        created_by=created_by,
        reason=None,
        created_at=now,
    )
    item.current_stock = quantity_after
    item.current_price = price
    item.updated_at = now
    db_session.add(event)
    db_session.flush()
    return event
```

`backend/app/services/audit_logs.py`

```python
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.core.ids import new_prefixed_id
from app.models import AuditLog, InventoryEvent, InventoryItem


def append_inventory_stock_in_audit_log(db_session: Session, *, shop_id: str, task_run_id: str, actor_id: str, confirmation_id: str, item: InventoryItem, inventory_event: InventoryEvent) -> AuditLog:
    log = AuditLog(
        audit_log_id=new_prefixed_id("audit"),
        shop_id=shop_id,
        scope="inventory",
        action="inventory.stock_in_confirmed",
        actor_type="owner",
        actor_id=actor_id,
        task_run_id=task_run_id,
        target_type="inventory_item",
        target_id=item.item_id,
        metadata={
            "confirmation_id": confirmation_id,
            "inventory_event_id": inventory_event.inventory_event_id,
            "event_type": inventory_event.event_type,
            "item_id": item.item_id,
            "item_name": item.name,
            "quantity_delta": float(inventory_event.quantity_delta),
            "quantity_after": float(inventory_event.quantity_after),
            "unit": item.default_unit,
            "price": float(inventory_event.price or 0),
            "source": inventory_event.source,
        },
        created_at=datetime.now(UTC).replace(tzinfo=None),
    )
    db_session.add(log)
    db_session.flush()
    return log
```

`backend/alembic/versions/20260404_04_create_inventory_and_audit_truth.py`

```python
from alembic import op
import sqlalchemy as sa


revision = "20260404_04"
down_revision = "20260404_03"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "inventory_items",
        sa.Column("item_id", sa.String(length=40), nullable=False),
        sa.Column("shop_id", sa.String(length=40), nullable=False),
        sa.Column("sku", sa.String(length=64), nullable=True),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("category", sa.String(length=64), nullable=True),
        sa.Column("barcode", sa.String(length=64), nullable=True),
        sa.Column("default_unit", sa.String(length=24), nullable=False),
        sa.Column("current_stock", sa.Numeric(12, 3), nullable=False),
        sa.Column("current_price", sa.Numeric(12, 2), nullable=True),
        sa.Column("low_stock_threshold", sa.Numeric(12, 3), nullable=True),
        sa.Column("image_media_id", sa.String(length=40), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["shop_id"], ["shops.shop_id"]),
        sa.PrimaryKeyConstraint("item_id"),
    )
    op.create_index("ix_inventory_items_shop_id_name", "inventory_items", ["shop_id", "name"], unique=False)
    op.create_table(
        "inventory_events",
        sa.Column("inventory_event_id", sa.String(length=40), nullable=False),
        sa.Column("shop_id", sa.String(length=40), nullable=False),
        sa.Column("item_id", sa.String(length=40), nullable=False),
        sa.Column("event_type", sa.String(length=24), nullable=False),
        sa.Column("quantity_delta", sa.Numeric(12, 3), nullable=False),
        sa.Column("quantity_after", sa.Numeric(12, 3), nullable=False),
        sa.Column("unit", sa.String(length=24), nullable=False),
        sa.Column("price", sa.Numeric(12, 2), nullable=True),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("task_run_id", sa.String(length=40), nullable=True),
        sa.Column("created_by", sa.String(length=40), nullable=False),
        sa.Column("reason", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["shop_id"], ["shops.shop_id"]),
        sa.ForeignKeyConstraint(["item_id"], ["inventory_items.item_id"]),
        sa.ForeignKeyConstraint(["task_run_id"], ["task_runs.task_run_id"]),
        sa.PrimaryKeyConstraint("inventory_event_id"),
    )
    op.create_index("ix_inventory_events_shop_id_item_created_at", "inventory_events", ["shop_id", "item_id", "created_at"], unique=False)
    op.create_table(
        "audit_logs",
        sa.Column("audit_log_id", sa.String(length=40), nullable=False),
        sa.Column("shop_id", sa.String(length=40), nullable=False),
        sa.Column("scope", sa.String(length=32), nullable=False),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("actor_type", sa.String(length=16), nullable=False),
        sa.Column("actor_id", sa.String(length=40), nullable=False),
        sa.Column("task_run_id", sa.String(length=40), nullable=True),
        sa.Column("target_type", sa.String(length=32), nullable=True),
        sa.Column("target_id", sa.String(length=40), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["shop_id"], ["shops.shop_id"]),
        sa.ForeignKeyConstraint(["task_run_id"], ["task_runs.task_run_id"]),
        sa.PrimaryKeyConstraint("audit_log_id"),
    )
    op.create_index("ix_audit_logs_shop_id_created_at", "audit_logs", ["shop_id", "created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_audit_logs_shop_id_created_at", table_name="audit_logs")
    op.drop_table("audit_logs")
    op.drop_index("ix_inventory_events_shop_id_item_created_at", table_name="inventory_events")
    op.drop_table("inventory_events")
    op.drop_index("ix_inventory_items_shop_id_name", table_name="inventory_items")
    op.drop_table("inventory_items")
```

- [ ] **Step 4: Re-run the schema and inventory item tests to verify they pass**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_alembic_bootstrap.py backend/tests/test_inventory_items_service.py -q
```

Expected:

- migration bootstrap passes with the three new tables
- inventory item service tests pass

- [ ] **Step 5: Commit**

```bash
git add backend/app/models/inventory_item.py backend/app/models/inventory_event.py backend/app/models/audit_log.py backend/app/models/__init__.py backend/app/services/inventory_items.py backend/app/services/inventory_events.py backend/app/services/audit_logs.py backend/alembic/versions/20260404_04_create_inventory_and_audit_truth.py backend/tests/test_alembic_bootstrap.py backend/tests/test_inventory_items_service.py
git commit -m "feat: add inventory and audit persistence primitives"
```

### Task 2: Add the approved stock-in commit orchestrator

**Files:**
- Create: `backend/app/services/approved_stock_in_commits.py`
- Create: `backend/tests/test_inventory_commit_service.py`

- [ ] **Step 1: Write the failing commit-service tests**

`backend/tests/test_inventory_commit_service.py`

```python
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models import AuditLog, Confirmation, InventoryEvent, InventoryItem, Message, TaskRun
from app.runtime.processor import process_task_run
from app.services.approved_stock_in_commits import commit_approved_stock_in_confirmation
from app.services.bootstrap import ensure_default_context
from app.services.messages import create_message


def _create_pending_stock_in_confirmation(db_session, *, client_request_id: str) -> tuple[Confirmation, TaskRun]:
    context = ensure_default_context(db_session)
    result = create_message(
        db_session,
        session_id=context.session.session_id,
        actor_type="owner",
        actor_id="owner_default",
        message_type="text",
        text="restock apples today",
        media_ids=[],
        client_request_id=client_request_id,
    )
    runtime_result = process_task_run(db_session, result.task_run_id)
    assert runtime_result.status == "awaiting-confirmation"
    confirmation = db_session.scalar(select(Confirmation).where(Confirmation.task_run_id == result.task_run_id))
    task_run = db_session.get(TaskRun, result.task_run_id)
    assert confirmation is not None
    assert task_run is not None
    return confirmation, task_run


def test_commit_approved_stock_in_confirmation_writes_truth_and_completes_task(db_session) -> None:
    confirmation, task_run = _create_pending_stock_in_confirmation(
        db_session,
        client_request_id="inventory_commit_success",
    )

    result = commit_approved_stock_in_confirmation(
        db_session,
        confirmation_id=confirmation.confirmation_id,
        payload_fields={"item_name": "Apple", "quantity": 3, "unit": "box", "price": 18.5},
        approved_by_actor_id="owner_default",
    )

    persisted_confirmation = db_session.get(Confirmation, confirmation.confirmation_id)
    persisted_task_run = db_session.get(TaskRun, task_run.task_run_id)
    inventory_item = db_session.get(InventoryItem, result.inventory_item.item_id)
    inventory_event = db_session.get(InventoryEvent, result.inventory_event.inventory_event_id)
    audit_log = db_session.get(AuditLog, result.audit_log.audit_log_id)
    runtime_messages = db_session.scalars(
        select(Message)
        .where(Message.task_run_id == task_run.task_run_id, Message.actor_type == "system")
        .order_by(Message.created_at.asc(), Message.message_id.asc())
    ).all()

    assert persisted_confirmation is not None
    assert persisted_confirmation.status == "approved"
    assert persisted_task_run is not None
    assert persisted_task_run.status == "completed"
    assert inventory_item is not None
    assert inventory_item.name == "Apple"
    assert inventory_item.current_stock == Decimal("3")
    assert inventory_item.current_price == Decimal("18.5")
    assert inventory_event is not None
    assert inventory_event.event_type == "stock-in"
    assert inventory_event.quantity_delta == Decimal("3")
    assert inventory_event.quantity_after == Decimal("3")
    assert audit_log is not None
    assert audit_log.action == "inventory.stock_in_confirmed"
    assert audit_log.metadata["confirmation_id"] == confirmation.confirmation_id
    assert len(runtime_messages) == 2
    assert "committed" in (runtime_messages[-1].text or "").lower()


def test_commit_approved_stock_in_confirmation_reuses_existing_inventory_item(db_session) -> None:
    confirmation, _ = _create_pending_stock_in_confirmation(
        db_session,
        client_request_id="inventory_commit_existing_item",
    )
    context = ensure_default_context(db_session)
    existing = InventoryItem(
        item_id="item_existing_commit",
        shop_id=context.shop.shop_id,
        sku=None,
        name="Apple",
        category=None,
        barcode=None,
        default_unit="box",
        current_stock=Decimal("5"),
        current_price=Decimal("11.0"),
        low_stock_threshold=context.shop.default_low_stock_threshold,
        image_media_id=None,
        is_active=True,
        created_at=context.shop.created_at,
        updated_at=context.shop.updated_at,
    )
    db_session.add(existing)
    db_session.commit()

    commit_approved_stock_in_confirmation(
        db_session,
        confirmation_id=confirmation.confirmation_id,
        payload_fields={"item_id": existing.item_id, "quantity": 2, "unit": "box", "price": 13},
        approved_by_actor_id="owner_default",
    )

    persisted_item = db_session.get(InventoryItem, existing.item_id)
    assert persisted_item is not None
    assert persisted_item.current_stock == Decimal("7")
    assert persisted_item.current_price == Decimal("13")


def test_commit_approved_stock_in_confirmation_rolls_back_on_inner_failure(db_session, monkeypatch) -> None:
    confirmation, task_run = _create_pending_stock_in_confirmation(
        db_session,
        client_request_id="inventory_commit_rollback",
    )

    from app.services import approved_stock_in_commits as commit_service

    def blow_up(*args, **kwargs):
        raise RuntimeError("audit write failed")

    monkeypatch.setattr(commit_service, "append_inventory_stock_in_audit_log", blow_up)

    with pytest.raises(RuntimeError, match="audit write failed"):
        commit_approved_stock_in_confirmation(
            db_session,
            confirmation_id=confirmation.confirmation_id,
            payload_fields={"item_name": "Apple", "quantity": 3, "unit": "box", "price": 18.5},
            approved_by_actor_id="owner_default",
        )

    persisted_confirmation = db_session.get(Confirmation, confirmation.confirmation_id)
    persisted_task_run = db_session.get(TaskRun, task_run.task_run_id)
    assert persisted_confirmation is not None
    assert persisted_confirmation.status == "pending"
    assert persisted_task_run is not None
    assert persisted_task_run.status == "awaiting-confirmation"
    assert db_session.scalars(select(InventoryItem)).all() == []
    assert db_session.scalars(select(InventoryEvent)).all() == []
    assert db_session.scalars(select(AuditLog)).all() == []
```

- [ ] **Step 2: Run the commit-service tests to verify they fail**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_inventory_commit_service.py -q
```

Expected:

- import failure for `app.services.approved_stock_in_commits`

- [ ] **Step 3: Implement the approval-backed stock-in commit orchestrator**

`backend/app/services/approved_stock_in_commits.py`

```python
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models import AuditLog, Confirmation, InventoryEvent, InventoryItem, SessionRecord, Shop, TaskRun
from app.services.audit_logs import append_inventory_stock_in_audit_log
from app.services.confirmations import approve_confirmation
from app.services.inventory_events import append_stock_in_event
from app.services.inventory_items import ApprovedStockInFields, parse_approved_stock_in_fields, resolve_inventory_item_for_stock_in
from app.services.runtime_messages import write_runtime_message
from app.services.task_runs import resolve_awaiting_confirmation_task_run


@dataclass(frozen=True)
class ApprovedStockInCommitResult:
    confirmation: Confirmation
    task_run: TaskRun
    inventory_item: InventoryItem
    inventory_event: InventoryEvent
    audit_log: AuditLog


def _format_decimal(value: Decimal) -> str:
    text = format(value.normalize(), "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


def _require_context(db_session: Session, *, confirmation: Confirmation) -> tuple[TaskRun, SessionRecord, Shop]:
    task_run = db_session.get(TaskRun, confirmation.task_run_id)
    if task_run is None:
        raise LookupError(confirmation.task_run_id)
    session_record = db_session.get(SessionRecord, task_run.session_id)
    if session_record is None:
        raise LookupError(task_run.session_id)
    shop = db_session.get(Shop, session_record.shop_id)
    if shop is None:
        raise LookupError(session_record.shop_id)
    return task_run, session_record, shop


def commit_approved_stock_in_confirmation(db_session: Session, *, confirmation_id: str, payload_fields: dict[str, object], approved_by_actor_id: str) -> ApprovedStockInCommitResult:
    try:
        confirmation = db_session.get(Confirmation, confirmation_id)
        if confirmation is None:
            raise LookupError(confirmation_id)
        task_run, session_record, shop = _require_context(db_session, confirmation=confirmation)
        approved_fields: ApprovedStockInFields = parse_approved_stock_in_fields(payload_fields)
        confirmation = approve_confirmation(
            db_session,
            confirmation_id=confirmation_id,
            resolution_payload={"fields": payload_fields},
            approved_by_actor_id=approved_by_actor_id,
        )
        inventory_item = resolve_inventory_item_for_stock_in(db_session, shop=shop, fields=approved_fields)
        inventory_event = append_stock_in_event(
            db_session,
            item=inventory_item,
            quantity=approved_fields.quantity,
            price=approved_fields.price,
            task_run_id=task_run.task_run_id,
            created_by=approved_by_actor_id,
        )
        audit_log = append_inventory_stock_in_audit_log(
            db_session,
            shop_id=shop.shop_id,
            task_run_id=task_run.task_run_id,
            actor_id=approved_by_actor_id,
            confirmation_id=confirmation.confirmation_id,
            item=inventory_item,
            inventory_event=inventory_event,
        )
        task_run = resolve_awaiting_confirmation_task_run(
            db_session,
            task_run_id=task_run.task_run_id,
            result_summary=(
                f"Owner approved stock-in for {inventory_item.name} (+{_format_decimal(approved_fields.quantity)} {inventory_item.default_unit}). "
                f"Current stock: {_format_decimal(inventory_item.current_stock)} {inventory_item.default_unit}."
            ),
        )
        write_runtime_message(
            db_session,
            session_id=session_record.session_id,
            task_run_id=task_run.task_run_id,
            text=(
                f"Mock runtime: stock-in committed for {inventory_item.name} "
                f"(+{_format_decimal(approved_fields.quantity)} {inventory_item.default_unit}). "
                f"Current stock: {_format_decimal(inventory_item.current_stock)} {inventory_item.default_unit}."
            ),
        )
        db_session.commit()
        return ApprovedStockInCommitResult(
            confirmation=confirmation,
            task_run=task_run,
            inventory_item=inventory_item,
            inventory_event=inventory_event,
            audit_log=audit_log,
        )
    except Exception:
        db_session.rollback()
        raise
```

- [ ] **Step 4: Re-run the commit-service tests to verify they pass**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_inventory_commit_service.py -q
```

Expected:

- commit service success, reuse, and rollback tests all pass

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/approved_stock_in_commits.py backend/tests/test_inventory_commit_service.py
git commit -m "feat: commit stock-in approvals into inventory truth"
```

### Task 3: Wire confirmation approval to the commit service and expand API coverage

**Files:**
- Modify: `backend/app/api/routes/confirmations.py`
- Modify: `backend/tests/test_confirmations_api.py`

- [ ] **Step 1: Expand the confirmation API tests first**

Keep the existing pending-list and reject coverage. Extend `backend/tests/test_confirmations_api.py` with:

```python
from decimal import Decimal

from app.models import AuditLog, Confirmation, InventoryEvent, InventoryItem, Message, TaskRun
from app.services.bootstrap import ensure_default_context
```

Add these cases:

```python
def test_approve_confirmation_commits_inventory_truth_and_audit_log(client, monkeypatch) -> None:
    confirmation_id, task_run_id = _create_runtime_pending_confirmation(
        client,
        monkeypatch,
        client_request_id="confirmations_api_commit_truth",
    )

    approve_response = client.post(
        f"/api/v1/confirmations/{confirmation_id}/approve",
        headers=AUTH_HEADERS,
        json={"fields": {"item_name": "Apple", "quantity": 3, "unit": "box", "price": 18.5}},
    )

    db_session = get_session_factory()()
    try:
        confirmation = db_session.get(Confirmation, confirmation_id)
        task_run = db_session.get(TaskRun, task_run_id)
        inventory_items = db_session.scalars(select(InventoryItem)).all()
        inventory_events = db_session.scalars(select(InventoryEvent)).all()
        audit_logs = db_session.scalars(select(AuditLog)).all()
        runtime_messages = db_session.scalars(
            select(Message)
            .where(Message.task_run_id == task_run_id, Message.actor_type == "system")
            .order_by(Message.created_at.asc(), Message.message_id.asc())
        ).all()
    finally:
        db_session.close()

    assert approve_response.status_code == 200
    assert confirmation is not None
    assert confirmation.status == "approved"
    assert task_run is not None
    assert task_run.status == "completed"
    assert len(inventory_items) == 1
    assert inventory_items[0].name == "Apple"
    assert inventory_items[0].current_stock == Decimal("3")
    assert len(inventory_events) == 1
    assert inventory_events[0].event_type == "stock-in"
    assert len(audit_logs) == 1
    assert audit_logs[0].action == "inventory.stock_in_confirmed"
    assert audit_logs[0].metadata["confirmation_id"] == confirmation_id
    assert "committed" in (runtime_messages[-1].text or "").lower()


def test_approve_confirmation_returns_404_for_unknown_item_id(client, monkeypatch) -> None:
    confirmation_id, _ = _create_runtime_pending_confirmation(
        client,
        monkeypatch,
        client_request_id="confirmations_api_missing_item",
    )

    response = client.post(
        f"/api/v1/confirmations/{confirmation_id}/approve",
        headers=AUTH_HEADERS,
        json={"fields": {"item_id": "item_missing", "quantity": 2, "unit": "box", "price": 18.5}},
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "inventory_item_not_found"


def test_approve_confirmation_returns_409_for_unit_mismatch(client, monkeypatch) -> None:
    confirmation_id, _ = _create_runtime_pending_confirmation(
        client,
        monkeypatch,
        client_request_id="confirmations_api_unit_mismatch",
    )

    db_session = get_session_factory()()
    try:
        context = ensure_default_context(db_session)
        db_session.add(
            InventoryItem(
                item_id="item_unit_mismatch_api",
                shop_id=context.shop.shop_id,
                sku=None,
                name="Apple",
                category=None,
                barcode=None,
                default_unit="box",
                current_stock=Decimal("5"),
                current_price=Decimal("10"),
                low_stock_threshold=context.shop.default_low_stock_threshold,
                image_media_id=None,
                is_active=True,
                created_at=context.shop.created_at,
                updated_at=context.shop.updated_at,
            )
        )
        db_session.commit()
    finally:
        db_session.close()

    response = client.post(
        f"/api/v1/confirmations/{confirmation_id}/approve",
        headers=AUTH_HEADERS,
        json={"fields": {"item_name": "Apple", "quantity": 2, "unit": "bottle", "price": 18.5}},
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "inventory_unit_mismatch"


def test_approve_confirmation_returns_422_for_invalid_fields(client, monkeypatch) -> None:
    confirmation_id, _ = _create_runtime_pending_confirmation(
        client,
        monkeypatch,
        client_request_id="confirmations_api_invalid_fields",
    )

    response = client.post(
        f"/api/v1/confirmations/{confirmation_id}/approve",
        headers=AUTH_HEADERS,
        json={"fields": {"item_name": "Apple", "quantity": 0, "unit": "box", "price": 18.5}},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "confirmation_fields_invalid"
```

- [ ] **Step 2: Run the API tests to verify they fail**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_confirmations_api.py -q
```

Expected:

- approve success still lacks inventory/audit truth
- new error-mapping tests fail because the route does not yet delegate to the commit service

- [ ] **Step 3: Replace inline approval flow with the commit service and domain error mapping**

Update `backend/app/api/routes/confirmations.py` imports:

```python
from app.services.approved_stock_in_commits import commit_approved_stock_in_confirmation
from app.services.inventory_items import (
    ApprovedFieldsValidationError,
    InventoryItemAmbiguousError,
    InventoryItemInactiveError,
    InventoryItemNotFoundError,
    InventoryUnitMismatchError,
)
```

Replace `post_approve_confirmation()` with:

```python
@router.post("/{confirmation_id}/approve", response_model=DataEnvelope[ConfirmationData])
def post_approve_confirmation(
    confirmation_id: str,
    payload: ApproveConfirmationRequest,
    authorization: str | None = Header(default=None),
    db_session: Session = Depends(get_db_session),
) -> DataEnvelope[ConfirmationData] | JSONResponse:
    if authorization != "Bearer mock_owner_token":
        return _unauthorized()

    try:
        result = commit_approved_stock_in_confirmation(
            db_session,
            confirmation_id=confirmation_id,
            payload_fields=payload.fields,
            approved_by_actor_id="owner_default",
        )
    except LookupError:
        return _error_response(status.HTTP_404_NOT_FOUND, "confirmation_not_found", "Confirmation not found")
    except ApprovedFieldsValidationError as exc:
        return _error_response(status.HTTP_422_UNPROCESSABLE_ENTITY, "confirmation_fields_invalid", str(exc))
    except InventoryItemNotFoundError:
        return _error_response(status.HTTP_404_NOT_FOUND, "inventory_item_not_found", "Inventory item not found")
    except InventoryItemAmbiguousError:
        return _error_response(status.HTTP_409_CONFLICT, "inventory_item_ambiguous", "Inventory item match is ambiguous")
    except InventoryItemInactiveError:
        return _error_response(status.HTTP_409_CONFLICT, "inventory_item_inactive", "Inventory item is inactive")
    except InventoryUnitMismatchError:
        return _error_response(status.HTTP_409_CONFLICT, "inventory_unit_mismatch", "Inventory unit does not match the existing item")
    except (ConfirmationConflictError, TaskRunTransitionError):
        return _error_response(status.HTTP_409_CONFLICT, "confirmation_not_pending", "Confirmation is not pending")

    return DataEnvelope(data=_to_confirmation_data(result.confirmation, task_run=result.task_run))
```

Keep `post_reject_confirmation()` unchanged aside from import cleanup.

- [ ] **Step 4: Re-run the API tests to verify they pass**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_confirmations_api.py -q
```

Expected:

- approval success now creates inventory/audit truth
- validation and inventory-domain errors return the documented status codes
- reject coverage still passes unchanged

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/routes/confirmations.py backend/tests/test_confirmations_api.py
git commit -m "feat: map inventory commit results through confirmation approval"
```

### Task 4: Refresh docs for the new truth-write boundary

**Files:**
- Modify: `backend/app/runtime/README.md`
- Modify: `infra/docker/README.md`

- [ ] **Step 1: Update runtime and infra docs**

`backend/app/runtime/README.md`

```md
# Runtime Skeleton

Phase 5A keeps the Phase 4B runtime loop and confirmation boundary, but approval is no longer workflow-only.

It now includes:

- deterministic input routing for text and voice
- a minimal policy layer with `allow` and `require-confirmation`
- mock audio transcription fixtures
- runtime context assembly from persisted session data
- pending confirmation lookup for the current task run
- deterministic success and failure summarization
- approval-backed inventory and audit truth writes for `voice-stock-in`

Behavior in this phase:

- `voice-stock-query` still completes as a read-only runtime result
- `voice-stock-in` still pauses in `awaiting-confirmation`
- owner approval now commits inventory truth and audit truth
- owner rejection still resolves workflow without mutating inventory

The runtime still does not implement alerts, session stream events, or WebSocket fanout.
```

`infra/docker/README.md`

```md
Phase 5A adds durable inventory and audit truth behind confirmation approval. The local stack is still the same MySQL/Redis/MinIO/API/worker composition, but approving a pending stock-in confirmation now writes `inventory_items`, `inventory_events`, and `audit_logs` in the backend database.

Alert maintenance, session stream events, and WebSocket fanout remain future work.
```

- [ ] **Step 2: Run the focused Phase 5A backend tests**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_alembic_bootstrap.py backend/tests/test_inventory_items_service.py backend/tests/test_inventory_commit_service.py backend/tests/test_confirmations_api.py -q
```

Expected:

- the schema, inventory service, commit service, and API tests all pass together

- [ ] **Step 3: Commit**

```bash
git add backend/app/runtime/README.md infra/docker/README.md
git commit -m "docs: describe phase 5a inventory commit boundary"
```

### Task 5: Run full verification and close the phase

**Files:**
- No additional file edits expected

- [ ] **Step 1: Run the full backend suite**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests -q
```

Expected:

- all backend tests pass with the new inventory and audit truth layer

- [ ] **Step 2: Run the mobile shell test**

Run:

```powershell
npm --prefix apps/mobile test -- --runInBand
```

Expected:

- the existing mobile shell test still passes

- [ ] **Step 3: Verify compose configuration**

Run:

```powershell
docker compose -f infra/docker/docker-compose.yml --env-file .env.example config
```

Expected:

- compose config resolves successfully

- [ ] **Step 4: Check git state**

Run:

```powershell
git status --short --branch
```

Expected:

- only the intended Phase 5A files are changed before the final verification commit

- [ ] **Step 5: Commit the verified phase**

```bash
git add backend app infra docs
git commit -m "test: verify phase 5a inventory audit foundation"
```
