# Phase 6A Inventory and Audit Read Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add inventory/audit read-side backend APIs and wire the mobile `LedgerScreen` to render inventory items plus recent audit activity from the real backend truth established in Phase 5A.

**Architecture:** Extend the existing backend with read-only inventory and audit services, typed contracts, and protected FastAPI routes, then add a lightweight Expo fetch client plus two ledger hooks that feed a minimally interactive `LedgerScreen`. Keep the scope strictly read-only and avoid introducing alerts, dashboard summary, or a full mobile data library.

**Tech Stack:** Python, FastAPI, SQLAlchemy, Pydantic, pytest, TypeScript, Expo, React Native, Jest, Testing Library

---

### Task 1: Add backend read services and contracts for inventory and audit truth

**Files:**
- Create: `backend/app/contracts/inventory_item.py`
- Create: `backend/app/contracts/audit_log.py`
- Modify: `backend/app/services/inventory_items.py`
- Modify: `backend/app/services/audit_logs.py`
- Create: `backend/tests/test_inventory_read_services.py`

- [ ] **Step 1: Write the failing backend read-service tests**

`backend/tests/test_inventory_read_services.py`

```python
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models import AuditLog, Confirmation, InventoryItem, TaskRun
from app.runtime.processor import process_task_run
from app.services.approved_stock_in_commits import commit_approved_stock_in_confirmation
from app.services.audit_logs import UnsupportedAuditScopeError, list_audit_logs
from app.services.bootstrap import ensure_default_context
from app.services.inventory_items import get_inventory_item, list_inventory_items
from app.services.messages import create_message


def _seed_committed_stock_in(db_session, *, client_request_id: str, item_name: str, quantity: int) -> str:
    context = ensure_default_context(db_session)
    message_result = create_message(
        db_session,
        session_id=context.session.session_id,
        actor_type="owner",
        actor_id="owner_default",
        message_type="text",
        text=f"restock {item_name}",
        media_ids=[],
        client_request_id=client_request_id,
    )
    runtime_result = process_task_run(db_session, message_result.task_run_id)
    assert runtime_result.status == "awaiting-confirmation"
    confirmation = db_session.scalar(
        select(Confirmation).where(Confirmation.task_run_id == message_result.task_run_id)
    )
    assert confirmation is not None
    commit_result = commit_approved_stock_in_confirmation(
        db_session,
        confirmation_id=confirmation.confirmation_id,
        payload_fields={"item_name": item_name, "quantity": quantity, "unit": "box", "price": 12.5},
        approved_by_actor_id="owner_default",
    )
    return commit_result.inventory_item.item_id


def test_list_inventory_items_orders_by_updated_at_desc_and_filters_by_query(db_session) -> None:
    older_item_id = _seed_committed_stock_in(
        db_session,
        client_request_id="inventory_read_service_older",
        item_name="Apple",
        quantity=1,
    )
    newer_item_id = _seed_committed_stock_in(
        db_session,
        client_request_id="inventory_read_service_newer",
        item_name="Orange",
        quantity=2,
    )

    all_items = list_inventory_items(db_session, shop_id="shop_default", query=None, limit=20)
    filtered_items = list_inventory_items(db_session, shop_id="shop_default", query="ora", limit=20)

    assert [item.item_id for item in all_items.items[:2]] == [newer_item_id, older_item_id]
    assert [item.name for item in filtered_items.items] == ["Orange"]


def test_get_inventory_item_returns_matching_shop_item(db_session) -> None:
    item_id = _seed_committed_stock_in(
        db_session,
        client_request_id="inventory_read_service_detail",
        item_name="Apple",
        quantity=3,
    )

    item = get_inventory_item(db_session, shop_id="shop_default", item_id=item_id)

    assert item.item_id == item_id
    assert item.current_stock == Decimal("3")


def test_get_inventory_item_raises_lookup_error_for_missing_item(db_session) -> None:
    ensure_default_context(db_session)

    with pytest.raises(LookupError):
        get_inventory_item(db_session, shop_id="shop_default", item_id="item_missing")


def test_list_audit_logs_orders_newest_first_and_requires_inventory_scope(db_session) -> None:
    _seed_committed_stock_in(
        db_session,
        client_request_id="inventory_read_service_audit_older",
        item_name="Apple",
        quantity=1,
    )
    _seed_committed_stock_in(
        db_session,
        client_request_id="inventory_read_service_audit_newer",
        item_name="Orange",
        quantity=2,
    )

    page = list_audit_logs(db_session, shop_id="shop_default", scope="inventory", limit=20)

    assert len(page.items) == 2
    assert page.items[0].created_at >= page.items[1].created_at
    assert page.items[0].scope == "inventory"

    with pytest.raises(UnsupportedAuditScopeError):
        list_audit_logs(db_session, shop_id="shop_default", scope="other", limit=20)
```

