# Phase 2 Persistence Foundation Design

## Context

Phase 1 moved this repository from documentation-only assets into a runnable MVP skeleton:

- `backend/` now exposes `health`, `mock-login`, and `sessions/bootstrap`
- `apps/mobile/` provides an Expo shell with the three primary screens
- `infra/docker/` defines MySQL, Redis, MinIO, API, and worker services

That skeleton is intentionally still mock-first. The current backend returns default shop and session context from configuration rather than persistent truth. This is the biggest remaining blocker to turning the project docs into coding-ready implementation ground, because the next planned subsystems all depend on stable persisted IDs, relationships, and migration-managed schema:

- `messages`
- `task_runs`
- `confirmations`
- `session_stream_events`
- inventory and audit writes

The project docs already identify `SQLAlchemy + Alembic` as part of the current backend construction scope, and they define the first-pass MySQL schema in detail. Phase 2 therefore should not jump to runtime orchestration or WebSocket delivery yet. It should first create the persistence layer that those subsystems will stand on.

## Goal

Build the minimum persistence foundation that turns the current backend from config-only mock context into database-backed application context.

After this phase:

1. The backend has a real SQLAlchemy database layer and Alembic migration setup.
2. The schema includes the first persistence slice required for application bootstrap.
3. The API can create or load the default shop and default workgroup session from the database.
4. The existing mock auth and session bootstrap flow continues to work, but now resolves against persisted records instead of hardcoded-only values.
5. The repository has a repeatable initialization path for local development and tests.

## Options Considered

### Option A: Persistence foundation first

Deliver:

- SQLAlchemy engine/session wiring
- Alembic initialization
- first DB models and migration
- seed/bootstrap service
- DB-backed `mock-login` and `sessions/bootstrap`

Pros:

- unlocks every subsequent backend subsystem
- converts the docs' MySQL schema into executable project truth
- keeps Phase 2 tightly scoped and testable

Tradeoff:

- user-visible behavior changes only slightly in this phase

### Option B: Runtime loop first

Deliver:

- router
- policy guard
- tool runner
- task state machine

Why not now:

- runtime contracts depend on persisted `task_runs`, `confirmations`, and session context
- building orchestration before storage would force a second rewrite

### Option C: WebSocket/session stream first

Deliver:

- WebSocket endpoint
- event publication
- client subscription contract

Why not now:

- event sequencing in `session_stream_events` depends on durable session records
- reconnect and compensation logic need a persisted source of truth

## Chosen Approach

Use Option A.

Phase 2 will implement the persistence slice that supports only the existing bootstrap path:

- `shops`
- `sessions`

It will also establish the shared database infrastructure needed for later phases:

- SQLAlchemy declarative base
- engine/session management
- Alembic env and first migration
- seed/bootstrap service for default records

This phase intentionally does **not** add:

- `messages`
- `task_runs`
- `confirmations`
- WebSocket server
- runtime orchestration
- real provider integrations

Those will be much cheaper to build once a stable persisted shop/session foundation exists.

## Architecture

### 1. Database boundary

Add a dedicated DB package under `backend/app/db` responsible for:

- engine creation
- session factory
- declarative base
- database settings access

This package is infrastructure only. Route handlers should not compose SQL directly.

### 2. Persistence models

Add a dedicated models package under `backend/app/models` for the initial ORM entities:

- `Shop`
- `Session`

These models map directly to the schema already defined in `project_docs/12-db-schema.md`, but only for the fields needed now.

The initial field set should be enough to support:

- default shop identity
- locale/timezone defaults
- workgroup session bootstrap
- future event sequencing

So `sessions.last_event_seq` should exist now even though WebSocket is not implemented yet.

### 3. Repository/service split

Do not put seeding logic inside route handlers.

Create a small service layer under `backend/app/services` that owns:

- ensuring the default shop exists
- ensuring the default workgroup session exists
- returning the persisted bootstrap context

This service becomes the single source of truth for how the mock-first app materializes its initial records.

