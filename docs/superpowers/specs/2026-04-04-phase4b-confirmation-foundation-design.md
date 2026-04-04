# Phase 4B Confirmation Foundation Design

## Context

Phase 4A established a durable, observable runtime loop:

- owner message intake writes one `message`
- intake creates one linked `task_run`
- a worker can claim and process the task
- supported `text` and `voice` inputs can currently finish as read-only dry-run outcomes

But the next documented boundary is still missing:

- `TaskRun.status = "awaiting-confirmation"`
- explicit `Confirmation` persistence
- owner approve/reject resolution

The project docs are consistent on three points:

1. `voice-stock-in` should pass through a confirmation state.
2. `Confirmation` is an explicit domain object, not hidden inside message text.
3. `InventoryEvent`, `AuditLog`, and WebSocket fanout should happen after the confirmation boundary is stable.

Today the repo still collapses all supported runtime work into either:

- `completed`
- `failed`

So the next clean slice is not inventory or realtime yet. It is the minimum durable confirmation chain.

## Goal

Build the minimum confirmation foundation so a stock-in task can pause for owner confirmation, and the owner can resolve that confirmation through explicit backend contracts.

After this phase:

1. `voice-stock-in` tasks can transition from `processing` to `awaiting-confirmation`.
2. The backend persists one explicit `Confirmation` per pending stock-in task.
3. The backend exposes read/write confirmation routes for:
   - pending list
   - approve
   - reject
4. Approving or rejecting a confirmation resolves both:
   - `confirmations.status`
   - the linked `task_run.status`
5. The message ledger shows visible runtime/system text for:
   - confirmation requested
   - confirmation approved
   - confirmation rejected
6. No inventory, audit, alert, session stream, or WebSocket side effects are introduced yet.

## Options Considered

### Option A: Jump straight to approval-backed inventory and audit writes

Deliver:

- confirmations
- approval endpoints
- inventory writes
- audit writes

Pros:

- closer to the end-state blueprint
- more user-visible business value

Why not now:

- adds too many new truth-writing boundaries at once
- makes it harder to isolate whether failures come from runtime, confirmation resolution, or business persistence
- weakens the reusable seam between "human approval recorded" and "approved change committed"

### Option B: Confirmation foundation first, truth writes later

Deliver:

- explicit `confirmations` persistence
- `awaiting-confirmation` task state
- pending list and approve/reject routes
- resolution messages in the session ledger

Pros:

- matches the documented state machine cleanly
- creates a durable human-approval boundary before truth writes
- keeps the next inventory phase narrowly focused on business persistence

Tradeoff:

- approved confirmations do not yet mutate inventory truth

### Option C: Realtime confirmation fanout before confirmation persistence

Deliver:

- session stream events
- WebSocket pushes for synthetic confirmation status

Why not now:

- violates the project rule that business truth lands before realtime fanout
- would create transport behavior around an object that does not yet exist durably

## Chosen Approach

Use Option B.

Phase 4B will add the minimum durable confirmation chain and stop there.

That means:

- runtime can require confirmation for stock-in work
- confirmation state is durable and queryable
- the owner can explicitly approve or reject
- task lifecycle becomes:
  - `created`
  - `processing`
  - `awaiting-confirmation`
  - `completed` or `rejected`

But this phase will not:

- create `inventory_items`
- append `inventory_events`
- append `audit_logs`
- maintain `alerts`
- write `session_stream_events`
- publish WebSocket updates

## Scope Decisions

### 1. Which tasks can require confirmation

Phase 4B should only introduce confirmation for:

- `voice-stock-in`

Phase 4B should keep:

- `voice-stock-query` as a direct read-only completion

Phase 4B should not add new executable runtime paths for:

- `image`
- `receipt-image`
- `manual-correction`

Those remain later-phase work.

### 2. Why stock-in requires confirmation in this phase

The current runtime has no real product recognition, no structured extraction, and no inventory writer. That means a stock-in transcript cannot safely become truth yet.

So for Phase 4B, stock-in should always produce one pending confirmation with a conservative phase-local reason:

- `confirmation_type = "low-confidence-recognition"`

This is the most honest current-state explanation:

- the system recognized a stock-in intent
- it does not trust itself to commit structured fields yet
- human confirmation is required before later truth-writing phases can be added

### 3. Confirmation payload shape in this phase

The durable `confirmations.fields` payload should be explicit and stable, but it should not pretend that the system already extracted high-quality structured data.

Use a phase-local shape like:

