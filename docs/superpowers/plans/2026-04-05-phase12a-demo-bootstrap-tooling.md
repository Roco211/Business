# Phase 12A Demo Bootstrap Tooling Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a repeatable script and service that reset the current MVP into a representative demo state backed by real inventory, alerts, confirmations, and chat history.

**Architecture:** Build a testable demo bootstrap service, wrap it in a backend script, and verify idempotent representative state through backend tests.

**Tech Stack:** Python, FastAPI domain services, SQLAlchemy, pytest

---

## File Structure

- Create:
  - `backend/app/services/demo_state.py`
  - `backend/scripts/bootstrap_demo_state.py`
  - `backend/tests/test_demo_state_bootstrap.py`
  - `project_docs/demo-bootstrap-status.md`

### Task 1: Write Red Tests For Demo Bootstrap

- [ ] Add a failing backend test module that verifies:
  - bootstrap creates representative inventory, alerts, messages, and pending confirmations
  - bootstrap is repeatable and does not duplicate demo noise on the second run
- [ ] Keep assertions focused on business-visible state, not internal implementation details.
- [ ] Run `python -m pytest backend/tests/test_demo_state_bootstrap.py -q` and confirm the new tests fail first.

### Task 2: Implement Demo Bootstrap Service And Script

- [ ] Add `backend/app/services/demo_state.py` with:
  - controlled reset of mutable default-shop/session state
  - seed flows for stock-in, manual stock-out, pending stock-out confirmation, and pending receipt confirmation
  - typed summary of created state
- [ ] Add `backend/scripts/bootstrap_demo_state.py` as a thin wrapper that prints the summary.
- [ ] Re-run the targeted bootstrap tests until they pass.

### Task 3: Add Status Doc

- [ ] Add `project_docs/demo-bootstrap-status.md` explaining what the bootstrap tool creates and why it exists.

### Task 4: Final Verification

- [ ] Run:
  - `$env:PYTHONPATH='backend'; python -m pytest backend/tests -q`
  - `npm.cmd test -- --runInBand`
  - `docker compose -f infra/docker/docker-compose.yml --env-file .env.example config`
- [ ] Commit the bootstrap tooling slice.