- [ ] **Step 2: Run the read-service tests to verify they fail**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_inventory_read_services.py -q
```

Expected:

- import failures for `app.contracts.inventory_item`, `list_inventory_items`, or `list_audit_logs`

- [ ] **Step 3: Add typed contracts and read-only service functions**

`backend/app/contracts/inventory_item.py`

```python
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class InventoryItemData(BaseModel):
    item_id: str
    shop_id: str
    sku: str | None
    name: str
    category: str | None
    barcode: str | None
    default_unit: str
    current_stock: Decimal
    current_price: Decimal | None
    low_stock_threshold: Decimal | None
    image_media_id: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class ListInventoryItemsMeta(BaseModel):
    count: int


class ListInventoryItemsResponse(BaseModel):
    data: list[InventoryItemData]
    meta: ListInventoryItemsMeta
```

`backend/app/contracts/audit_log.py`

```python
from datetime import datetime
from typing import Any

from pydantic import BaseModel


class AuditLogData(BaseModel):
    audit_log_id: str
    shop_id: str
    scope: str
    action: str
    actor_type: str
    actor_id: str
    task_run_id: str | None
    target_type: str | None
    target_id: str | None
    metadata: dict[str, Any]
    created_at: datetime


class ListAuditLogsMeta(BaseModel):
    count: int


class ListAuditLogsResponse(BaseModel):
    data: list[AuditLogData]
    meta: ListAuditLogsMeta
```

Append to `backend/app/services/inventory_items.py`:

```python
from dataclasses import dataclass
from sqlalchemy import or_, select
```

and add:

```python
@dataclass(frozen=True)
class InventoryItemListPage:
    items: list[InventoryItem]


def list_inventory_items(
    db_session: Session,
    *,
    shop_id: str,
    query: str | None,
    limit: int,
) -> InventoryItemListPage:
    safe_limit = max(1, min(limit, 50))
    statement = select(InventoryItem).where(
        InventoryItem.shop_id == shop_id,
        InventoryItem.is_active.is_(True),
    )
    if query:
        like_query = f"%{query.strip()}%"
        statement = statement.where(InventoryItem.name.ilike(like_query))
    statement = statement.order_by(InventoryItem.updated_at.desc(), InventoryItem.item_id.desc()).limit(safe_limit)
    return InventoryItemListPage(items=list(db_session.scalars(statement)))


def get_inventory_item(
    db_session: Session,
    *,
    shop_id: str,
    item_id: str,
) -> InventoryItem:
    item = db_session.scalar(
        select(InventoryItem).where(
            InventoryItem.shop_id == shop_id,
            InventoryItem.item_id == item_id,
            InventoryItem.is_active.is_(True),
        )
    )
    if item is None:
        raise LookupError(item_id)
    return item
```

Append to `backend/app/services/audit_logs.py`:

```python
from dataclasses import dataclass
from sqlalchemy import select
```

and add:

```python
class UnsupportedAuditScopeError(ValueError):
    pass


@dataclass(frozen=True)
class AuditLogListPage:
    items: list[AuditLog]


def list_audit_logs(
    db_session: Session,
    *,
    shop_id: str,
    scope: str,
    limit: int,
) -> AuditLogListPage:
    if scope != "inventory":
        raise UnsupportedAuditScopeError(scope)
    safe_limit = max(1, min(limit, 50))
    statement = (
        select(AuditLog)
        .where(AuditLog.shop_id == shop_id, AuditLog.scope == scope)
        .order_by(AuditLog.created_at.desc(), AuditLog.audit_log_id.desc())
        .limit(safe_limit)
    )
    return AuditLogListPage(items=list(db_session.scalars(statement)))
