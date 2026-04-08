# Phase 3A Message and Task Ledger Foundation Design

## Context

Phase 1 created the runnable MVP skeleton. Phase 2 then persisted the minimum bootstrap context:

- `shops`
- `sessions`

The next documented gap is the durable ledger between the owner-facing message stream and the later runtime loop:

- `messages`
- `task_runs`

The project docs consistently assume that later runtime behavior will revolve around:

- `source_message_id`
- `task_run_id`

So the backend should not jump to Router, PolicyGuard, ToolRunner, or confirmation logic yet. It should first build the stable message and task ledger those later subsystems will consume.

One design gap also becomes clear at this stage: the current docs make `task_runs.task_type` required, but the actual task type for `text`, `voice`, and generic `image` inputs cannot be determined honestly before the runtime router exists. Phase 3A should therefore solve that mismatch explicitly instead of smuggling runtime logic into the message route.

## Goal

Build the minimum durable message and task ledger foundation for the default workgroup session, without introducing runtime orchestration.

After this phase:

1. The schema includes `messages` and `task_runs`.
2. The backend exposes `GET /api/v1/sessions/{session_id}/messages`.
3. The backend exposes `POST /api/v1/sessions/{session_id}/messages`.
4. A successful message write creates one `message` and one initial `task_run` in the same transaction.
5. Owner-authored writes support `client_request_id` idempotency.
6. `sessions.last_message_at` is updated whenever a new message is created.

## Options Considered

### Option A: Message and task ledger foundation first

Deliver:

- persistence for `messages` and `task_runs`
- message list and message create APIs
- idempotent owner writes
- initial task ledger creation with no runtime consumption yet

Pros:

- matches the documented build order
- gives later runtime work a durable truth layer
- keeps the phase small enough to implement and test in isolation

Tradeoff:

- the initial task run is only a staging record, not a semantically routed task

### Option B: Add runtime routing now

Deliver:

- message persistence
- task typing
- worker-side state advancement

Why not now:

- this would pull Router, PolicyGuard, and worker orchestration into the same phase
- it would blur the boundary between persistence and execution
- it would make review much harder because failures would mix schema, API, and runtime causes

### Option C: Persist messages only, defer task creation

Deliver:

- `messages`
- list and create endpoints

Why not now:

- later runtime expects a durable `task_run_id`
- it would force the next phase to retroactively backfill missing task records
- it would postpone the idempotency contract where it matters most

## Chosen Approach

Use Option A.

Phase 3A will introduce the durable message and task ledger, but it will stop at initial intake bookkeeping.

That means:

- every successful owner message write creates a `message`
- the same transaction also creates an initial `task_run`
- the initial task run stays at `status = "created"`
- Phase 3A does not classify, execute, confirm, or complete the task

To reconcile the current doc gap around non-null `task_type`, Phase 3A adds a temporary intake-only task type:

- `pending-classification`

This value means:

- the message has been durably accepted
- a follow-on runtime phase still needs to classify it into `voice-stock-in`, `voice-stock-query`, `photo-stock-in`, `photo-stock-query`, `receipt-ocr`, or `manual-correction`

This keeps the schema explicit and avoids introducing nullable `task_type` or premature routing logic.

## Architecture

### 1. Persistence boundary

Extend the SQLAlchemy model layer with:

- `Message`
- `TaskRun`

These models live under `backend/app/models` and match the documented schema, except for the deliberate addition of `pending-classification` as an intake-only `task_type` value.

### 2. Service boundary

Add focused services under `backend/app/services`:

- `MessageWriteService`
- `MessageQueryService`
- `TaskRunService`

Responsibilities:

- validate the target session exists
- enforce idempotency
- create the message row
- create the initial task run row
- update `sessions.last_message_at`
- paginate message history

Route handlers should delegate all message/task write behavior to these services.

### 3. API boundary

Add routes for:

- `GET /api/v1/sessions/{session_id}/messages`
- `POST /api/v1/sessions/{session_id}/messages`

Authentication remains the current mock-first contract:

- `Authorization: Bearer mock_owner_token`

The routes should explicitly verify that:

- the session exists
- the session belongs to the current default shop context

## Data Model Scope

### `messages`

Required fields:

- `message_id`
- `session_id`
- `actor_type`
- `actor_id`
- `message_type`
- `text`
- `media_ids`
- `client_request_id`
- `task_run_id`
- `created_at`

Important constraints:

- `UNIQUE(session_id, actor_type, actor_id, client_request_id)`
- `messages.task_run_id` remains a soft reference with no foreign key
- add index `messages(session_id, created_at desc)`

### `task_runs`

Required fields:

- `task_run_id`
- `session_id`
- `source_message_id`
- `task_type`
- `status`
- `assigned_employee_id`
- `result_summary`
- `error_code`
- `error_message`
- `created_at`
- `updated_at`
- `completed_at`

Important constraints:

- add index `task_runs(session_id, updated_at desc)`
- add index `task_runs(source_message_id)`

Phase 3A creates all new task runs with:

