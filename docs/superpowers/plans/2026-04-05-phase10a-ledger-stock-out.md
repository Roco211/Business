# Phase 10A Ledger Stock-Out Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a manual ledger-driven stock-out write path with durable inventory events, audit logs, alert refreshes, and a minimal stock-out form in the mobile ledger.

**Architecture:** Reuse the existing correction pipeline shape. Add a dedicated backend stock-out service plus API contract, then extend `LedgerScreen` with a small action-specific form that submits the new route and refreshes durable reads.

**Tech Stack:** FastAPI, SQLAlchemy, pytest, Expo React Native, Jest

---

## File Structure

- Create:
  - `backend/app/services/inventory_stock_outs.py`
- Modify:
  - `backend/app/contracts/inventory_event.py`
  - `backend/app/api/routes/inventory_events.py`
  - `backend/app/services/inventory_events.py`
  - `backend/app/services/audit_logs.py`
  - `backend/tests/test_inventory_events_api.py`
  - `apps/mobile/src/features/ledger/screens/LedgerScreen.tsx`
  - `apps/mobile/src/features/ledger/hooks/useCreateStockOutMutation.ts`
  - `apps/mobile/__tests__/LedgerScreen.test.tsx`
  - `project_docs/02-api-contract.md`
  - `project_docs/11-realtime-contract-implementation-status.md`

### Task 1: Write Red Tests For Backend Stock-Out

- [ ] Add failing API tests in `backend/tests/test_inventory_events_api.py` for:
  - successful stock-out write
  - stale snapshot conflict
  - insufficient stock validation
- [ ] Run `$env:PYTHONPATH='backend'; python -m pytest backend/tests/test_inventory_events_api.py -q` and confirm the new tests fail.
- [ ] Commit the red-test slice.

### Task 2: Implement Durable Stock-Out Backend

- [ ] Extend `backend/app/contracts/inventory_event.py` with stock-out request/response models.
- [ ] Add `append_stock_out_event()` in `backend/app/services/inventory_events.py`.
- [ ] Add `backend/app/services/inventory_stock_outs.py` for validation, audit, alert refresh, and session-stream projection writes.
- [ ] Add `inventory.stock_out_submitted` audit logging in `backend/app/services/audit_logs.py`.
- [ ] Wire `POST /api/v1/inventory-events/stock-out` in `backend/app/api/routes/inventory_events.py`.
- [ ] Run the targeted stock-out API tests, then the full backend suite.
- [ ] Commit the backend slice.

### Task 3: Write Red Tests For Ledger Stock-Out UI

- [ ] Add failing ledger tests in `apps/mobile/__tests__/LedgerScreen.test.tsx` for:
  - successful stock-out submission
  - recoverable stock-out conflict/error
- [ ] Run `npm.cmd test -- --runInBand -- LedgerScreen.test.tsx` and confirm the new tests fail.
- [ ] Commit the red-test slice if useful; otherwise keep it with the UI implementation slice.

### Task 4: Implement Ledger Stock-Out UI

- [ ] Add `useCreateStockOutMutation.ts` alongside the existing correction hook.
- [ ] Update `LedgerScreen.tsx` to support action-specific forms for correction and stock-out without breaking search or realtime refresh.
- [ ] Keep the UI intentionally minimal: one quantity field, one reason field, one submit button.
- [ ] Run:
  - `npm.cmd test -- --runInBand -- LedgerScreen.test.tsx`
  - `npm.cmd test -- --runInBand`
- [ ] Commit the mobile slice.

### Task 5: Update Docs And Final Verification

- [ ] Update `project_docs/02-api-contract.md` with the new stock-out route.
- [ ] Update `project_docs/11-realtime-contract-implementation-status.md` so ledger stock-out is reflected in the implemented read/write surface.
- [ ] Run final verification:
  - `$env:PYTHONPATH='backend'; python -m pytest backend/tests -q`
  - `npm.cmd test -- --runInBand`
  - `docker compose -f infra/docker/docker-compose.yml --env-file .env.example config`
- [ ] Commit the docs and verification slice.