```

- [ ] **Step 4: Re-run the read-service tests to verify they pass**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_inventory_read_services.py -q
```

Expected:

- inventory list/detail and audit read-service tests pass

- [ ] **Step 5: Commit**

```bash
git add backend/app/contracts/inventory_item.py backend/app/contracts/audit_log.py backend/app/services/inventory_items.py backend/app/services/audit_logs.py backend/tests/test_inventory_read_services.py
git commit -m "feat: add inventory and audit read services"
```

---

### Task 2: Add protected backend read routes for inventory items and audit logs

**Files:**
- Create: `backend/app/api/routes/inventory_items.py`
- Create: `backend/app/api/routes/audit_logs.py`
- Modify: `backend/app/api/router.py`
- Create: `backend/tests/test_inventory_items_api.py`
- Create: `backend/tests/test_audit_logs_api.py`

- [ ] **Step 1: Write the failing backend API tests**

`backend/tests/test_inventory_items_api.py`

```python
from app.api.routes import messages as message_routes
from app.db.session import get_session_factory
from app.runtime.processor import process_task_run
from app.services.approved_stock_in_commits import commit_approved_stock_in_confirmation
from sqlalchemy import select

from app.models import Confirmation


AUTH_HEADERS = {"Authorization": "Bearer mock_owner_token"}


def _commit_stock_in(client, monkeypatch, *, client_request_id: str, item_name: str, quantity: int) -> str:
    monkeypatch.setattr(message_routes, "enqueue_runtime_task", lambda _task_run_id: True)
    create_response = client.post(
        "/api/v1/sessions/sess_default/messages",
        headers=AUTH_HEADERS,
        json={
            "message_type": "text",
            "text": f"restock {item_name}",
            "media_ids": [],
            "client_request_id": client_request_id,
        },
    )
    assert create_response.status_code == 201
    task_run_id = create_response.json()["data"]["task_run_id"]

    db_session = get_session_factory()()
    try:
        process_task_run(db_session, task_run_id)
        confirmation = db_session.scalar(
            select(Confirmation).where(Confirmation.task_run_id == task_run_id)
        )
        assert confirmation is not None
        result = commit_approved_stock_in_confirmation(
            db_session,
            confirmation_id=confirmation.confirmation_id,
            payload_fields={"item_name": item_name, "quantity": quantity, "unit": "box", "price": 12.5},
            approved_by_actor_id="owner_default",
        )
        return result.inventory_item.item_id
    finally:
        db_session.close()


def test_get_inventory_items_lists_active_items_newest_first(client, monkeypatch) -> None:
    older_item_id = _commit_stock_in(
        client,
        monkeypatch,
        client_request_id="inventory_items_api_older",
        item_name="Apple",
        quantity=1,
    )
    newer_item_id = _commit_stock_in(
        client,
        monkeypatch,
        client_request_id="inventory_items_api_newer",
        item_name="Orange",
        quantity=2,
    )

    response = client.get("/api/v1/inventory-items?limit=20", headers=AUTH_HEADERS)

    assert response.status_code == 200
    payload = response.json()
    assert payload["meta"]["count"] == 2
    assert [item["item_id"] for item in payload["data"][:2]] == [newer_item_id, older_item_id]


def test_get_inventory_items_filters_by_query(client, monkeypatch) -> None:
    _commit_stock_in(
        client,
        monkeypatch,
        client_request_id="inventory_items_api_query_apple",
        item_name="Apple",
        quantity=1,
    )
    _commit_stock_in(
        client,
        monkeypatch,
        client_request_id="inventory_items_api_query_orange",
        item_name="Orange",
        quantity=2,
    )

    response = client.get("/api/v1/inventory-items?query=ora", headers=AUTH_HEADERS)

    assert response.status_code == 200
    payload = response.json()
    assert [item["name"] for item in payload["data"]] == ["Orange"]


def test_get_inventory_item_returns_detail_and_not_found(client, monkeypatch) -> None:
    item_id = _commit_stock_in(
        client,
        monkeypatch,
        client_request_id="inventory_items_api_detail",
        item_name="Apple",
        quantity=3,
    )

    response = client.get(f"/api/v1/inventory-items/{item_id}", headers=AUTH_HEADERS)
    not_found_response = client.get("/api/v1/inventory-items/item_missing", headers=AUTH_HEADERS)

    assert response.status_code == 200
    assert response.json()["data"]["item_id"] == item_id
    assert response.json()["data"]["current_stock"] == "3"
    assert not_found_response.status_code == 404
    assert not_found_response.json()["error"]["code"] == "inventory_item_not_found"
```

