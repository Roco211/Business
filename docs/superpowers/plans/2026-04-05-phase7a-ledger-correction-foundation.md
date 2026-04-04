# Phase 7A Ledger Correction Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the first manual correction write flow so the ledger can update inventory truth, audit truth, and low-stock alert truth end-to-end.

**Architecture:** Extend the backend inventory domain with a dedicated correction command, expose it through an `inventory-events/corrections` route, then wire a minimal correction form into `LedgerScreen` using the lightweight mobile fetch layer.

**Tech Stack:** Python, FastAPI, SQLAlchemy, pytest, TypeScript, Expo, React Native, Jest, Testing Library

---

### Task 1: Add backend correction command and tests

**Files:**
- Create: `backend/app/contracts/inventory_event.py`
- Create: `backend/app/services/inventory_corrections.py`
- Modify: `backend/app/services/inventory_events.py`
- Create: `backend/tests/test_inventory_corrections_service.py`

- [ ] Write failing correction service tests for validation, inventory event writes, audit writes, and alert refresh.
- [ ] Run `python -m pytest backend/tests/test_inventory_corrections_service.py -q` and observe failure.
- [ ] Implement correction contracts and command service.
- [ ] Re-run the correction service tests until they pass.
- [ ] Commit with `feat: add inventory correction service`.

### Task 2: Add correction API route and tests

**Files:**
- Create: `backend/app/api/routes/inventory_events.py`
- Modify: `backend/app/api/router.py`
- Create: `backend/tests/test_inventory_events_api.py`

- [ ] Write failing API tests for `POST /api/v1/inventory-events/corrections`.
- [ ] Run `python -m pytest backend/tests/test_inventory_events_api.py -q` and observe failure.
- [ ] Implement the correction route and error mapping.
- [ ] Re-run the API tests until they pass.
- [ ] Commit with `feat: add inventory correction route`.

### Task 3: Wire ledger correction UI and tests

**Files:**
- Create: `apps/mobile/src/features/ledger/hooks/useCreateCorrectionMutation.ts`
- Modify: `apps/mobile/src/features/ledger/hooks/useInventoryItemsQuery.ts`
- Modify: `apps/mobile/src/features/ledger/hooks/useAuditLogsQuery.ts`
- Modify: `apps/mobile/src/features/ledger/screens/LedgerScreen.tsx`
- Modify: `apps/mobile/__tests__/LedgerScreen.test.tsx`

- [ ] Write or extend the failing ledger test to cover correction submission and refresh.
- [ ] Run `npm.cmd test -- --runInBand LedgerScreen.test.tsx` in `apps/mobile` and observe failure.
- [ ] Implement the mutation hook and minimal correction UI.
- [ ] Re-run the ledger test until it passes.
- [ ] Commit with `feat: add ledger correction flow`.

### Task 4: Update docs and verify the phase

**Files:**
- Modify: `backend/app/runtime/README.md`
- Modify: `infra/docker/README.md`

- [ ] Document the new correction write surface and alert refresh semantics.
- [ ] Run `python -m pytest backend/tests -q`.
- [ ] Run `npm.cmd test -- --runInBand` in `apps/mobile`.
- [ ] Run `docker compose -f infra/docker/docker-compose.yml --env-file .env.example config`.
- [ ] Run `git status --short --branch`.
- [ ] Commit docs with `docs: document ledger correction surface`.
- [ ] Commit verification with `test: verify phase 7a ledger correction foundation`.
