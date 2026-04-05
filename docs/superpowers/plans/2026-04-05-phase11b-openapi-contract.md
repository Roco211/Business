# Phase 11B OpenAPI Contract Snapshot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Commit a machine-readable OpenAPI snapshot generated from the real FastAPI app and protect it with a regression test.

**Architecture:** Add one deterministic generator utility, one committed snapshot artifact, one snapshot regression test, and one short project-doc addendum describing the machine-readable contract source.

**Tech Stack:** FastAPI, Python stdlib JSON, pytest

---

## File Structure

- Create:
  - `backend/tests/test_openapi_contract_snapshot.py`
  - `project_docs/generated/openapi-v1.json`
  - `project_docs/02-api-contract-machine-readable-status.md`
  - a small generator utility in an appropriate backend/scripts or tooling location

### Task 1: Write Snapshot Regression Test

- [ ] Add a failing backend test that loads the committed snapshot and compares it to the current `create_app().openapi()` output.
- [ ] Keep the comparison deterministic by normalizing JSON ordering and formatting.
- [ ] Run the targeted test and confirm it fails before the snapshot and utility exist.

### Task 2: Add Generator And Snapshot

- [ ] Add the generator utility that writes the OpenAPI snapshot from the real FastAPI app.
- [ ] Generate and commit `project_docs/generated/openapi-v1.json`.
- [ ] Re-run the targeted snapshot test until it passes.

### Task 3: Add Machine-Readable Contract Status Doc

- [ ] Add a short addendum explaining where the generated contract lives and how it relates to `project_docs/02-api-contract.md`.

### Task 4: Final Verification

- [ ] Run:
  - `$env:PYTHONPATH='backend'; python -m pytest backend/tests -q`
  - `npm.cmd test -- --runInBand`
  - `docker compose -f infra/docker/docker-compose.yml --env-file .env.example config`
- [ ] Commit the snapshot hardening slice.