`backend/tests/test_audit_logs_api.py`

```python
from app.api.routes import messages as message_routes
from app.db.session import get_session_factory
from app.runtime.processor import process_task_run
from app.services.approved_stock_in_commits import commit_approved_stock_in_confirmation
from sqlalchemy import select

from app.models import Confirmation


AUTH_HEADERS = {"Authorization": "Bearer mock_owner_token"}


def _commit_stock_in(client, monkeypatch, *, client_request_id: str, item_name: str, quantity: int) -> None:
    monkeypatch.setattr(message_routes, "enqueue_runtime_task", lambda _task_run_id: True)
    create_response = client.post(
        "/api/v1/sessions/sess_default/messages",
        headers=AUTH_HEADERS,
        json={
            "message_type": "text",
            "text": f"restock {item_name}",
            "media_ids": [],
            "client_request_id": client_request_id,
        },
    )
    assert create_response.status_code == 201
    task_run_id = create_response.json()["data"]["task_run_id"]

    db_session = get_session_factory()()
    try:
        process_task_run(db_session, task_run_id)
        confirmation = db_session.scalar(
            select(Confirmation).where(Confirmation.task_run_id == task_run_id)
        )
        assert confirmation is not None
        commit_approved_stock_in_confirmation(
            db_session,
            confirmation_id=confirmation.confirmation_id,
            payload_fields={"item_name": item_name, "quantity": quantity, "unit": "box", "price": 12.5},
            approved_by_actor_id="owner_default",
        )
    finally:
        db_session.close()


def test_get_audit_logs_lists_inventory_scope_newest_first(client, monkeypatch) -> None:
    _commit_stock_in(
        client,
        monkeypatch,
        client_request_id="audit_logs_api_older",
        item_name="Apple",
        quantity=1,
    )
    _commit_stock_in(
        client,
        monkeypatch,
        client_request_id="audit_logs_api_newer",
        item_name="Orange",
        quantity=2,
    )

    response = client.get("/api/v1/audit-logs?scope=inventory&limit=20", headers=AUTH_HEADERS)

    assert response.status_code == 200
    payload = response.json()
    assert payload["meta"]["count"] == 2
    assert payload["data"][0]["created_at"] >= payload["data"][1]["created_at"]
    assert payload["data"][0]["scope"] == "inventory"


def test_get_audit_logs_rejects_unsupported_scope(client) -> None:
    response = client.get("/api/v1/audit-logs?scope=other", headers=AUTH_HEADERS)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "unsupported_audit_scope"
```

- [ ] **Step 2: Run the backend API tests to verify they fail**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_inventory_items_api.py backend/tests/test_audit_logs_api.py -q
```

Expected:

- route import or 404 failures because the new read endpoints do not exist yet

- [ ] **Step 3: Add route modules, envelope mapping, and error handling**

`backend/app/api/routes/inventory_items.py`

```python
from fastapi import APIRouter, Depends, Header, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.contracts.common import DataEnvelope, ErrorBody, ErrorEnvelope
from app.contracts.inventory_item import (
    InventoryItemData,
    ListInventoryItemsMeta,
    ListInventoryItemsResponse,
)
from app.db.session import get_db_session
from app.models import InventoryItem
from app.services.inventory_items import get_inventory_item, list_inventory_items

router = APIRouter(prefix="/api/v1/inventory-items", tags=["inventory-items"])


def _unauthorized() -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content=ErrorEnvelope(
            error=ErrorBody(code="unauthorized", message="Unauthorized", details=[])
        ).model_dump(),
    )


