# Phase 14A Local Demo Smoke Automation Design

## Goal

Add one executable local-demo smoke flow so a developer can bring up the stack, reset it to the known-good demo state, and verify that the owner-facing MVP surface is healthy without manually clicking through every page first.

## Why This Matters

The repository now has:

- a real local Docker stack
- a repeatable demo bootstrap API
- durable owner workflows for chat, dashboard, ledger, confirmations, and realtime replay
- strong automated test coverage inside the repo

What it still lacks is one simple operator-facing answer to:

`After I start the local stack, how do I know the running system is actually healthy?`

Right now the answer is scattered across:

- Docker docs
- backend tests
- mobile instructions
- demo bootstrap notes

That is enough for contributors already deep in the codebase, but weaker for onboarding, handoff, QA, and demo-day confidence.

## Approaches Considered

### 1. Add Only A README Checklist

Pros:

- smallest documentation-only change

Cons:

- still manual
- easy to drift
- no executable proof that the live stack is healthy

### 2. Add A Live API Smoke Script Plus Runbook

Pros:

- verifies the real running API over HTTP
- keeps the scope bounded to the existing MVP surface
- easy for QA and developers to reuse
- complements the existing repo-internal tests instead of replacing them

Cons:

- requires a small amount of orchestration code and result formatting

### 3. Build A Full Local Environment Launcher

Pros:

- most automation

Cons:

- becomes OS- and shell-specific quickly
- mixes infrastructure startup policy with smoke verification
- larger maintenance surface than the current MVP needs

## Chosen Approach

Use approach 2.

This phase should:

- add a live API smoke runner script
- validate the known-good demo bootstrap and owner-facing read surfaces
- document the local run order clearly
- keep infrastructure startup itself in Docker Compose and avoid inventing a parallel launcher

## Design

### 1. Add One Reusable Smoke Runner

Create a small backend-side utility that can run against a live API base URL and validate the current demo stack.

The smoke runner should verify:

- `GET /health`
- `POST /api/v1/system/demo/bootstrap`
- `POST /api/v1/sessions/bootstrap`
- `GET /api/v1/dashboard/summary`
- `GET /api/v1/alerts?type=low-stock`
- `GET /api/v1/confirmations?status=pending`
- `GET /api/v1/sessions/{session_id}/messages`
- `GET /api/v1/sessions/{session_id}/stream-events?after_seq=0`

The runner should fail fast with a clear error if any of those surfaces drift from the expected demo shape.

### 2. Keep The Script Live-Stack Oriented

The smoke entrypoint should talk to the running API over HTTP rather than importing the app directly.

That matters because this phase is about validating the local running system, not just adding another in-process test path.

Defaults should stay simple:

- default API base URL: `http://127.0.0.1:8001`
- default auth token: `mock_owner_token`

Optional CLI flags can override these values for custom local environments.

### 3. Return Human-Readable And Machine-Readable Output

The smoke runner should print a compact JSON summary that includes the verified demo state:

- `shop_id`
- `session_id`
- inventory item count
- pending confirmation count
- low-stock alert count
- message count
- replay event count

This gives both:

- a human-readable quick confidence check
- a reusable output for shell automation if needed later

### 4. Document The Local Operator Flow

Update the local infra docs so the intended sequence is explicit:

1. bring up Docker services
2. run the smoke script
3. start Expo if mobile interaction is needed

This phase should also update the existing demo bootstrap status doc so it points to the smoke script as the recommended post-startup verification path.

### 5. Keep Scope Narrow

This phase is not:

- a full local process manager
- a mobile emulator launcher
- a browser automation suite
- a Docker black-box end-to-end test framework

The goal is one reliable smoke check for the current MVP, not a generalized deployment platform.

## Acceptance Criteria

This phase is complete when:

- the repo contains a reusable local demo smoke script
- that script validates the live API against the known-good demo state
- backend tests cover the smoke runner logic
- local infra/demo docs explain how to start the stack and run the smoke check
- the smoke runner can be executed successfully against the local running stack
