# Phase 4A Runtime Dry-Run Worker Design

## Context

Phase 3A established the durable intake ledger:

- `messages`
- `task_runs`

Every successful owner message write now creates:

- one `message`
- one linked `task_run`

But the runtime boundary is still missing. Today the backend stops at:

- `task_type = "pending-classification"`
- `status = "created"`

and `backend/app/runtime` is still only a placeholder package.

The project docs also make the intended order clear:

1. message/task ledger
2. runtime loop
3. confirmation chain
4. inventory and audit writes
5. WebSocket/session stream fanout

So the next slice should not jump directly to confirmations, inventory writes, audit writes, or WebSocket delivery. It should first make `TaskRun` actually executable.

## Goal

Build the minimum worker-backed runtime execution skeleton as a read-only dry-run.

After this phase:

1. Fresh message writes enqueue exactly one worker task after commit.
2. The worker can consume a `created` `task_run` by id.
3. The runtime can route and execute supported text/voice inputs without touching inventory truth.
4. `task_runs.status` can advance from `created` to `processing` to `completed`, or to `failed`.
5. The runtime writes back a visible system/assistant text message to the same session.
6. The backend exposes a read-only polling contract for task status.

## Options Considered

### Option A: State-only classification worker

Deliver:

- worker classifies the task
- task status advances to `processing` or `failed`
- no result message, no task polling API

Pros:

- smallest code change

Why not now:

- too hard to observe from the outside
- frontend and manual verification would have to inspect the database directly
- leaves the phase technically functional but practically invisible

### Option B: Read-only dry-run runtime worker

Deliver:

- worker consumes a `task_run`
- runtime executes a mock/read-only path
- task completes or fails
- result is written back to both:
  - `task_runs.result_summary`
  - a new runtime-authored session message
- add a read-only `GET /api/v1/task-runs/{task_run_id}` route

Pros:

- still keeps scope tightly below confirmations/inventory/WebSocket
- produces a real, observable backend loop
- creates a stable seam for later provider and confirmation work

Tradeoff:

- slightly larger than a pure state-only worker

### Option C: Full P0 closed loop now

Deliver:

- runtime
- confirmations
- inventory writes
- audit writes
- WebSocket updates

Why not now:

- too many new subsystems at once
- confirmations do not exist in the repo yet
- would blur the boundary between runtime execution and business side effects

## Chosen Approach

Use Option B.

Phase 4A will build the minimum worker-backed runtime execution skeleton, but it will remain strictly read-only from a business-truth perspective.

That means:

- runtime may classify and summarize
- runtime may write a visible system/assistant message
- runtime may complete or fail the `task_run`

But runtime will not:

- create confirmations
- write inventory
- write audit logs
- publish WebSocket updates

## Scope Decisions

### 1. Supported inputs in Phase 4A

Phase 4A should support only:

- `text`
- `voice`

Those two inputs are enough to prove the runtime loop without pulling in multimodal pipelines.

### 2. Existing unsupported inputs

Because Phase 3A already allows additional message types into the ledger, the runtime must handle them explicitly instead of leaving them stranded.

For:

- `image`
- `receipt-image`

Phase 4A should mark the task as failed with:

- `error_code = "runtime_input_not_supported"`

and write back a runtime-authored message explaining that this input path is deferred to a later phase.

### 3. Voice handling

Phase 4A should not claim to perform real ASR.

Instead it should use a single mock read-only tool:

- `transcribe_audio`

Behavior:

- if `message.text` exists, treat it as a provided transcript hint
- otherwise, if the first `media_id` matches a supported fixture key, return a canned transcript
- otherwise fail with:
  - `error_code = "transcript_unavailable"`

This keeps the phase honest while still making `voice` executable.

### 4. Read-only dry-run outcome

Phase 4A should produce a runtime-authored plain text message in the same session describing one of:

- accepted stock-in dry-run
- stock query dry-run result
- unsupported input
- transcript unavailable

The message should use:

- `actor_type = "system"`
- `actor_id = "runtime_system"`
- `message_type = "text"`

This avoids inventing card contracts too early while still making runtime results visible through the existing messages API.

### 5. Task status polling

Add a read-only route:

- `GET /api/v1/task-runs/{task_run_id}`

This route exists only because WebSocket delivery is still out of scope. It gives the frontend and manual verification a stable way to observe task lifecycle without introducing session stream events yet.

## Architecture

### 1. TaskRun lifecycle service

Add a focused service boundary for task execution lifecycle under `backend/app/services` or `backend/app/runtime` that owns:

- claiming a `created` task
- moving it to `processing`
- completing it with `result_summary`
- failing it with `error_code` and `error_message`

Rules:

- only `created` tasks may be claimed
- already-advanced tasks must return a structured no-op result
- updates must be atomic per task transition

### 2. Runtime context builder

Add a runtime context builder under `backend/app/runtime` that loads:

- `task_run`
- `source_message`
- `session`
- `shop`
- recent messages for the same session

and produces a structured `RuntimeTurnContext`.

For Phase 4A, the context should include:

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

### 3. Router

Add a minimal deterministic router under `backend/app/runtime`.

For `text` and transcribed `voice` input:

- if normalized text contains a query keyword:
  - route to `voice-stock-query`
- otherwise:
  - route to `voice-stock-in`

For unsupported message types:

- return a block/unsupported result instead of a task type

### 4. PolicyGuard

Phase 4A should add only the smallest policy layer:

- `allow`
- `block`