def _not_found() -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content=ErrorEnvelope(
            error=ErrorBody(
                code="inventory_item_not_found",
                message="Inventory item not found",
                details=[],
            )
        ).model_dump(),
    )


def _to_inventory_item_data(item: InventoryItem) -> InventoryItemData:
    return InventoryItemData.model_validate(item, from_attributes=True)


@router.get("", response_model=ListInventoryItemsResponse)
def get_inventory_items(
    authorization: str | None = Header(default=None),
    query: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=50),
    db_session: Session = Depends(get_db_session),
) -> ListInventoryItemsResponse | JSONResponse:
    if authorization != "Bearer mock_owner_token":
        return _unauthorized()

    page = list_inventory_items(db_session, shop_id="shop_default", query=query, limit=limit)
    return ListInventoryItemsResponse(
        data=[_to_inventory_item_data(item) for item in page.items],
        meta=ListInventoryItemsMeta(count=len(page.items)),
    )


@router.get("/{item_id}", response_model=DataEnvelope[InventoryItemData])
def get_inventory_item_detail(
    item_id: str,
    authorization: str | None = Header(default=None),
    db_session: Session = Depends(get_db_session),
) -> DataEnvelope[InventoryItemData] | JSONResponse:
    if authorization != "Bearer mock_owner_token":
        return _unauthorized()
    try:
        item = get_inventory_item(db_session, shop_id="shop_default", item_id=item_id)
    except LookupError:
        return _not_found()
    return DataEnvelope(data=_to_inventory_item_data(item))
```

`backend/app/api/routes/audit_logs.py`

```python
from fastapi import APIRouter, Depends, Header, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.contracts.audit_log import AuditLogData, ListAuditLogsMeta, ListAuditLogsResponse
from app.contracts.common import ErrorBody, ErrorEnvelope
from app.db.session import get_db_session
from app.models import AuditLog
from app.services.audit_logs import UnsupportedAuditScopeError, list_audit_logs

router = APIRouter(prefix="/api/v1/audit-logs", tags=["audit-logs"])


def _unauthorized() -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content=ErrorEnvelope(
            error=ErrorBody(code="unauthorized", message="Unauthorized", details=[])
        ).model_dump(),
    )


def _unsupported_scope() -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=ErrorEnvelope(
            error=ErrorBody(
                code="unsupported_audit_scope",
                message="Audit scope is not supported",
                details=[],
            )
        ).model_dump(),
    )


def _to_audit_log_data(log: AuditLog) -> AuditLogData:
    return AuditLogData(
        audit_log_id=log.audit_log_id,
        shop_id=log.shop_id,
        scope=log.scope,
        action=log.action,
        actor_type=log.actor_type,
        actor_id=log.actor_id,
        task_run_id=log.task_run_id,
        target_type=log.target_type,
        target_id=log.target_id,
        metadata=log.metadata_json,
        created_at=log.created_at,
    )


@router.get("", response_model=ListAuditLogsResponse)
def get_audit_logs(
    authorization: str | None = Header(default=None),
    scope: str = Query(default="inventory"),
    limit: int = Query(default=20, ge=1, le=50),
    db_session: Session = Depends(get_db_session),
) -> ListAuditLogsResponse | JSONResponse:
    if authorization != "Bearer mock_owner_token":
        return _unauthorized()
    try:
        page = list_audit_logs(db_session, shop_id="shop_default", scope=scope, limit=limit)
    except UnsupportedAuditScopeError:
        return _unsupported_scope()
    return ListAuditLogsResponse(
        data=[_to_audit_log_data(item) for item in page.items],
        meta=ListAuditLogsMeta(count=len(page.items)),
    )
```

Update `backend/app/api/router.py` to include:

```python
from app.api.routes.audit_logs import router as audit_logs_router
from app.api.routes.inventory_items import router as inventory_items_router
```

and:

```python
api_router.include_router(inventory_items_router)
api_router.include_router(audit_logs_router)
```

- [ ] **Step 4: Re-run the backend API tests to verify they pass**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests/test_inventory_items_api.py backend/tests/test_audit_logs_api.py -q
```

