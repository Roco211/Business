# Phase 12B Demo Bootstrap API Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expose the Phase 12A demo bootstrap service through an authenticated HTTP endpoint and keep the OpenAPI/docs layer aligned.

**Architecture:** Add a thin API route and response contract on top of `app.services.demo_state.bootstrap_demo_state`, cover it with route tests for auth and repeatability, and regenerate the committed OpenAPI snapshot so the machine-readable contract remains accurate.

**Tech Stack:** FastAPI, Pydantic, SQLAlchemy, pytest

---

## File Structure

- Create:
  - `backend/tests/test_demo_bootstrap_api.py`
- Modify:
  - `backend/app/contracts/system.py`
  - `backend/app/api/routes/health.py`
  - `project_docs/demo-bootstrap-status.md`
  - `project_docs/generated/openapi-v1.json`

### Task 1: Write Red API Tests

- [ ] Add a failing backend test module that verifies:
  - `POST /api/v1/system/demo/bootstrap` returns `401` without the mock owner token
  - authorized calls return the demo bootstrap summary envelope
  - calling the endpoint twice yields the same stable summary
- [ ] Keep assertions focused on contract shape and business-visible state.
- [ ] Run `python -m pytest backend/tests/test_demo_bootstrap_api.py -q` and confirm the new tests fail first.

### Task 2: Add The Route And Response Contract

- [ ] Extend `backend/app/contracts/system.py` with a response model for the bootstrap summary.
- [ ] Extend `backend/app/api/routes/health.py` with an authenticated `POST /api/v1/system/demo/bootstrap` handler that calls `bootstrap_demo_state`.
- [ ] Re-run `python -m pytest backend/tests/test_demo_bootstrap_api.py -q` until it passes.

### Task 3: Update Docs And OpenAPI Snapshot

- [ ] Update `project_docs/demo-bootstrap-status.md` to document both the script and API reset entrypoints.
- [ ] Regenerate `project_docs/generated/openapi-v1.json` from the live FastAPI app so the new endpoint is captured.
- [ ] Re-run the OpenAPI snapshot test and confirm it stays green.

### Task 4: Final Verification

- [ ] Run:
  - `$env:PYTHONPATH='backend'; python -m pytest backend/tests -q`
  - `npm.cmd test -- --runInBand`
  - `docker compose -f infra/docker/docker-compose.yml --env-file .env.example config`
- [ ] Commit the demo bootstrap API slice.
