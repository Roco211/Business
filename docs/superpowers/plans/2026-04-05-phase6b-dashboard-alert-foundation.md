# Phase 6B Dashboard and Low-Stock Alert Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add durable low-stock alert truth, backend dashboard/alert read APIs, and a minimally useful mobile `DashboardScreen`.

**Architecture:** Extend the inventory commit path with alert refresh semantics, add a new `alerts` persistence layer and a summary aggregation service, then wire the mobile dashboard to lightweight fetch hooks for summary, low-stock alerts, and pending confirmations.

**Tech Stack:** Python, FastAPI, SQLAlchemy, Alembic, pytest, TypeScript, Expo, React Native, Jest, Testing Library

---

### Task 1: Add alert persistence and refresh logic

**Files:**
- Create: `backend/app/models/alert.py`
- Modify: `backend/app/models/__init__.py`
- Create: `backend/alembic/versions/20260405_01_create_alerts.py`
- Create: `backend/app/services/alerts.py`
- Modify: `backend/app/services/approved_stock_in_commits.py`
- Create: `backend/tests/test_alerts_service.py`

- [ ] Write failing service tests for low-stock alert open/update/resolve behavior.
- [ ] Run `python -m pytest backend/tests/test_alerts_service.py -q` and observe failure.
- [ ] Implement alert model, migration, refresh service, and approval-path integration.
- [ ] Re-run the alert service tests until they pass.
- [ ] Commit with `feat: add low stock alert persistence`.

### Task 2: Add dashboard summary and alerts read routes

**Files:**
- Create: `backend/app/contracts/alert.py`
- Create: `backend/app/contracts/dashboard.py`
- Create: `backend/app/services/dashboard.py`
- Create: `backend/app/api/routes/alerts.py`
- Create: `backend/app/api/routes/dashboard.py`
- Modify: `backend/app/api/router.py`
- Create: `backend/tests/test_alerts_api.py`
- Create: `backend/tests/test_dashboard_api.py`

- [ ] Write failing API tests for dashboard summary and low-stock alerts.
- [ ] Run `python -m pytest backend/tests/test_alerts_api.py backend/tests/test_dashboard_api.py -q` and observe failure.
- [ ] Implement contracts, aggregation services, and read routes with auth and validation errors.
- [ ] Re-run the API tests until they pass.
- [ ] Commit with `feat: add dashboard and alert read routes`.

### Task 3: Wire the mobile dashboard surface

**Files:**
- Create: `apps/mobile/src/features/dashboard/hooks/useDashboardSummaryQuery.ts`
- Create: `apps/mobile/src/features/dashboard/hooks/useLowStockAlertsQuery.ts`
- Create: `apps/mobile/src/features/dashboard/hooks/usePendingConfirmationsQuery.ts`
- Modify: `apps/mobile/src/features/dashboard/screens/DashboardScreen.tsx`
- Create: `apps/mobile/__tests__/DashboardScreen.test.tsx`

- [ ] Write a failing dashboard screen test covering summary, low-stock alerts, and pending confirmations.
- [ ] Run `npm --prefix apps/mobile test -- --runInBand DashboardScreen.test.tsx` and observe failure.
- [ ] Implement the hooks and `DashboardScreen` rendering.
- [ ] Re-run the dashboard test until it passes.
- [ ] Commit with `feat: add dashboard alert overview screen`.

### Task 4: Update docs and verify the phase

**Files:**
- Modify: `backend/app/runtime/README.md`
- Modify: `infra/docker/README.md`

- [ ] Document the new dashboard and alert read surface.
- [ ] Run `python -m pytest backend/tests -q`.
- [ ] Run `npm --prefix apps/mobile test -- --runInBand`.
- [ ] Run `docker compose -f infra/docker/docker-compose.yml --env-file .env.example config`.
- [ ] Run `git status --short --branch`.
- [ ] Commit with `docs: document dashboard alert read surface`.
- [ ] Commit verification with `test: verify phase 6b dashboard alert foundation`.
