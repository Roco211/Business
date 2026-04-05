# Phase 12B Demo Bootstrap API Design

## Goal

Expose the existing demo bootstrap capability through an authenticated backend API so QA, frontend developers, and future automation can reset the default MVP state without shell access.

## Why This Matters

Phase 12A added a repeatable service and script for rebuilding the default demo state, but that capability still lives only in the backend shell.
That leaves an unnecessary gap for:

- frontend and mobile developers who need a fast reset during manual testing
- QA workflows that should trigger a known-good seed state through HTTP
- future demo tooling that should not fork a second reset implementation

## Approaches Considered

### 1. Keep The Script As The Only Entry Point

Pros:

- no new API surface

Cons:

- not accessible from app-adjacent tooling
- forces shell access for every reset

### 2. Add A Thin Authenticated API Wrapper Around `demo_state.bootstrap_demo_state`

Pros:

- reuses the tested service layer
- keeps one source of truth for reset behavior
- easy to document and add to OpenAPI

Cons:

- introduces a privileged reset endpoint that must stay tightly scoped

### 3. Add A Mobile-Only Debug Button First

Pros:

- visible to app developers immediately

Cons:

- couples demo reset to one client
- still needs a backend trigger underneath

## Chosen Approach

Use approach 2.

This phase should add a narrow owner-authenticated HTTP endpoint that:

- calls the Phase 12A demo bootstrap service
- returns the typed bootstrap summary in a standard API envelope
- keeps the script entrypoint intact as an ops/developer convenience
- updates the machine-readable OpenAPI snapshot so the contract stays current

## Design

### 1. Reuse The Existing Service

`backend/app/services/demo_state.py` remains the only place that knows how to reset and seed the default demo state.
The new route should only orchestrate authorization, call the service, and serialize the response.

### 2. Keep The Endpoint Explicitly Privileged

Use the current mock owner token gate.
The endpoint is for development and showcase workflows, not for end-user product behavior.

### 3. Return A Stable Summary Contract

The API response should include the same stable summary fields already returned by the script:

- `shop_id`
- `session_id`
- inventory item counts and names
- pending confirmation counts and types
- open low-stock alert counts and item names
- message and task counts

### 4. Preserve One Truth For Contracts

Because the repository now enforces an OpenAPI snapshot, this phase must update the generated snapshot and keep the new endpoint reflected in the committed contract output.

## Acceptance Criteria

This phase is complete when:

- an authenticated backend endpoint can trigger demo bootstrap
- unauthorized requests are rejected
- repeated API calls still produce a stable demo state
- the OpenAPI snapshot includes the new endpoint and response shape
- demo bootstrap docs mention both script and API entrypoints
