# Phase 3 Message and Task Intake Design

## Context

Phase 1 created the runnable MVP skeleton. Phase 2 then gave that skeleton durable application context by persisting:

- `shops`
- `sessions`

The next missing slice is the intake ledger between the owner-facing chat surface and the later runtime loop. The project docs already define that ledger in three pieces:

- `media_uploads`
- `messages`
- `task_runs`

They also make the intended build order explicit:

1. bootstrap the default workgroup session
2. stand up messages and task ledger
3. add runtime orchestration
4. add confirmation, inventory, audit, and WebSocket loops

That order matters. If the backend jumps directly to runtime, we would have to invent temporary storage or rewrite orchestration once durable message and task records arrive. Phase 3 should therefore build the persisted intake boundary first.

## Goal

Build the minimum durable message and task intake foundation that lets the backend record owner-facing session traffic and create task ledger entries where the task type is already deterministic.

After this phase:

1. The schema includes `media_uploads`, `messages`, and `task_runs`.
2. The backend exposes `GET /api/v1/sessions/{session_id}/messages`.
3. The backend exposes `POST /api/v1/sessions/{session_id}/messages`.
4. Owner-authored write requests support `client_request_id` idempotency.
5. The backend can validate that referenced media exists and is already `uploaded`.
6. The backend can create a linked `task_run` for deterministic intake paths without introducing the full runtime loop.

## Options Considered

### Option A: Full intake foundation before runtime

Deliver:

- persistence for `media_uploads`, `messages`, and `task_runs`
- message list and message create APIs
- idempotent owner writes
- deterministic task-run creation for safe message types

Pros:

- matches the documented construction order
- turns the API and schema docs into executable truth
- gives later runtime work a durable source of truth instead of an in-memory queue

Tradeoff:

- does not yet deliver semantic routing for all message types

### Option B: Runtime first, persistence second

Deliver:

- router
- policy guard
- worker loop

Why not now:

- runtime needs a durable `source_message_id`
- later WebSocket and confirmation flows depend on durable task records
- temporary orchestration storage would be throwaway work

### Option C: Message log only, no task ledger

Deliver:

- store messages
- skip task creation until runtime exists

Why not now:

- breaks the docs' message-to-task linkage
- leaves no durable unit for later confirmation and audit chains
- makes Phase 4 larger and more coupled than it needs to be

## Chosen Approach

Use Option A, but keep task creation intentionally narrow.

Phase 3 will add the full persistence and API foundation for:

- attachment metadata validation through `media_uploads`
- message history through `messages`
- task intake ledger through `task_runs`

It will only create `task_runs` for message types whose task type is already deterministic without semantic routing:

- `receipt-image` -> `receipt-ocr`

It will also allow plain `text` messages to be persisted as chat history, but those messages will not create a task run in this phase.

It will explicitly reject runtime-dependent task-creating message types for now:

- `voice`
- `image`

Those two inputs require the later runtime router to distinguish:

- stock-in vs stock-query
- product recognition vs inventory query

That distinction cannot be made honestly in Phase 3 because the current API contract for media messages does not yet carry a stable intent hint.

## Architecture

### 1. Persistence boundary

Extend the current SQLAlchemy layer with three new ORM models:

- `MediaUpload`
- `Message`
- `TaskRun`

These models live under `backend/app/models` and remain infrastructure-facing only. Route handlers should call services, not compose ORM writes directly.

### 2. Service boundary

Add a focused service module under `backend/app/services` that owns:

- validating the target session exists
- validating media readiness
- applying idempotency rules for owner-authored requests
- creating the `message`
- conditionally creating the linked `task_run`
- listing message history with cursor pagination

This service becomes the single source of truth for message intake behavior.

### 3. API boundary

Add contracts and routes for:

- listing session messages
- creating session messages

Authentication stays aligned with the existing mock-first backend:

- `Authorization: Bearer mock_owner_token`

The route must verify that the requested `session_id` belongs to the default shop context. In the current single-shop phase, this is mostly a future-proofing boundary, but it should still be explicit now instead of implied.

## Data Model Scope

### `media_uploads`

Phase 3 adds the table now even though upload endpoints are still out of scope. The reason is simple: message creation for media-bearing inputs needs a durable way to verify that referenced media exists and is already ready.

Required fields:

- `media_id`
- `shop_id`
- `uploader_actor_type`
- `uploader_actor_id`
- `media_type`
- `file_name`
- `content_type`
- `size_bytes`
- `storage_bucket`
- `storage_key`
- `public_url`
- `status`
- `checksum_sha256`
- `created_at`
- `uploaded_at`

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

- add `UNIQUE(session_id, actor_type, actor_id, client_request_id)`
- allow `client_request_id` to be nullable at the DB layer
- for the current owner-facing create route, require `client_request_id` in request validation

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

Phase 3 creates new task runs with:

- `task_type = "receipt-ocr"`
- `status = "created"`

