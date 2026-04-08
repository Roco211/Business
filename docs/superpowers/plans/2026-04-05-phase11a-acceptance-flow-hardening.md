# Phase 11A Acceptance Flow Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a readable acceptance-level regression suite that exercises the current MVP's most important owner flows across runtime, confirmations, inventory truth, alerts, and dashboard projections.

**Architecture:** Build a dedicated backend acceptance test module that drives the real FastAPI app and runtime processor through the existing public APIs and durable services. Keep the suite focused on golden-path business journeys rather than low-level edge cases.

**Tech Stack:** FastAPI TestClient, pytest, SQLAlchemy, existing runtime fixtures

---

## File Structure

- Create:
  - `backend/tests/test_mvp_acceptance_flows.py`
- Modify:
  - `project_docs/09-implementation-scope.md`

### Task 1: Write Red Acceptance Flows

- [ ] Add `backend/tests/test_mvp_acceptance_flows.py` with failing golden-path flows for:
  - chat stock-in confirmation
  - receipt batch stock-in
  - manual ledger stock-out opening a low-stock alert
  - chat stock-out confirmation
  - correction recovery clearing the low-stock alert
- [ ] Reuse minimal helper setup for:
  - runtime queue stubbing
  - uploaded receipt media seeding
  - reading back inventory, alerts, dashboard, audit logs, and message timeline
- [ ] Run `python -m pytest backend/tests/test_mvp_acceptance_flows.py -q` and confirm the new file fails if any assumptions are still missing.

### Task 2: Implement Or Refine Test Helpers

- [ ] Keep implementation changes minimal and preferably test-local.
- [ ] If existing contracts are awkward to exercise from acceptance tests, make the smallest production-safe refinements needed to support stable flow testing.
- [ ] Run the acceptance file again until all new flows pass.

### Task 3: Update Scope Docs

- [ ] Update `project_docs/09-implementation-scope.md` so the repo's current stage explicitly mentions executable acceptance coverage for the MVP owner flows.
- [ ] Keep the note short and implementation-status oriented.

### Task 4: Final Verification

- [ ] Run:
  - `$env:PYTHONPATH='backend'; python -m pytest backend/tests -q`
  - `npm.cmd test -- --runInBand`
  - `docker compose -f infra/docker/docker-compose.yml --env-file .env.example config`
- [ ] Commit the acceptance and docs slice.
