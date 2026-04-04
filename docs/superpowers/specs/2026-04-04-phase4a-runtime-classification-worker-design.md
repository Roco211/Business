# Phase 4A Runtime Classification Worker Design

## Context

Phase 3A established a durable intake ledger:

- `messages`
- `task_runs`

Every successful owner message write now creates:

- one `message`
- one linked `task_run`

But those new task runs currently stop at:

- `task_type = "pending-classification"`
- `status = "created"`

That was the right stopping point for the ledger phase, but it leaves the runtime boundary unimplemented. The next missing slice is not the full P0 closed loop yet. It is the minimum worker-backed runtime layer that can:

1. consume the ledger
2. classify a pending task run
3. advance its state
4. fail unsupported inputs explicitly instead of leaving them indefinitely parked in `created`

This is also the right time to preserve the architectural boundary described in the project docs:

- intake happens through API and persistence
- runtime consumes structured context
- worker execution is separate from request/response handling

## Goal

Build the minimum async runtime classification worker that consumes `pending-classification` task runs and advances them to `processing` or `failed`.

After this phase:

1. Fresh message writes enqueue a worker task after the database transaction commits.
2. The worker can load a `task_run` and its source message from persistent storage.
3. A runtime router classifies supported pending tasks into concrete task types.
4. Supported tasks transition from `created` to `processing`.
5. Unsupported tasks transition from `created` to `failed` with explicit error details.
6. Replayed message writes do not enqueue duplicate runtime work.

## Options Considered

### Option A: Inline runtime execution inside `POST /messages`

Deliver:

- call runtime processing directly from the request handler
- update task state before returning the HTTP response

Pros:

- fewer moving parts
- simplest manual demo path

Why not now:

- collapses intake and worker boundaries
- makes request latency depend on runtime behavior
- works against the repository's explicit Celery worker skeleton

### Option B: Worker-backed classification loop

Deliver:

- keep API intake unchanged
- enqueue a Celery task only after a fresh successful create
- process the task run in a dedicated runtime/orchestrator layer

Pros:

- matches the intended architecture
- keeps request handling fast and deterministic
- creates the smallest honest path toward the later runtime loop

Tradeoff:

- requires a bit more scaffolding than inline execution

### Option C: Polling scanner over `task_runs`

Deliver:

- periodic process finds every `created` task and processes it

Why not now:

- no explicit dispatch boundary
- weaker ownership between the request that created the task and the worker that consumes it
- harder to test and reason about than one-task-by-id execution

## Chosen Approach

Use Option B.

Phase 4A will add the minimum worker-backed runtime classification loop, but it will stop strictly before confirmation, inventory writes, audit writes, and WebSocket fanout.

The runtime outcome surface in this phase is intentionally small:

- supported pending tasks become `processing`
- unsupported pending tasks become `failed`

This phase does not yet:

- call OCR/ASR/vision providers
- write inventory
- create confirmations
- write user-visible result cards

## Scope Decisions

### 1. Dispatch boundary

`POST /api/v1/sessions/{session_id}/messages` should dispatch runtime work only when:

- the message write is fresh
- not an idempotent replay

The route or route-adjacent boundary should enqueue:

- `process_task_run.delay(task_run_id)`

only after `create_message(...)` has already committed.

### 2. Runtime input support in Phase 4A

Phase 4A should handle the current message types as follows:

#### `receipt-image`

Deterministic route:

- `task_type = "receipt-ocr"`
- runtime marks the task `processing`

#### `text`

Development-only mock transcript shortcut:

- treat `message.text` as already-transcribed owner intent
- classify by keyword heuristics into:
  - `voice-stock-query`
  - `voice-stock-in`

This is an explicit mock-first shortcut for the current phase, not a final product contract.

#### `voice`

Rules:

- if `message.text` is present, treat it the same way as the `text` shortcut above
- if `message.text` is absent, fail the task with:
  - `error_code = "transcript_unavailable"`

This preserves honesty: Phase 4A still does not claim to perform ASR.

#### `image`

Rules:

- fail the task with:
  - `error_code = "image_runtime_not_supported"`

The image path stays intentionally deferred to the later multimodal phase.

## Architecture

### 1. Runtime context builder

Add a small runtime context builder under `backend/app/runtime` that loads:

- `shop`
- `session`
- `source_message`
- `task_run`

and produces a structured `RuntimeTurnContext`.

The context should include at least:

- `shop_id`
- `session_id`
- `source_message_id`
- `task_run_id`
- `input_kind`
- `locale`
- `timezone`
- `shop_rules`
- `recent_messages`
- `pending_confirmation_id = null`

The worker should consume this context rather than reach into random ORM state across multiple layers.

### 2. Runtime router

