# Phase 11A Acceptance Flow Hardening Design

## Goal

Turn the current MVP from a collection of well-tested subsystems into a repo with explicit, readable acceptance coverage for the core owner flows.

This phase does not add new product capabilities. Instead, it hardens the existing implementation by expressing the most important business journeys as end-to-end acceptance tests against the real FastAPI app, database, runtime processor, confirmation flow, inventory truth, alerts, and dashboard projections.

## Why Now

The repository now supports:

- chat-driven stock-in
- receipt batch stock-in
- manual ledger stock-out
- chat-driven stock-out
- manual correction
- low-stock alerts
- dashboard summary projections

These behaviors are already individually tested, but the coverage is scattered across many files and mostly organized by service or route. That is great for local correctness, but weaker for answering the higher-level question:

`Can this project act as a reliable coding blueprint for the next team or next phase?`

Acceptance coverage closes that gap by making the intended owner journeys legible and regressible.

## Approaches Considered

### 1. Keep Relying On Existing Unit And Route Tests

Pros:

- no new test layer

Cons:

- important user journeys remain split across many files
- harder to see whether the MVP still supports the documented end-to-end flows
- weaker as executable development documentation

### 2. Add Focused API-Level Acceptance Flows

Pros:

- best balance between fidelity and speed
- exercises real contracts across multiple subsystems
- produces readable executable documentation

Cons:

- some setup helper duplication is unavoidable

### 3. Add Docker Or Real-MySQL Black-Box E2E Tests First

Pros:

- higher environment fidelity

Cons:

- much slower and more brittle for the current iteration
- obscures functional regressions behind environment noise

## Chosen Approach

Use approach 2.

This phase adds a single acceptance-oriented backend test module that treats the repo as a working MVP system and validates the most important owner flows end to end.

## Acceptance Scope

The suite should cover these flows:

### 1. Chat Stock-In Confirmation Flow

Flow:

- owner sends text message
- runtime classifies `voice-stock-in`
- pending confirmation is created
- owner approves confirmation
- inventory event, audit log, and runtime message are written

Key assertions:

- task transitions: `created -> awaiting-confirmation -> completed`
- one `stock-in` inventory event exists
- runtime message timeline includes the confirmation prompt and commit message

### 2. Receipt Batch Stock-In Flow

Flow:

- owner uploads receipt image
- runtime creates receipt confirmation
- owner approves receipt lines
- two inventory events and two audit logs are written

Key assertions:

- durable `ocr_document` exists
- receipt confirmation resolves successfully
- committed line items appear in inventory truth

### 3. Manual Ledger Stock-Out Flow

Flow:

- owner submits `POST /api/v1/inventory-events/stock-out`
- stock is reduced
- alert projection updates
- dashboard summary reflects the new low-stock state

Key assertions:

- one `stock-out` inventory event exists
- low-stock alert is opened when threshold is crossed
- dashboard summary counts remain internally consistent

### 4. Chat Stock-Out Confirmation Flow

Flow:

- owner sends text message
- runtime classifies `voice-stock-out`
- pending `stock-out` confirmation is created
- owner approves confirmation
- stock is reduced via durable stock-out truth

Key assertions:

- confirmation type is `stock-out`
- resulting inventory event uses `event_type = stock-out`
- audit log action is `inventory.stock_out_submitted`

### 5. Manual Correction Recovery Flow

Flow:

- owner submits a correction after stock has fallen low
- inventory quantity is restored
- low-stock alert projection clears

Key assertions:

- one `correction` inventory event exists
- correction audit log is written
- low-stock alert transitions back to resolved/absent state

## Design Constraints

- keep the suite deterministic and SQLite-backed for speed
- reuse the real app, routes, and services instead of mocking business logic
- mock only the runtime queue dispatch boundary the same way current route tests do
- avoid duplicating every edge case from the lower-level test modules; acceptance tests should cover golden-path business journeys

## Out Of Scope

This phase does not include:

- browser/emulator UI automation
- dockerized black-box E2E
- real MySQL acceptance tests
- new inventory capabilities
- formal performance benchmarking

## Acceptance Criteria

This phase is complete when all of the following are true:

- the repo contains a dedicated acceptance-oriented test module for the MVP owner flows
- that module covers stock-in, receipt batch stock-in, manual stock-out, runtime stock-out, and correction recovery
- the acceptance tests validate projections such as alerts and dashboard summary where those behaviors matter
- the full backend test suite still passes
- the implementation-scope docs mention that these MVP flows now have executable acceptance coverage