Expected:

- the new read endpoints pass auth, list, detail, and scope validation coverage

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/routes/inventory_items.py backend/app/api/routes/audit_logs.py backend/app/api/router.py backend/tests/test_inventory_items_api.py backend/tests/test_audit_logs_api.py
git commit -m "feat: add inventory and audit read routes"
```

---

### Task 3: Add a lightweight mobile API client and ledger read hooks

**Files:**
- Create: `apps/mobile/src/shared/api/client.ts`
- Create: `apps/mobile/src/features/ledger/hooks/useInventoryItemsQuery.ts`
- Create: `apps/mobile/src/features/ledger/hooks/useAuditLogsQuery.ts`
- Create: `apps/mobile/__tests__/LedgerScreen.test.tsx`
- Modify: `apps/mobile/src/features/ledger/screens/LedgerScreen.tsx`

- [ ] **Step 1: Write the failing ledger screen test**

`apps/mobile/__tests__/LedgerScreen.test.tsx`

```tsx
import { fireEvent, render, screen, waitFor } from "@testing-library/react-native";

import LedgerScreen from "../src/features/ledger/screens/LedgerScreen";


describe("LedgerScreen", () => {
  beforeEach(() => {
    global.fetch = jest.fn().mockImplementation((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("/api/v1/inventory-items?query=ora")) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            data: [
              {
                item_id: "item_orange",
                shop_id: "shop_default",
                sku: null,
                name: "Orange",
                category: null,
                barcode: null,
                default_unit: "box",
                current_stock: "2",
                current_price: "12.5",
                low_stock_threshold: "5",
                image_media_id: null,
                is_active: true,
                created_at: "2026-04-05T10:00:00",
                updated_at: "2026-04-05T10:00:00",
              },
            ],
            meta: { count: 1 },
          }),
        });
      }
      if (url.includes("/api/v1/inventory-items")) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            data: [
              {
                item_id: "item_apple",
                shop_id: "shop_default",
                sku: null,
                name: "Apple",
                category: null,
                barcode: null,
                default_unit: "box",
                current_stock: "3",
                current_price: "11.5",
                low_stock_threshold: "5",
                image_media_id: null,
                is_active: true,
                created_at: "2026-04-05T09:00:00",
                updated_at: "2026-04-05T09:00:00",
              },
            ],
            meta: { count: 1 },
          }),
        });
      }
      if (url.includes("/api/v1/audit-logs")) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            data: [
              {
                audit_log_id: "audit_1",
                shop_id: "shop_default",
                scope: "inventory",
                action: "inventory.stock_in_confirmed",
                actor_type: "owner",
                actor_id: "owner_default",
                task_run_id: "task_1",
                target_type: "inventory_item",
                target_id: "item_apple",
                metadata: {
                  item_name: "Apple",
                  quantity_delta: 3,
                  quantity_after: 3,
                },
                created_at: "2026-04-05T09:00:00",
              },
            ],
            meta: { count: 1 },
          }),
        });
      }
      return Promise.resolve({
        ok: false,
        json: async () => ({
          error: { code: "unexpected", message: "Unexpected request", details: [] },
        }),
      });
    }) as jest.Mock;
  });

  afterEach(() => {
    jest.resetAllMocks();
  });

  it("renders inventory items and recent audit activity, then re-queries inventory on search", async () => {
    render(<LedgerScreen />);

    expect(screen.getByText("Loading ledger...")).toBeTruthy();
    expect(await screen.findByText("Apple")).toBeTruthy();
    expect(await screen.findByText("inventory.stock_in_confirmed")).toBeTruthy();

    fireEvent.changeText(screen.getByPlaceholderText("Search inventory"), "ora");

    await waitFor(() => {
      expect(screen.getByText("Orange")).toBeTruthy();
    });

    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining("/api/v1/inventory-items?query=ora"),
      expect.any(Object),
    );
  });
});
```

- [ ] **Step 2: Run the ledger screen test to verify it fails**

Run:

```powershell
npm --prefix apps/mobile test -- --runInBand LedgerScreen.test.tsx
```

Expected:

- missing client/hooks or shell screen assertions fail because the ledger UI is still a placeholder

- [ ] **Step 3: Add the mobile fetch client, hooks, and `LedgerScreen` rendering**

`apps/mobile/src/shared/api/client.ts`

```ts
import { Platform } from "react-native";

