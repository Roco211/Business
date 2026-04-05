# Phase 12A Demo Bootstrap Tooling Design

## Goal

Add a repeatable demo/bootstrap tool that can reset the current MVP into a representative, stable showcase state using the real business services already present in the repository.

This phase is a deliberate pivot from the initially considered MySQL smoke slice. On this machine, Docker Compose configuration is valid, but the Docker daemon is not currently available, so a real MySQL smoke path cannot be verified end to end in this session. Rather than ship an unverified environment harness, this phase focuses on the next most valuable hardening layer that is fully implementable and testable now.

## Why This Matters

The repository now has:

- durable business truth
- acceptance coverage for the main owner flows
- a committed machine-readable OpenAPI contract

What it still lacks is a convenient way to put the app into a compelling, known-good demo state without manually replaying several flows by hand. That gap matters for:

- internal demos
- onboarding new engineers
- validating UI behavior against realistic data
- future environment smoke work that needs a canonical seed state

## Approaches Considered

### 1. Keep Relying On Manual Seeding Through Tests Or Ad Hoc Steps

Pros:

- no new tooling

Cons:

- demo state remains tribal knowledge
- setup is slow and easy to drift

### 2. Add A Service-Backed Demo Bootstrap Tool

Pros:

- reproducible
- testable in-process
- reuses the real domain flows instead of fake fixture tables

Cons:

- requires careful reset semantics for mutable demo state

### 3. Add A Docker-Based Demo Environment First

Pros:

- eventually useful for pilot-like environments

Cons:

- blocked by current machine daemon availability
- does not solve what representative state should actually be

## Chosen Approach

Use approach 2.

This phase should create a deterministic demo bootstrap path that:

- resets mutable default-shop state
- seeds a meaningful mix of inventory, alerts, pending confirmations, and chat history
- uses the real services and runtime flows wherever practical

## Target Demo State

After bootstrap, the default MVP should have a state that is immediately useful in the mobile app and API:

### Dashboard

- at least one open low-stock alert
- at least one pending confirmation
- at least one completed task today

### Chat

- recent successful stock-in history
- one pending stock-out confirmation card
- one pending receipt confirmation card

### Ledger

- at least two active inventory items
- one low-stock item
- audit trail and inventory events present

## Design

### 1. Seed Through Real Services

Prefer these existing paths over raw table inserts:

- `create_message` + `process_task_run`
- confirmation approval services
- inventory stock-out service

This keeps seeded data honest to the current business model.

### 2. Controlled Reset

The bootstrap tool should only reset mutable data tied to the default single-shop MVP context:

- messages
- task runs
- confirmations
- OCR documents
- media uploads
- inventory items
- inventory events
- alerts
- audit logs
- session stream events

The default shop and session records should be preserved and normalized, not re-created from scratch if already present.

### 3. Public Entry Point

Provide a script entry point, for example:

- `python backend/scripts/bootstrap_demo_state.py`

The script should print a concise summary of what it created so the operator knows the resulting state.

### 4. Testable Service Layer

Implement the main logic in a service module that returns a typed summary. The script should be a thin wrapper around that service.

This keeps the demo bootstrap both testable and reusable.

## Constraints

- deterministic enough for repeatable demos
- scoped to the current single-shop MVP context
- no destructive behavior outside the default demo shop/session
- prefer readable demo data over large volumes of seed noise

## Out Of Scope

- multi-shop seeding
- production-safe tenant-aware reset tools
- real MySQL smoke orchestration
- mobile UI automation

## Acceptance Criteria

This phase is complete when:

- the repository has a repeatable demo bootstrap script
- the script seeds representative dashboard/chat/ledger data through real business flows
- the bootstrap path is covered by backend tests
- running it twice yields a stable, usable demo state instead of duplicated noise
