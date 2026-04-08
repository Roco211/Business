# Phase 14A Local Demo Smoke Automation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add one live API smoke runner and supporting runbook updates so developers can verify the local MVP stack after startup.

**Architecture:** Build a small reusable smoke helper in backend code, expose a thin script entrypoint that targets a running API base URL, then document the intended Docker -> smoke -> Expo flow in the local docs.

**Tech Stack:** Python, FastAPI HTTP contracts, stdlib HTTP client, Pytest, Docker Compose docs

---

## File Structure

- Create:
  - `backend/app/devtools/local_demo_smoke.py`
  - `backend/scripts/run_local_demo_smoke.py`
  - `backend/tests/test_local_demo_smoke.py`
- Modify:
  - `infra/docker/README.md`
  - `project_docs/demo-bootstrap-status.md`

### Task 1: Write Red Tests For The Smoke Runner

- [ ] Add `backend/tests/test_local_demo_smoke.py` with failing coverage for:
  - a happy path that validates health, demo bootstrap, dashboard, alerts, confirmations, messages, and replay events
  - a failure path where one live API response violates the expected demo state and the runner raises a clear error
- [ ] Keep the tests in-process by injecting a request adapter built from `TestClient`, so the runner logic can be exercised without a real TCP server in unit tests.
- [ ] Run `python -m pytest backend/tests/test_local_demo_smoke.py -q` and confirm the new tests fail first.

### Task 2: Implement The Reusable Smoke Helper

- [ ] Create `backend/app/devtools/local_demo_smoke.py` with:
  - a small result dataclass
  - a reusable `run_local_demo_smoke(...)` function
  - clear validation helpers for envelope parsing and demo-state assertions
- [ ] Keep HTTP request execution injectable so tests can pass a `TestClient`-backed adapter while the script uses a live HTTP adapter.
- [ ] Re-run `python -m pytest backend/tests/test_local_demo_smoke.py -q` until the smoke helper passes.

### Task 3: Add The Live Script Entrypoint

- [ ] Create `backend/scripts/run_local_demo_smoke.py` as a thin CLI wrapper around the reusable smoke helper.
- [ ] Support optional CLI overrides for:
  - `--api-base-url`
  - `--auth-token`
- [ ] Print a compact JSON summary on success and return a non-zero exit on validation failure.

### Task 4: Document The Operator Flow

- [ ] Update `infra/docker/README.md` with the intended local flow:
  - `docker compose up -d`
  - `python backend/scripts/run_local_demo_smoke.py`
  - `npx expo start`
- [ ] Update `project_docs/demo-bootstrap-status.md` so the demo bootstrap API and script docs point to the smoke runner as the recommended verification step after startup.

### Task 5: Verify Against The Real Local Stack

- [ ] Run:
  - `npm.cmd test -- --runInBand`
  - `$env:PYTHONPATH='backend'; python -m pytest backend/tests -q`
  - `docker compose -f infra/docker/docker-compose.yml --env-file .env.example up -d mysql redis minio api worker`
  - `python backend/scripts/run_local_demo_smoke.py`
  - `docker compose -f infra/docker/docker-compose.yml --env-file .env.example down`
- [ ] Confirm the live smoke script succeeds against the running local stack.
- [ ] Commit the local demo smoke automation slice.