const DEFAULT_OWNER_TOKEN = "mock_owner_token";

function getBaseUrl(): string {
  const configuredBaseUrl = process.env.EXPO_PUBLIC_API_BASE_URL?.trim();
  if (configuredBaseUrl) {
    return configuredBaseUrl.replace(/\/+$/, "");
  }
  return Platform.OS === "android" ? "http://10.0.2.2:8001" : "http://127.0.0.1:8001";
}

export async function apiGetJson<T>(path: string): Promise<T> {
  const response = await fetch(`${getBaseUrl()}${path}`, {
    headers: {
      Authorization: `Bearer ${DEFAULT_OWNER_TOKEN}`,
    },
  });
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload?.error?.message ?? "Request failed");
  }
  return payload as T;
}
```

`apps/mobile/src/features/ledger/hooks/useInventoryItemsQuery.ts`

```ts
import { useDeferredValue, useEffect, useState } from "react";

import { apiGetJson } from "../../../shared/api/client";

export type InventoryItemRecord = {
  item_id: string;
  name: string;
  default_unit: string;
  current_stock: string;
  current_price: string | null;
};

type InventoryItemsResponse = {
  data: InventoryItemRecord[];
  meta: {
    count: number;
  };
};

export function useInventoryItemsQuery(searchText: string) {
  const deferredSearchText = useDeferredValue(searchText.trim());
  const [data, setData] = useState<InventoryItemRecord[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let isActive = true;
    setIsLoading(true);
    setError(null);

    const query = deferredSearchText ? `?query=${encodeURIComponent(deferredSearchText)}` : "";
    apiGetJson<InventoryItemsResponse>(`/api/v1/inventory-items${query}`)
      .then((response) => {
        if (!isActive) {
          return;
        }
        setData(response.data);
      })
      .catch((reason: unknown) => {
        if (!isActive) {
          return;
        }
        setError(reason instanceof Error ? reason.message : "Failed to load inventory");
      })
      .finally(() => {
        if (isActive) {
          setIsLoading(false);
        }
      });

    return () => {
      isActive = false;
    };
  }, [deferredSearchText]);

  return { data, isLoading, error };
}
```

`apps/mobile/src/features/ledger/hooks/useAuditLogsQuery.ts`

```ts
import { useEffect, useState } from "react";

import { apiGetJson } from "../../../shared/api/client";

export type AuditLogRecord = {
  audit_log_id: string;
  action: string;
  created_at: string;
  metadata: {
    item_name?: string;
    quantity_delta?: number;
    quantity_after?: number;
  };
};

type AuditLogsResponse = {
  data: AuditLogRecord[];
  meta: {
    count: number;
  };
};

export function useAuditLogsQuery() {
  const [data, setData] = useState<AuditLogRecord[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let isActive = true;
    setIsLoading(true);
    setError(null);

    apiGetJson<AuditLogsResponse>("/api/v1/audit-logs?scope=inventory")
      .then((response) => {
        if (!isActive) {
          return;
        }
        setData(response.data);
      })
      .catch((reason: unknown) => {
        if (!isActive) {
          return;
        }
        setError(reason instanceof Error ? reason.message : "Failed to load audit logs");
      })
      .finally(() => {
        if (isActive) {
          setIsLoading(false);
        }
      });

    return () => {
      isActive = false;
    };
  }, []);

  return { data, isLoading, error };
}
```

Update `apps/mobile/src/features/ledger/screens/LedgerScreen.tsx` to:

```tsx
import { useState } from "react";
import { ScrollView, Text, TextInput, View } from "react-native";

import { useAuditLogsQuery } from "../hooks/useAuditLogsQuery";
import { useInventoryItemsQuery } from "../hooks/useInventoryItemsQuery";

function formatAuditLine(itemName: string | undefined, quantityDelta: number | undefined) {
  if (!itemName) {
    return "Inventory update";
  }
  if (typeof quantityDelta !== "number") {
    return itemName;
  }
  return `${itemName} +${quantityDelta}`;
}