```json
{
  "summary": "Please confirm the stock-in details before commit.",
  "transcript": "restock apples today",
  "draft_fields": {
    "item_name": null,
    "quantity": null,
    "unit": null,
    "price": null
  },
  "required_fields": ["item_name", "quantity", "unit", "price"]
}
```

Approval should accept the existing API-style payload:

```json
{
  "fields": {
    "item_name": "Apple",
    "quantity": 3,
    "unit": "box",
    "price": 18.5
  }
}
```

Phase 4B should persist the owner submission into:

- `confirmations.resolution_payload`

Reject should not require a payload in this phase.

### 4. TaskRun projection rule

The docs already state that `confirmation_id` is a domain-level convenience projection, not a required physical column on `task_runs`.

So Phase 4B should:

- keep the physical schema unchanged for `task_runs`
- add `confirmations.task_run_id` as the owning relationship
- project `confirmation_id` into API responses by joining from `task_runs` to `confirmations`

Do not add a `task_runs.confirmation_id` column in this phase.

### 5. Approval semantics in this phase

Approving a confirmation in Phase 4B should mean:

- the human approval is durably recorded
- the linked task is resolved as `completed`
- a resolution summary is written back to the session message ledger

It should not mean:

- inventory truth was written
- audit truth was written

This is an intentional temporary seam. The next inventory phase will replace the internal "approval complete" behavior with "approval then commit business truth" while keeping the confirmation contracts stable.

### 6. Rejection semantics in this phase

Rejecting a confirmation should mean:

- `confirmations.status = "rejected"`
- `confirmations.resolution_payload = null`
- `task_runs.status = "rejected"`
- the session ledger receives a visible runtime/system rejection message

Phase 4B does not need correction loops or editable rejection reasons yet.

## Architecture

### 1. Confirmation model and persistence

Add a durable `Confirmation` ORM model and Alembic migration for:

- `confirmation_id`
- `task_run_id` (`UNIQUE`)
- `confirmation_type`
- `status`
- `fields`
- `resolution_payload`
- `requested_by_employee_id`
- `approved_by_actor_id`
- `created_at`
- `resolved_at`

Constraints:

- one `Confirmation` per `task_run_id`
- `status` must be one of:
  - `pending`
  - `approved`
  - `rejected`

### 2. Confirmation service boundary

Add a focused confirmation service under `backend/app/services` that owns:

- creating a pending confirmation for a task run
- listing confirmations by status
- resolving a pending confirmation as approved
- resolving a pending confirmation as rejected
- projecting linked task state where needed

Rules:

- creation must be idempotent per `task_run_id`
- resolution must only succeed from `pending`
- double-approval, double-rejection, or cross-resolution must return a conflict-style domain error

### 3. Task lifecycle service extensions

Extend `backend/app/services/task_runs.py` so the task lifecycle can express the runtime contract already documented in `project_docs`:

- `processing -> awaiting-confirmation`
- `awaiting-confirmation -> completed`
- `awaiting-confirmation -> rejected`

Rules:

- only a `processing` task may enter `awaiting-confirmation`
- only an `awaiting-confirmation` task may be approved or rejected
- resolution must update `updated_at`
- approval should set `completed_at`
- rejection should set `completed_at`

### 4. Minimal policy layer

Phase 4B should add the smallest useful policy seam between runtime routing and task completion.

Add a small policy module under `backend/app/runtime`, for example:

- `policy.py`

It only needs two outcomes in this phase:

- `allow`
- `require-confirmation`

Rules:

- `voice-stock-query` -> `allow`
- `voice-stock-in` -> `require-confirmation`

This keeps the repo moving toward the documented `PolicyGuard` shape without overbuilding a generic engine.

### 5. Runtime processor behavior

The runtime processor should evolve from:

- route
- complete or fail

into:

- route
- evaluate policy
- either:
  - complete read-only query work
  - create confirmation and pause the task
  - fail on blocked/unsupported work

When policy returns `require-confirmation`, the processor should:

1. create or load the linked pending confirmation
2. transition the task to `awaiting-confirmation`
3. write one visible runtime/system text message into the session ledger
4. commit the transaction

The worker return payload should remain small and serializable, but now it may return:

- `status = "awaiting-confirmation"`

### 6. Runtime/system message writeback

Continue using the same message ledger for visible system output.

Phase 4B should write system messages for:

- pending confirmation created
- confirmation approved
- confirmation rejected

Message type should remain:

- `text`

for this phase.

Do not introduce `confirmation-card` storage yet because the current repo does not yet have a durable typed message payload contract.

### 7. Confirmation API

Add a new route set under `backend/app/api/routes/confirmations.py`:

