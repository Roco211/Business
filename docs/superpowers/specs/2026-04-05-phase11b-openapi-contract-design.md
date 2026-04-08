# Phase 11B OpenAPI Contract Snapshot Design

## Goal

Add a machine-readable API contract source to the repository by exporting the real FastAPI OpenAPI schema into versioned project docs and validating that export in tests.

This phase is intentionally narrow:

- no new runtime or inventory features
- no separate hand-written OpenAPI authoring workflow
- no attempt to solve every documentation problem at once

The goal is simply to make the current API surface auditable, comparable, and regressible from code.

## Problem

The repository now has:

- narrative API documentation in `project_docs/02-api-contract.md`
- real FastAPI routes and Pydantic contracts
- acceptance coverage for the main owner flows

What it still lacks is a committed machine-readable contract artifact. That gap matters because narrative docs are useful for humans but weak as a source of truth for:

- regression review
- downstream client generation
- contract drift detection
- future team handoff

## Approaches Considered

### 1. Keep Relying On Narrative Markdown Docs

Pros:

- no extra artifact to maintain

Cons:

- contract drift remains easy
- changes are harder to diff structurally

### 2. Export The Real FastAPI OpenAPI Schema And Commit It

Pros:

- generated from the real app
- cheap to diff in code review
- minimal new maintenance surface

Cons:

- snapshot files can be noisy when unrelated metadata changes

### 3. Hand-Author A Separate OpenAPI File

Pros:

- highly curated contract document

Cons:

- creates a second truth source immediately
- expensive to keep synchronized

## Chosen Approach

Use approach 2.

The repo should generate a committed OpenAPI snapshot from `create_app()` and validate that snapshot with a focused regression test.

## Design

### 1. Snapshot Artifact

Add a generated contract file under project docs, for example:

- `project_docs/generated/openapi-v1.json`

This file should be produced from the real FastAPI application object, not handwritten.

### 2. Generation Utility

Add a small script or utility entrypoint that:

- imports `app.main:create_app`
- obtains `app.openapi()`
- serializes deterministic JSON with stable formatting and key ordering
- writes the snapshot file

### 3. Regression Test

Add a backend test that:

- generates the current OpenAPI schema in memory
- loads the committed snapshot
- asserts the snapshot still matches the app contract

If a difference is intentional, the snapshot should be regenerated and committed as part of the change.

### 4. Scope Documentation

Add a short addendum explaining:

- where the machine-readable contract lives
- that it is generated from the real FastAPI app
- that narrative API docs remain explanatory, while the snapshot is the machine-readable truth artifact

## Constraints

- keep the generation deterministic
- avoid introducing a new build dependency if the standard library is sufficient
- prefer a single committed snapshot over a directory of fragmented files

## Out Of Scope

- client SDK generation
- schema linting against external governance rules
- websocket schema formalization
- JSON Schema exports for every internal model

## Acceptance Criteria

This phase is complete when:

- the repository contains a committed generated OpenAPI snapshot
- there is a repeatable utility to regenerate it from the real FastAPI app
- backend tests fail when the committed snapshot drifts from the live app schema
- project docs state where the machine-readable API contract now lives
