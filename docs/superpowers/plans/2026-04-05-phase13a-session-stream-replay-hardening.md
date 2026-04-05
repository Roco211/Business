# Phase 13A Session Stream Replay Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add durable replay and reconnect catch-up so the session stream no longer drops business events across reconnects or concurrent subscribers.

**Architecture:** Extend the backend with a session stream replay route and connection-local websocket cursors, then teach the mobile session stream client/provider to reconnect with the latest durable `seq` and ignore stale replay duplicates.

**Tech Stack:** FastAPI, SQLAlchemy, websocket session stream manager, React Native, TypeScript, Jest, Pytest

---

## File Structure

- Create:
  - `backend/tests/test_session_stream_api.py`
- Modify:
  - `backend/app/api/routes/session_stream.py`
  - `backend/app/contracts/session_stream.py`
  - `backend/app/realtime/connection_manager.py`
  - `backend/app/services/session_stream.py`
  - `backend/tests/test_session_stream_ws.py`
  - `backend/tests/test_session_stream_integration.py`
  - `backend/tests/test_session_stream_service.py`
  - `apps/mobile/src/shared/session/sessionStreamClient.ts`
  - `apps/mobile/src/shared/session/SessionStreamProvider.tsx`
  - `apps/mobile/__tests__/SessionStreamProvider.test.tsx`
  - `project_docs/02-api-contract.md`
  - `project_docs/11-realtime-contract-implementation-status.md`
  - `project_docs/generated/openapi-v1.json`

### Task 1: Write Red Tests For Replay Contract And Catch-Up

- [ ] Add a failing backend API test in `backend/tests/test_session_stream_api.py` that:
  - appends durable session events
  - calls `GET /api/v1/sessions/{session_id}/stream-events?after_seq=...`
  - verifies ascending replay order and safe auth behavior
- [ ] Add failing websocket tests in `backend/tests/test_session_stream_ws.py` and `backend/tests/test_session_stream_integration.py` that prove:
  - `after_seq` replays missed business events on connect
  - two websocket clients on one session each receive the same published event independently
- [ ] Add a failing mobile provider test in `apps/mobile/__tests__/SessionStreamProvider.test.tsx` that verifies reconnect uses the latest durable `seq` and ignores replay duplicates.
- [ ] Run the targeted test commands and confirm the new assertions fail first.

### Task 2: Add Backend Replay Read Surface

- [ ] Extend `backend/app/contracts/session_stream.py` with a replay response model that can return durable stream events plus count metadata if needed.
- [ ] Add a read helper or reuse `list_session_events_after()` in `backend/app/services/session_stream.py` so the route can safely clamp `limit` and return ascending durable events.
- [ ] Update `backend/app/api/routes/session_stream.py` to expose:
  - `GET /api/v1/sessions/{session_id}/stream-events`
  - query params `after_seq` and `limit`
  - mock owner auth rules aligned with the existing session stream websocket
- [ ] Re-run the new replay API test until it passes.

### Task 3: Move Websocket Catch-Up To Connection Scope

- [ ] Refactor `backend/app/realtime/connection_manager.py` so replay cursor state is tracked per websocket connection instead of one shared value per session.
- [ ] Accept optional `after_seq` in `backend/app/api/routes/session_stream.py` for websocket connects and seed each connection cursor from it.
- [ ] Keep `session.ready` and `stream.keepalive` ephemeral while ensuring durable business events update only the relevant connection cursor after send.
- [ ] Re-run the websocket tests until the reconnect and multi-client cases pass.

### Task 4: Reconnect Mobile With Durable Cursor

- [ ] Update `apps/mobile/src/shared/session/sessionStreamClient.ts` so websocket URLs include the latest `after_seq` on every reconnect attempt rather than only the initial connect.
- [ ] Update `apps/mobile/src/shared/session/SessionStreamProvider.tsx` to:
  - track the latest durable business `seq`
  - ignore duplicate or stale business events
  - preserve the current screen-facing event flow and data reset flow
- [ ] Extend `apps/mobile/__tests__/SessionStreamProvider.test.tsx` to cover reconnect cursor reuse and stale replay dedupe.
- [ ] Re-run the targeted mobile test until it passes.

### Task 5: Refresh Contracts And Verify End-To-End

- [ ] Update `project_docs/02-api-contract.md` and `project_docs/11-realtime-contract-implementation-status.md` to describe the replay route and `after_seq` reconnect contract.
- [ ] Regenerate `project_docs/generated/openapi-v1.json` with `python backend/scripts/generate_openapi_snapshot.py`.
- [ ] Run:
  - `npm.cmd test -- --runInBand`
  - `$env:PYTHONPATH='backend'; python -m pytest backend/tests -q`
  - `docker compose -f infra/docker/docker-compose.yml --env-file .env.example config`
- [ ] Commit the replay hardening slice.
