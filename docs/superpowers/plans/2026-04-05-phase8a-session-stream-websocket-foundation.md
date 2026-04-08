# Phase 8A Session Stream WebSocket Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a durable session event stream plus a shared mobile websocket consumer so the app can react to committed business events in realtime.

**Architecture:** Extend the backend with a persisted `session_stream_events` ledger, an append-and-publish service boundary, and a websocket session endpoint. Then add a shared session bootstrap and websocket provider in the mobile shell so Dashboard, Ledger, and Chat can respond to incoming events without introducing a cache framework.

**Tech Stack:** Python, FastAPI, SQLAlchemy, Alembic, pytest, TypeScript, Expo, React Native, Jest, Testing Library

---

### Task 1: Add durable session stream persistence and tests

**Files:**
- Create: `backend/app/models/session_stream_event.py`
- Modify: `backend/app/models/__init__.py`
- Create: `backend/app/contracts/session_stream.py`
- Create: `backend/app/services/session_stream.py`
- Create: `backend/alembic/versions/20260405_02_create_session_stream_events.py`
- Create: `backend/tests/test_session_stream_service.py`
- Modify: `backend/tests/test_alembic_bootstrap.py`

- [ ] Write failing tests for ordered per-session `seq` allocation, persisted payload shape, and `sessions.last_event_seq` updates.
- [ ] Run `python -m pytest backend/tests/test_session_stream_service.py -q` and observe failure.
- [ ] Implement the `SessionStreamEvent` model, migration, outbound event contract, and append service.
- [ ] Re-run `python -m pytest backend/tests/test_session_stream_service.py -q` until it passes.
- [ ] Run `python -m pytest backend/tests/test_alembic_bootstrap.py -q` to verify the migration chain still boots cleanly.
- [ ] Commit with `feat: add session stream persistence`.

### Task 2: Add websocket hub, route, and handshake tests

**Files:**
- Create: `backend/app/realtime/connection_manager.py`
- Create: `backend/app/api/routes/session_stream.py`
- Modify: `backend/app/api/router.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_session_stream_ws.py`

- [ ] Write failing websocket tests for unauthorized connect, unknown session connect, `session.ready`, and `stream.keepalive`.
- [ ] Run `python -m pytest backend/tests/test_session_stream_ws.py -q` and observe failure.
- [ ] Implement the in-process connection manager and websocket route.
- [ ] Re-run `python -m pytest backend/tests/test_session_stream_ws.py -q` until it passes.
- [ ] Commit with `feat: add session stream websocket route`.

### Task 3: Emit session events from business write paths

**Files:**
- Modify: `backend/app/services/messages.py`
- Modify: `backend/app/api/routes/messages.py`
- Modify: `backend/app/services/task_runs.py`
- Modify: `backend/app/runtime/processor.py`
- Modify: `backend/app/services/confirmations.py`
- Modify: `backend/app/api/routes/confirmations.py`
- Modify: `backend/app/services/alerts.py`
- Modify: `backend/app/services/approved_stock_in_commits.py`
- Modify: `backend/app/services/inventory_corrections.py`
- Create: `backend/tests/test_session_stream_integration.py`
- Modify: `backend/tests/test_message_service.py`
- Modify: `backend/tests/test_runtime_processor.py`
- Modify: `backend/tests/test_confirmations_api.py`
- Modify: `backend/tests/test_inventory_commit_service.py`
- Modify: `backend/tests/test_inventory_corrections_service.py`

- [ ] Write failing tests that prove committed business writes append the correct durable session events.
- [ ] Run the focused backend test set for those write paths and observe failure.
- [ ] Integrate append-before-commit and publish-after-commit behavior into message, task, confirmation, inventory, and alert writes.
- [ ] Re-run the focused tests until they pass.
- [ ] Commit with `feat: emit durable session stream events`.

### Task 4: Add shared mobile session bootstrap and stream provider

**Files:**
- Create: `apps/mobile/src/shared/session/useBootstrapSession.ts`
- Create: `apps/mobile/src/shared/session/SessionStreamProvider.tsx`
- Create: `apps/mobile/src/shared/session/useSessionStream.ts`
- Create: `apps/mobile/src/shared/session/sessionStreamClient.ts`
- Modify: `apps/mobile/src/app/navigation/RootNavigator.tsx`
- Create: `apps/mobile/__tests__/SessionStreamProvider.test.tsx`

- [ ] Write failing mobile tests for bootstrap, websocket lifecycle, and provider value updates.
- [ ] Run `npm.cmd test -- --runInBand SessionStreamProvider.test.tsx` in `apps/mobile` and observe failure.
- [ ] Implement the shared bootstrap and websocket provider layer.
- [ ] Re-run `npm.cmd test -- --runInBand SessionStreamProvider.test.tsx` until it passes.
- [ ] Commit with `feat: add shared mobile session stream provider`.

### Task 5: React to session events in dashboard, ledger, and chat

**Files:**
- Modify: `apps/mobile/src/features/dashboard/hooks/useDashboardSummaryQuery.ts`
- Modify: `apps/mobile/src/features/dashboard/hooks/useLowStockAlertsQuery.ts`
- Modify: `apps/mobile/src/features/dashboard/hooks/usePendingConfirmationsQuery.ts`
- Modify: `apps/mobile/src/features/dashboard/screens/DashboardScreen.tsx`
- Modify: `apps/mobile/src/features/ledger/screens/LedgerScreen.tsx`
- Modify: `apps/mobile/src/features/chat/screens/ChatScreen.tsx`
- Create: `apps/mobile/__tests__/DashboardRealtime.test.tsx`
- Modify: `apps/mobile/__tests__/LedgerScreen.test.tsx`
- Create: `apps/mobile/__tests__/ChatScreen.test.tsx`

- [ ] Write failing screen tests for dashboard refresh, ledger refresh, and chat realtime rendering.
- [ ] Run the focused mobile test set and observe failure.
- [ ] Implement event-driven `refresh()` reactions and the minimal chat stream view.
- [ ] Re-run the focused mobile tests until they pass.
- [ ] Commit with `feat: wire mobile screens to session stream events`.

### Task 6: Update docs and verify the phase

**Files:**
- Modify: `backend/app/runtime/README.md`
- Modify: `infra/docker/README.md`
- Modify: `project_docs/11-realtime-contract.md`

- [ ] Document the implemented websocket endpoint, durable event types, and current mobile behavior.
- [ ] Run `python -m pytest backend/tests -q`.
- [ ] Run `npm.cmd test -- --runInBand` in `apps/mobile`.
- [ ] Run `docker compose -f infra/docker/docker-compose.yml --env-file .env.example config`.
- [ ] Run `git status --short --branch`.
- [ ] Commit docs with `docs: document session stream foundation`.
- [ ] Commit verification with `test: verify phase 8a session stream foundation`.