### 4. API behavior

The external API stays intentionally stable:

- `POST /api/v1/auth/mock-login`
- `POST /api/v1/sessions/bootstrap`

But internally:

- `mock-login` ensures the shop context exists in the database
- `sessions/bootstrap` loads or creates the default workgroup session for that shop

This preserves Phase 1 clients while upgrading the backend from config mocks to persistence-backed mocks.

## Data Model Scope

### `shops`

Include at least:

- `shop_id`
- `name`
- `owner_name`
- `industry`
- `locale`
- `timezone`
- `require_price_confirmation`
- `require_new_item_confirmation`
- `low_confidence_threshold`
- `default_low_stock_threshold`
- `created_at`
- `updated_at`

### `sessions`

Include at least:

- `session_id`
- `shop_id`
- `session_type`
- `title`
- `participants`
- `last_event_seq`
- `last_message_at`
- `created_at`
- `updated_at`

### Why only these two tables now

They are the minimum persistence units needed to support:

- authenticated default shop context
- stable bootstrap session
- future `session_stream_events`
- later `messages` and `task_runs`

Adding more tables now would expand Phase 2 from a foundation step into a partial product build.

## Migration Strategy

Add Alembic to the repo and create the first migration for:

- `shops`
- `sessions`

The migration must be explicit and checked in. This phase does not rely on runtime auto-create.

For local and test workflows:

- tests may use SQLite for fast isolated verification
- production-targeted schema remains aligned to MySQL-oriented naming and field intent

If a MySQL-specific type choice would make SQLite tests fragile, prefer the simplest SQLAlchemy type that preserves the contract semantics.

## Seeding Strategy

Create a small bootstrap initializer service that can safely run multiple times.

Rules:

1. Ensure a default shop exists using `DEFAULT_SHOP_ID`.
2. Ensure a default workgroup session exists for that shop using `DEFAULT_SESSION_ID`.
3. Repeated execution must be idempotent.
4. Returned data must be suitable for both the auth route and the bootstrap route.

The seed path can run lazily from the existing mock routes in this phase. A separate CLI seed command is optional and not required yet.

## Error Handling

This phase keeps the existing unified response style and adds only the minimum new failure boundary:

- database misconfiguration should fail fast at startup or dependency resolution time
- bootstrap service errors should surface as internal server errors with the existing API error envelope

This phase does not yet add:

- retry orchestration
- transaction outbox patterns
- advanced DB conflict translation

## Testing Strategy

Phase 2 should be test-first and include:

1. DB configuration tests proving the app can create a database session from test settings.
2. Service tests for idempotent default shop/session initialization.
3. Route tests proving:
   - `mock-login` returns persisted shop context
   - `sessions/bootstrap` returns the persisted default workgroup session
4. Alembic-level verification that the first migration upgrades successfully in test.

The existing Phase 1 backend tests should remain green after the persistence refactor.

## Acceptance Criteria

Phase 2 is complete when all of the following are true:

1. `backend/app/db` exists and is used by the backend.
2. `backend/app/models` contains ORM models for `shops` and `sessions`.
3. Alembic is configured in-repo and includes an initial migration for those tables.
4. `mock-login` and `sessions/bootstrap` are DB-backed through a service, not pure hardcoded route assembly.
5. Re-running the bootstrap path does not create duplicate default records.
6. Backend tests pass against the new persistence layer.
7. Docker config still parses after the DB-related additions.

## Out of Scope

This phase explicitly does not implement:

- `messages`
- `task_runs`
- `confirmations`
- `inventory_items`
- `inventory_events`
- `audit_logs`
- `session_stream_events`
- WebSocket endpoint
- MinIO upload flows
- runtime orchestration
- provider interfaces beyond the existing skeleton

## Follow-On Work

Once this phase lands, the next highest-value backend slice becomes:

1. `messages` + `task_runs` persistence
2. `confirmations`
3. session stream events and WebSocket delivery

That order matches the existing project docs and avoids building orchestration on top of unstable storage.