export default function LedgerScreen() {
  const [searchText, setSearchText] = useState("");
  const inventory = useInventoryItemsQuery(searchText);
  const auditLogs = useAuditLogsQuery();

  if (inventory.isLoading || auditLogs.isLoading) {
    return (
      <View>
        <Text>Loading ledger...</Text>
      </View>
    );
  }

  if (inventory.error || auditLogs.error) {
    return (
      <View>
        <Text>Ledger unavailable</Text>
        <Text>{inventory.error ?? auditLogs.error}</Text>
      </View>
    );
  }

  return (
    <ScrollView>
      <Text>Ledger</Text>
      <TextInput placeholder="Search inventory" value={searchText} onChangeText={setSearchText} />

      <Text>Inventory</Text>
      {inventory.data.map((item) => (
        <View key={item.item_id}>
          <Text>{item.name}</Text>
          <Text>{`${item.current_stock} ${item.default_unit}`}</Text>
          <Text>{item.current_price ? `Price ${item.current_price}` : "Price unavailable"}</Text>
        </View>
      ))}

      <Text>Recent activity</Text>
      {auditLogs.data.map((log) => (
        <View key={log.audit_log_id}>
          <Text>{log.action}</Text>
          <Text>{formatAuditLine(log.metadata.item_name, log.metadata.quantity_delta)}</Text>
          <Text>{log.created_at}</Text>
        </View>
      ))}
    </ScrollView>
  );
}
```

- [ ] **Step 4: Re-run the ledger screen test to verify it passes**

Run:

```powershell
npm --prefix apps/mobile test -- --runInBand LedgerScreen.test.tsx
```

Expected:

- the ledger screen renders inventory and audit activity from mocked fetch responses

- [ ] **Step 5: Commit**

```bash
git add apps/mobile/src/shared/api/client.ts apps/mobile/src/features/ledger/hooks/useInventoryItemsQuery.ts apps/mobile/src/features/ledger/hooks/useAuditLogsQuery.ts apps/mobile/src/features/ledger/screens/LedgerScreen.tsx apps/mobile/__tests__/LedgerScreen.test.tsx
git commit -m "feat: add ledger inventory read screen"
```

---

### Task 4: Align read-side docs with the new implementation boundary

**Files:**
- Modify: `backend/app/runtime/README.md`
- Modify: `infra/docker/README.md`

- [ ] **Step 1: Update the backend runtime README with the new read routes**

Document:

- inventory item list/detail routes
- audit log list route
- mock bearer token requirement
- the fact that `LedgerScreen` now depends on the read-side foundation rather than static shell text

- [ ] **Step 2: Update infra docs with the mobile base URL convention**

Document:

- `EXPO_PUBLIC_API_BASE_URL`
- Android emulator fallback to `http://10.0.2.2:8001`
- non-Android fallback to `http://127.0.0.1:8001`

- [ ] **Step 3: Commit**

```bash
git add backend/app/runtime/README.md infra/docker/README.md
git commit -m "docs: document inventory audit read surface"
```

---

### Task 5: Run full verification and close the phase

**Files:**
- No additional file edits expected

- [ ] **Step 1: Run the full backend suite**

Run:

```powershell
$env:PYTHONPATH="backend"; python -m pytest backend/tests -q
```

Expected:

- all backend tests pass with the new read routes and services

- [ ] **Step 2: Run the mobile test suite**

Run:

```powershell
npm --prefix apps/mobile test -- --runInBand
```

Expected:

- the existing app shell test and the new ledger screen test pass together

- [ ] **Step 3: Verify compose configuration**

Run:

```powershell
docker compose -f infra/docker/docker-compose.yml --env-file .env.example config
```

Expected:

- compose config still resolves successfully

- [ ] **Step 4: Check git state**

Run:

```powershell
git status --short --branch
```

Expected:

- only the intended Phase 6A files are changed before the final verification commit

- [ ] **Step 5: Commit the verified phase**

```bash
git add backend apps/mobile infra
git commit -m "test: verify phase 6a inventory audit read foundation"
```
