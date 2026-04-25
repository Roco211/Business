# Phase C1-C4 Backend Hardening Plan

Date: 2026-04-25
Branch: hermes/ai-native-saas-rewrite
Scope: backend only

## Summary

This phase continues after the pushed Phase B10 baseline. The work is ordered as:

1. C1 formal stock-out HTTP regression.
2. C2 inventory query isolation and soft-delete regression.
3. C3 Docker backend acceptance one-command script.
4. C4 real AI provider readiness documentation.

## Phase C1: Formal stock-out API HTTP regression

Added pytest coverage for `POST /api/v2/inventory/stock-out`.

Acceptance criteria:

- Authenticates through real `/api/v2/auth/login`.
- Selects context through real `/api/v2/context/select`.
- Sends both `Authorization` and `X-Context-Token` headers.
- Successful stock-out writes `V2InventoryLedgerEvent(event_type="stock_out")`.
- Successful stock-out uses negative `quantity_delta` and decrements `V2InventoryStockSnapshot.current_quantity`.
- Stale `expected_quantity` returns 409 and writes no ledger event.
- Insufficient stock returns validation error and writes no ledger event.
- Foreign-tenant item returns 404 and writes no ledger/snapshot side effects.

Files:

- `backend/tests/test_v2_inventory_stock_out_http_flow.py`

## Phase C2: Inventory query isolation and soft-delete regression

Added pytest coverage for query-side isolation and fixed the service filters.

Acceptance criteria:

- `GET /api/v2/inventory/items` returns only active items in the current tenant.
- `GET /api/v2/inventory/stock` returns only current shop snapshots whose joined item is active and belongs to the current tenant.
- `GET /api/v2/inventory/events` returns only current shop ledger events whose joined item is active and belongs to the current tenant.
- Deleted items do not appear in items, stock, or events lists.
- Same-tenant other-shop stock/events do not leak into current shop query results.
- Foreign-tenant items, snapshots, and events do not leak.

Files:

- `backend/tests/test_v2_inventory_query_isolation_http_flow.py`
- `backend/app/services/v2_inventory.py`

Implementation note:

The service layer now applies `V2InventoryItem.status == "active"` and explicit joined-item tenant constraints in inventory list/stock/event queries.

## Phase C3: Docker backend acceptance script

Added a repeatable script for the Docker validation workflow that was previously executed manually.

Script:

- `backend/scripts/run_docker_backend_acceptance.sh`

What it does:

1. Removes the old `business-backend` container if present.
2. Builds `business-backend-test` from `backend/Dockerfile`.
3. Starts `business-backend` on host port 8001 with mock providers.
4. Deletes any container-side copied SQLite DB files.
5. Writes a temporary container-valid Alembic config at `/tmp/alembic.ini`.
6. Runs Alembic `upgrade head` inside the container.
7. Bootstraps V2 trial/demo data inside the same container runtime.
8. Verifies `/health` and `/api/v2/health`.
9. Verifies container DB Alembic version and table count.
10. Runs Phase 8, Phase 9, and Phase 10 acceptance scripts from the host against the Docker backend.

Default command:

```bash
bash backend/scripts/run_docker_backend_acceptance.sh
```

Optional overrides:

```bash
IMAGE_NAME=business-backend-test CONTAINER_NAME=business-backend HOST_PORT=8001 \
  bash backend/scripts/run_docker_backend_acceptance.sh
```

## Phase C4: Real AI Provider readiness

Added a provider readiness document for switching from mock local-demo validation to live/trial provider validation.

Document:

- `docs/superpowers/plans/2026-04-25-phase-c4-provider-readiness.md`

The document intentionally does not contain secrets. Any API key, token, password, or connection string must be supplied through environment variables or a local `.env` file and represented in docs as `[REDACTED]` only.

## Verification commands

Focused pytest regression:

```bash
PYTHONPATH=backend pytest -q \
  backend/tests/test_v2_inventory_stock_out_http_flow.py \
  backend/tests/test_v2_inventory_query_isolation_http_flow.py \
  backend/tests/test_v2_inventory_stock_in_http_flow.py
```

Static/syntax checks:

```bash
PYTHONPATH=backend python3 -m compileall -q backend/app backend/tests backend/scripts
bash -n backend/scripts/run_docker_backend_acceptance.sh
git diff --check
```

Docker acceptance:

```bash
bash backend/scripts/run_docker_backend_acceptance.sh
```