This is intentionally one step earlier than runtime processing. A later phase will move a created task run into `processing`.

## Intake Rules

### Supported create behaviors in Phase 3

#### `message_type = "text"`

Rules:

- `text` must be non-empty after trim
- `media_ids` must be empty
- the message is persisted
- no `task_run` is created

Response shape:

- `message_id`
- `task_run_id = null`
- `status = "accepted"`

#### `message_type = "receipt-image"`

Rules:

- at least one `media_id` must be provided
- each referenced media record must exist, belong to the same shop, and have `status = "uploaded"`
- the message is persisted
- a linked `task_run` is created with `task_type = "receipt-ocr"` and `status = "created"`
- the message record stores the created `task_run_id` as a soft reference

Response shape:

- `message_id`
- `task_run_id`
- `status = "created"`

### Rejected create behaviors in Phase 3

For:

- `voice`
- `image`

Return:

- `422 unsupported_message_type_for_phase`

Reason:

- these paths need semantic routing that belongs to the runtime phase, not the persistence phase

## Idempotency Rules

Owner-authored message creation must use:

- `(session_id, actor_type, actor_id, client_request_id)`

Behavior:

1. First submission creates the message and any linked task run.
2. Replayed submission with the same normalized payload returns the originally created records.
3. Replayed submission with the same idempotency key but a different normalized payload returns:
   - `409 idempotency_conflict`

Normalized payload comparison in this phase should include:

- `message_type`
- trimmed `text`
- ordered `media_ids`

For idempotent replays:

- fresh creation returns `201`
- replay returns `200`

## Listing Rules

`GET /api/v1/sessions/{session_id}/messages`

Phase 3 should implement cursor pagination now so later mobile integration does not need a route contract rewrite.

Rules:

- default page size: `20`
- max page size: `50`
- order: newest first
- cursor encodes the last seen `(created_at, message_id)` pair
- response includes:
  - `data`
  - `meta.next_cursor`

Each list item should expose:

- `message_id`
- `session_id`
- `actor_type`
- `actor_id`
- `message_type`
- `text`
- `media_ids`
- `task_run_id`
- `created_at`

This phase does not yet denormalize task details into the list response.

## Migration Strategy

Add the next Alembic migration after the Phase 2 bootstrap migration.

This migration should create:

- `media_uploads`
- `messages`
- `task_runs`

It should also add the documented indexes for this slice:

- `messages(session_id, created_at desc)`
- `UNIQUE messages(session_id, actor_type, actor_id, client_request_id)`
- `task_runs(session_id, updated_at desc)`
- `task_runs(source_message_id)`

The `messages.task_run_id` column remains a soft reference with no foreign key in this phase, matching the project docs.

## Error Handling

Phase 3 adds these backend error boundaries:

- `404 session_not_found`
- `409 media_not_ready`
- `409 idempotency_conflict`
- `422 unsupported_message_type_for_phase`
- `422 validation_error`

This phase still does not add:

- confirmation creation
- runtime retry logic
- dead-letter handling
- WebSocket publication

## Testing Strategy

Phase 3 should be test-first and include:

1. Alembic verification proving the new migration creates `media_uploads`, `messages`, and `task_runs`.
2. Service tests for:
   - text message creation
   - receipt-image message creation with linked task run
   - idempotent replay returning the original records
   - idempotency conflict detection
   - media readiness validation
   - unsupported message type rejection
3. Route tests for:
   - authenticated list messages
   - authenticated create text message
   - authenticated create receipt-image message
   - unauthorized access rejection
4. Cursor pagination tests for newest-first ordering and next cursor behavior.

## Acceptance Criteria

Phase 3 is complete when all of the following are true:

1. The schema includes `media_uploads`, `messages`, and `task_runs`.
2. The backend can list persisted session messages through `GET /api/v1/sessions/{session_id}/messages`.
3. The backend can create persisted `text` messages with idempotent owner writes.
4. The backend can create persisted `receipt-image` messages and a linked `receipt-ocr` task run.
5. Replayed owner requests return the originally created records instead of duplicating rows.
6. Payload drift on a reused idempotency key returns `409 idempotency_conflict`.
7. Media-bearing message creation fails when referenced media is missing or not `uploaded`.
8. Backend tests and Docker compose config remain green after the slice lands.

## Out of Scope

This phase explicitly does not implement:

- upload request and upload completion endpoints
- `voice` task intake
- generic `image` task intake
- confirmation generation
- inventory writes
- audit writes
- WebSocket session stream publication
- runtime router, policy guard, tool runner, or worker execution

## Follow-On Work

Once this phase lands, the next clean backend slice becomes one of two directions:

1. add the media upload API on top of the now-durable `media_uploads` table
2. add the runtime loop that can safely expand support for `voice` and `image`

Because Phase 3 leaves `voice` and `image` intentionally blocked, the follow-on runtime phase can extend the create route without revisiting the persistence model or idempotency contract.
