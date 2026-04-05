# Infra Docker

This directory defines the local infrastructure for the current MVP foundation:

- MySQL
- Redis
- MinIO
- API service
- Worker service

Phase 2 adds SQLAlchemy and Alembic-backed persistence. The backend now expects a migration-managed schema for DB-backed routes such as mock login bootstrap and session bootstrap. By default the application derives its database URL from `MYSQL_*` variables, and `DATABASE_URL` is only needed when you want to override that behavior explicitly.

Phase 3A extends that persistence layer with the message and task ledger foundation. The local stack still brings up MySQL, Redis, MinIO, API, and worker services, but this phase only exercises the DB-backed intake path and does not yet introduce runtime consumers, confirmations, or WebSocket session events.

The compose stack now includes a `migrator` service so the API and worker start behind an explicit schema upgrade step.

Phase 4A adds a dry-run runtime worker on top of that ledger. Fresh message intake now produces pollable task runs, the worker can consume them asynchronously, and runtime outcomes are written back into the session as read-only system messages. This phase still avoids confirmation flows, inventory mutation, audit trails, and WebSocket push.

Phase 4B adds durable confirmation persistence and owner-facing confirmation routes on top of the runtime worker. Stock-in tasks can now pause in `awaiting-confirmation`, pending confirmations can be listed and resolved through the API, and task-run polling can project the linked `confirmation_id`.

Phase 5A extends that approval path into real inventory truth. Approving a pending stock-in confirmation now writes `inventory_items`, `inventory_events`, and `audit_logs` in the backend database and only then completes the linked task.

Phase 6A adds the first read-side surface on top of that truth. The backend now exposes inventory item list/detail reads plus inventory-scoped audit log reads, and the Expo `LedgerScreen` consumes them through a lightweight fetch client.

Phase 6B extends that read-side with a durable `alerts` table, a dashboard summary route, and a low-stock alert route. The Expo `DashboardScreen` now reads:

- `GET /api/v1/dashboard/summary`
- `GET /api/v1/alerts?type=low-stock`
- `GET /api/v1/confirmations?status=pending`

Current alert truth is only refreshed by the approved stock-in commit path. Stock-out, correction, and realtime push remain future work.

Phase 7A adds the first ledger correction write path:

- `POST /api/v1/inventory-events/corrections`

The backend now refreshes low-stock alert truth after both:

- approved stock-in commits
- manual correction writes

Stock-out and realtime push still remain future work.

For local mobile development:

- set `EXPO_PUBLIC_API_BASE_URL` if you want to point Expo at a non-default backend
- otherwise the client defaults to `http://10.0.2.2:8001` on Android emulators
- and defaults to `http://127.0.0.1:8001` on non-Android Expo targets
- all current mobile reads still use `Authorization: Bearer mock_owner_token`

Phase 8A now adds:

- durable `session_stream_events`
- a websocket session endpoint at `WS /api/v1/ws/sessions/{session_id}?token=mock_owner_token`
- a mobile shared session bootstrap + websocket provider

Current realtime behavior is intentionally lightweight:

- the API process tails committed `session_stream_events` for connected websocket clients
- the mobile app re-fetches affected REST reads on incoming events instead of maintaining a local cache graph
- the current websocket surface is still mock-auth only and scoped to one session at a time

Replay endpoints, OCR-specific stream events, and stock-out realtime flows remain future work.