- `task_type = "pending-classification"`
- `status = "created"`

## Intake Rules

### Supported message types

Phase 3A should accept the existing contract-level owner message types:

- `text`
- `voice`
- `image`
- `receipt-image`

The phase does not need to understand what the message means. It only needs to durably record the intake and create the initial task ledger entry.

### Validation rules

Rules:

- `client_request_id` is required for the current owner-facing create route
- at least one of `text` or `media_ids` must be meaningfully present
- `media_ids` are treated as opaque IDs in this phase
- `message_type` must be one of the supported contract values

Phase 3A intentionally does not validate:

- media upload readiness
- ASR/OCR/provider availability
- semantic intent

Those checks belong to later upload and runtime phases.

### Write behavior

For every successful create:

1. Validate session ownership.
2. Create one `message`.
3. Create one linked `task_run` with `pending-classification`.
4. Write the new `task_run_id` back onto the message row.
5. Update `sessions.last_message_at` to the message timestamp.
6. Commit the whole unit atomically.

Response shape:

- `message_id`
- `task_run_id`
- `status = "created"`

## Idempotency Rules

Owner-authored message creation uses:

- `(session_id, actor_type, actor_id, client_request_id)`

Behavior:

1. First submission creates one `message` and one `task_run`.
2. Replayed submission with the same normalized payload returns the original ids.
3. Replayed submission with the same idempotency key but a different normalized payload returns:
   - `409 idempotency_conflict`

Normalized payload comparison should include:

- `message_type`
- trimmed `text`
- ordered `media_ids`

For idempotent replays:

- fresh create returns `201`
- replay returns `200`

## Listing Rules

`GET /api/v1/sessions/{session_id}/messages`

Phase 3A should implement cursor pagination now so mobile integration does not need a contract rewrite later.

Rules:

- default page size: `20`
- max page size: `50`
- order: newest first
- cursor encodes the last seen `(created_at, message_id)` pair
- response includes:
  - `data`
  - `meta.next_cursor`

Each message item should expose:

- `message_id`
- `session_id`
- `actor_type`
- `actor_id`
- `message_type`
- `text`
- `media_ids`
- `task_run_id`
- `created_at`

Phase 3A does not yet embed task run details in the list response.

## Migration Strategy

Add the next Alembic migration after the current shops/sessions migration.

This migration creates:

- `messages`
- `task_runs`

It also adds the documented indexes and unique constraint for this slice:

- `messages(session_id, created_at desc)`
- `UNIQUE messages(session_id, actor_type, actor_id, client_request_id)`
- `task_runs(session_id, updated_at desc)`
- `task_runs(source_message_id)`

The migration should also update the application's executable schema truth to include `pending-classification` as the initial `task_type` used before runtime classification exists.

## Error Handling

Phase 3A adds these backend error boundaries:

- `404 session_not_found`
- `409 idempotency_conflict`
- `422 validation_error`
- `401 unauthorized`

This phase explicitly does not add:

- media readiness errors
- confirmation-required errors
- runtime/provider execution failures

## Testing Strategy

Phase 3A should be test-first and include:

1. Alembic verification proving the new migration creates `messages` and `task_runs` with the expected indexes and unique constraint.
2. Service tests for:
   - successful message write
   - idempotent replay returning the original ids
   - idempotency conflict detection
   - invalid session rejection
   - `sessions.last_message_at` update
3. Route tests for:
   - authenticated message creation
   - authenticated message listing
   - unauthorized access rejection
   - newest-first pagination

## Acceptance Criteria

Phase 3A is complete when all of the following are true:

1. Alembic upgrades create `messages` and `task_runs` with the documented indexes and unique constraint.
2. `POST /api/v1/sessions/{session_id}/messages` creates one `message` and one initial `task_run` in a single transaction.
3. The initial `task_run` uses `task_type = "pending-classification"` and `status = "created"`.
4. Replayed owner writes return the original ids instead of duplicating rows.
5. Payload drift on a reused idempotency key returns `409 idempotency_conflict`.
6. `GET /api/v1/sessions/{session_id}/messages` pages newest first and returns `task_run_id`.
7. `sessions.last_message_at` is updated when a new message is written.
8. No inventory, confirmation, audit, or WebSocket tables are written by this phase.
9. Backend tests and Docker compose config remain green after the slice lands.

## Out of Scope

This phase explicitly does not implement:

- `media_uploads` endpoints or MinIO linkage
- Router, PolicyGuard, ToolRunner, Summarizer, or Reviewer
- confirmation creation
- inventory writes
- audit writes
- alerts
- session stream events or WebSocket push
- task status progression beyond the initial `created` row
- result-card or confirmation-card message generation

## Follow-On Work

Once Phase 3A lands, the clean next step is the minimum runtime slice:

1. read the pending message/task ledger
2. classify `pending-classification`
3. advance task status into runtime processing
4. only then introduce confirmation, inventory, and audit side effects

That sequencing keeps the message API small, the schema stable, and the runtime phase focused on execution instead of data-model catch-up.