Add a minimal router under `backend/app/runtime` that consumes the context and returns a structured routing decision.

The routing decision should contain:

- `task_type`
- `assigned_employee_id`

Phase 4A should keep assignment simple:

- assign every successfully classified task to `xiaoya`

Reason:

- the current slice is only about intake classification
- later handoff from `xiaoya` to `laoli` belongs to subsequent runtime phases

### 3. Runtime processor

Add a runtime processor/orchestrator under `backend/app/runtime` that:

1. loads the task run
2. confirms it is still:
   - `status = "created"`
   - `task_type = "pending-classification"`
3. builds runtime context
4. routes or fails the task
5. updates the task row atomically

Supported classification result:

- set concrete `task_type`
- set `status = "processing"`
- set `assigned_employee_id = "xiaoya"`
- update `updated_at`

Unsupported result:

- set `status = "failed"`
- keep `task_type = "pending-classification"`
- set `error_code`
- set `error_message`
- set `result_summary`
- set `completed_at`
- update `updated_at`

### 4. Idempotent worker behavior

Worker processing by `task_run_id` must be safe to repeat.

Rules:

- if the task no longer exists, return a structured no-op result
- if the task is no longer `created`, return a structured no-op result
- if the task is no longer `pending-classification`, return a structured no-op result

This keeps the worker safe under:

- duplicate queue delivery
- retries
- manual re-dispatch

## Classification Heuristics

Phase 4A should use a deliberately small mock-first heuristic set for transcript-style input:

Query-intent keywords:

- `查`
- `库存`
- `还有`
- `剩`
- `多少`
- `查询`

Routing rule:

- if the normalized text contains any query keyword:
  - classify as `voice-stock-query`
- otherwise:
  - classify as `voice-stock-in`

This heuristic applies only to:

- `text`
- `voice` with a provided `text` field

## Worker Integration

Add a Celery task module under `backend/app/workers` that exposes:

- `process_task_run`

The task should be a thin wrapper around the runtime processor, not the place where business logic lives.

The task should return a small serializable result such as:

- `processed`
- `skipped`
- `failed`
- `task_run_id`
- `task_type`

This makes the worker independently testable and keeps runtime behavior inspectable in logs.

## API Impact

Phase 4A should not add new public routes.

Existing message create behavior stays externally stable:

- fresh create returns `201`
- replay returns `200`
- payload still reports the intake-created `task_run_id`

The only new behavior is internal:

- fresh creates enqueue worker processing
- replays do not enqueue again

## Error Handling

Phase 4A adds these internal/runtime error codes:

- `transcript_unavailable`
- `image_runtime_not_supported`
- `runtime_processing_error`

Unexpected processor exceptions should result in:

- `status = "failed"`
- `error_code = "runtime_processing_error"`
- stable `error_message`

This phase should not let runtime exceptions bubble out of the worker as silent state corruption.

## Testing Strategy

Phase 4A should be test-first and include:

1. Runtime router tests for:
   - text query classification
   - text stock-in classification
   - receipt-image classification
   - unsupported image path
2. Runtime processor tests for:
   - `created` pending task -> `processing`
   - unsupported path -> `failed`
   - already-processed task -> skipped/no-op
   - missing task -> skipped/no-op
3. Worker task tests for:
   - Celery wrapper calling the processor
   - serializable result shape
4. Message route tests for:
   - fresh create dispatches worker once
   - idempotent replay does not dispatch again

## Acceptance Criteria

Phase 4A is complete when all of the following are true:

1. Fresh message writes dispatch exactly one worker task after commit.
2. Replayed message writes do not dispatch worker processing again.
3. The runtime processor can load a `pending-classification` task run by id and build structured context.
4. `receipt-image` tasks become `processing` with `task_type = "receipt-ocr"`.
5. `text` tasks classify into `voice-stock-query` or `voice-stock-in` and become `processing`.
6. `voice` tasks without a text transcript fail with `transcript_unavailable`.
7. `image` tasks fail with `image_runtime_not_supported`.
8. Re-processing an already-advanced task is a no-op rather than a duplicate transition.
9. Backend tests, mobile tests, and Docker compose config remain green.

## Out of Scope

This phase explicitly does not implement:

- ASR provider calls
- OCR provider calls
- image recognition provider calls
- confirmation creation
- inventory writes
- audit writes
- session stream events
- WebSocket fanout
- user-visible result-card or confirmation-card messages
- handoff from `xiaoya` to `laoli`

## Follow-On Work

Once Phase 4A lands, the next natural runtime slices are:

1. replace the text shortcut with mock/real ASR input for `voice`
2. add mock OCR extraction and confirmation generation for `receipt-image`
3. add confirmation-driven inventory and audit writes

That sequence preserves the current worker boundary while expanding actual business execution one layer at a time.