Block cases in this phase:

- unsupported input kind
- missing transcript for `voice`

Do not add:

- reviewer
- confirmation-required outcomes
- escalation flow

### 5. ToolRunner

Phase 4A should add only one mock read-only tool:

- `transcribe_audio`

No committable tools are allowed in this phase.

The tool runner should remain a separate layer anyway so later phases can add providers without rewriting the processor.

### 6. Summarizer

Add a small summarizer that turns runtime outcomes into:

- `result_summary`
- runtime-authored text message content

Examples of dry-run outcomes:

- stock-in intent accepted for later confirmation phase
- stock query dry-run result from fixture data
- unsupported input deferred to later phase

### 7. Runtime message writer

Add a focused service that writes runtime-authored messages back into the session ledger.

Responsibilities:

- create the runtime/system message
- associate it with the originating `task_run_id`
- update `sessions.last_message_at`

This service should reuse the same persistence model as owner messages instead of inventing a parallel result store.

### 8. Worker task wrapper

Add one Celery task under `backend/app/workers`, for example:

- `process_task_run(task_run_id)`

The task should be thin. It should call the runtime processor and return a small serializable result:

- `status`
- `task_run_id`
- `task_type`
- `error_code`

## Routing and Dry-Run Heuristics

### Query keywords

For the current mock runtime, use a small ASCII-safe keyword set:

- `query`
- `stock`
- `left`
- `remaining`
- `how many`
- `check`

If normalized text contains one of those keywords:

- route to `voice-stock-query`

Otherwise:

- route to `voice-stock-in`

Locale-specific Chinese keyword packs can be added later once the provider/runtime boundary is stable.

### Query dry-run output

For `voice-stock-query`, return a canned read-only summary such as:

- item lookup accepted
- fixture stock level
- note that this is mock runtime output

No inventory truth is written.

### Stock-in dry-run output

For `voice-stock-in`, return a canned acceptance summary such as:

- intake understood
- inventory write is deferred to later confirmation/inventory phases

No inventory truth is written.

## Dispatch Semantics

### Fresh create

After a fresh successful `POST /api/v1/sessions/{session_id}/messages`:

- dispatch `process_task_run.delay(task_run_id)`

### Idempotent replay

For an idempotent replay:

- do not dispatch again

### Queue failure after commit

If queue dispatch fails after the intake transaction has already committed:

- do not roll back the `message` or `task_run`
- leave the task in `created`
- surface the failure only as an internal runtime concern for later retry

This preserves intake truth even when background execution is temporarily unavailable.

## API Impact

### Existing route

`POST /api/v1/sessions/{session_id}/messages`

Behavior remains externally stable:

- `201` on fresh create
- `200` on replay

New internal behavior:

- fresh create dispatches the worker once

### New route

`GET /api/v1/task-runs/{task_run_id}`

Response should include at least:

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

This route is read-only and phase-local. It exists to bridge the gap until session stream events and WebSocket updates land.

## Error Handling

Phase 4A adds these runtime error codes:

- `transcript_unavailable`
- `runtime_input_not_supported`
- `runtime_processing_error`

Rules:

- expected block conditions should produce stable domain error codes
- unexpected processor exceptions should fail the task with:
  - `error_code = "runtime_processing_error"`

## Testing Strategy

Phase 4A should be test-first and include:

1. Router tests for:
   - text query routing
   - text stock-in routing
   - unsupported input block
2. Mock transcription/tool tests for:
   - text hint path
   - fixture `media_id` path
   - transcript unavailable path
3. Runtime processor tests for:
   - `created` text task -> `completed`
   - `created` voice task with fixture transcript -> `completed`
   - unsupported input -> `failed`
   - already-advanced task -> skipped/no-op
   - system/runtime message writeback
4. Worker task tests for:
   - thin wrapper behavior
   - serializable return payload
5. API tests for:
   - fresh message create dispatches the worker once
   - replay does not dispatch again
   - `GET /api/v1/task-runs/{task_run_id}` returns task state

## Acceptance Criteria

Phase 4A is complete when all of the following are true:

1. Fresh message writes enqueue exactly one worker task after commit.
2. Idempotent replays do not enqueue duplicate runtime work.
3. The worker can consume a `created` pending task by `task_run_id`.
4. `text` tasks run through the dry-run runtime and finish `completed`.
5. `voice` tasks with a fixture or hint transcript run through the dry-run runtime and finish `completed`.
6. Unsupported `image` and `receipt-image` tasks finish `failed` with `runtime_input_not_supported`.
7. Runtime writes a visible system/assistant text message back into the session ledger.
8. `task_runs.result_summary` and `error_code` have stable persisted values.
9. `GET /api/v1/task-runs/{task_run_id}` exposes the task lifecycle without requiring WebSocket.
10. No confirmation, inventory, audit, or WebSocket dependencies are introduced.

## Out of Scope

This phase explicitly does not implement:

- confirmations
- inventory writes
- audit logs
- alerts
- session stream events
- WebSocket fanout
- reviewer flow
- employee handoff
- OCR extraction
- image recognition
- real ASR
- media upload APIs

## Follow-On Work

Once Phase 4A lands, the next clean slices are:

1. replace the voice fixture path with a mock/real ASR provider boundary
2. add `receipt-image` OCR dry-run and then confirmation generation
3. add confirmation-approved inventory and audit writes

That keeps the system growing in the same order the docs describe: runtime first, then confirmations, then business-truth side effects, then realtime fanout.