- `GET /api/v1/confirmations?status=pending&limit=20`
- `POST /api/v1/confirmations/{confirmation_id}/approve`
- `POST /api/v1/confirmations/{confirmation_id}/reject`

Route behavior:

- use the same mock owner bearer token as existing protected routes
- `GET` returns newest-first confirmations
- `approve` requires a `fields` object
- `reject` requires no body in this phase

Suggested response shape for list items:

- `confirmation_id`
- `task_run_id`
- `session_id`
- `confirmation_type`
- `status`
- `fields`
- `resolution_payload`
- `requested_by_employee_id`
- `approved_by_actor_id`
- `created_at`
- `resolved_at`

### 8. TaskRun polling contract enrichment

Extend the existing `GET /api/v1/task-runs/{task_run_id}` response to include:

- `confirmation_id`

when a linked confirmation exists.

This keeps the current polling seam useful until realtime fanout lands.

## API and Contract Impact

### 1. Existing message intake route

`POST /api/v1/sessions/{session_id}/messages`

External behavior remains stable:

- `201` on fresh create
- `200` on replay

Internal behavior changes only for stock-in tasks:

- runtime may now resolve the task to `awaiting-confirmation` instead of `completed`

### 2. Existing task-run route

`GET /api/v1/task-runs/{task_run_id}`

Add support for:

- `status = "awaiting-confirmation"`
- `status = "rejected"`
- `confirmation_id`

### 3. New confirmation routes

Phase 4B adds:

- `GET /api/v1/confirmations?status=pending&limit=20`
- `POST /api/v1/confirmations/{confirmation_id}/approve`
- `POST /api/v1/confirmations/{confirmation_id}/reject`

Error cases should include stable domain-style codes for:

- `confirmation_not_found`
- `confirmation_not_pending`
- `validation_error`
- `unauthorized`

## Error Handling

Phase 4B should continue using the Phase 4A runtime error codes for routing and unsupported input.

It should add confirmation-domain errors for resolution problems:

- `confirmation_not_found`
- `confirmation_not_pending`

Rules:

- missing confirmation id -> `404`
- already-resolved confirmation -> `409`
- malformed approval payload -> `422`

## Testing Strategy

Phase 4B should be test-first and include:

1. Confirmation service tests for:
   - create pending confirmation
   - idempotent create by `task_run_id`
   - approve pending confirmation
   - reject pending confirmation
   - conflict on resolving an already-resolved confirmation
2. Task lifecycle tests for:
   - `processing -> awaiting-confirmation`
   - `awaiting-confirmation -> completed`
   - `awaiting-confirmation -> rejected`
3. Runtime processor tests for:
   - stock-in task creates pending confirmation and pauses
   - stock-query task still completes directly
   - pending confirmation creation writes a system message
4. API tests for:
   - `GET /confirmations?status=pending`
   - `POST /confirmations/{id}/approve`
   - `POST /confirmations/{id}/reject`
   - task-run polling includes `confirmation_id`
5. Worker wrapper tests for:
   - serializable return payload when runtime yields `awaiting-confirmation`

## Acceptance Criteria

Phase 4B is complete when all of the following are true:

1. A fresh `voice-stock-in` message can produce a worker-run `task_run` that ends in `awaiting-confirmation`.
2. The same task has exactly one durable linked `Confirmation`.
3. A fresh `voice-stock-query` message still completes as a read-only runtime result.
4. Pending confirmations can be listed through `GET /api/v1/confirmations?status=pending`.
5. Approving a pending confirmation marks:
   - `confirmations.status = "approved"`
   - `task_runs.status = "completed"`
6. Rejecting a pending confirmation marks:
   - `confirmations.status = "rejected"`
   - `task_runs.status = "rejected"`
7. Approval and rejection each write a visible runtime/system text message into the same session ledger.
8. `GET /api/v1/task-runs/{task_run_id}` exposes the `confirmation_id` projection when present.
9. No inventory, audit, alert, session stream, or WebSocket dependencies are introduced.

## Out of Scope

This phase explicitly does not implement:

- `inventory_items`
- `inventory_events`
- `audit_logs`
- `alerts`
- `session_stream_events`
- WebSocket fanout
- `confirmation-card` typed message payloads
- OCR extraction
- image recognition
- real ASR
- rejection reasons or correction loops
- multi-confirmation tasks

## Follow-On Work

Once Phase 4B lands, the next clean slices are:

1. convert approval resolution into transactional inventory and audit writes
2. add inventory read models and low-stock alert maintenance
3. add durable session stream events and WebSocket fanout after truth writes

That preserves the intended layering:

- runtime routing
- confirmation boundary
- business-truth persistence
- realtime delivery
