# Phase 10B Runtime Stock-Out Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the runtime/chat workflow to support owner-confirmed `stock-out` requests that commit through the durable inventory truth introduced in Phase 10A.

**Architecture:** Reuse the existing runtime -> confirmation -> approve -> inventory truth pipeline. Add a stock-out classification branch, a stock-out confirmation commit service, and a dedicated Chat confirmation card plus demo entry.

**Tech Stack:** FastAPI, SQLAlchemy, pytest, Expo React Native, Jest

---

## File Structure

- Create:
  - `backend/app/services/approved_stock_out_commits.py`
  - `apps/mobile/src/features/chat/components/PendingStockOutConfirmationCard.tsx`
- Modify:
  - `backend/app/runtime/router.py`
  - `backend/app/runtime/policy.py`
  - `backend/app/runtime/processor.py`
  - `backend/app/api/routes/confirmations.py`
  - `backend/tests/test_runtime_processor.py`
  - `backend/tests/test_confirmations_api.py`
  - `apps/mobile/src/features/chat/components/MockMediaEntryPanel.tsx`
  - `apps/mobile/src/features/chat/hooks/useSendVoiceDemoMutation.ts`
  - `apps/mobile/src/features/chat/screens/ChatScreen.tsx`
  - `apps/mobile/__tests__/ChatScreen.test.tsx`
  - `project_docs/02-api-contract.md`
  - `project_docs/11-realtime-contract-implementation-status.md`

### Task 1: Add Red Tests For Runtime Stock-Out

- [ ] Add failing backend tests for:
  - transcript classification to `voice-stock-out`
  - runtime processing that creates a pending `stock-out` confirmation
  - approval that commits a stock-out event and resolves the task
  - approval failure when stock is insufficient
- [ ] Run targeted pytest files and confirm the new tests fail.
- [ ] Commit the red-test slice.

### Task 2: Implement Backend Runtime Stock-Out

- [ ] Extend `backend/app/runtime/router.py` with stock-out heuristics.
- [ ] Update `backend/app/runtime/policy.py` so `voice-stock-out` requires `stock-out` confirmation.
- [ ] Update `backend/app/runtime/processor.py` to build stock-out confirmation fields and runtime messaging.
- [ ] Add `backend/app/services/approved_stock_out_commits.py` to resolve items, append stock-out events, refresh alerts, resolve task run, and write runtime messages.
- [ ] Branch stock-out approval in `backend/app/api/routes/confirmations.py`.
- [ ] Run targeted backend tests, then the full backend suite.
- [ ] Commit the backend slice.

### Task 3: Add Red Tests For Chat Stock-Out Interaction

- [ ] Add failing chat tests for:
  - rendering a pending stock-out confirmation card
  - approving a stock-out confirmation
  - showing a recoverable stock-out approval error
  - sending a voice stock-out demo
- [ ] Run `npm.cmd test -- --runInBand -- ChatScreen.test.tsx` and confirm the new tests fail.

### Task 4: Implement Chat Stock-Out Interaction

- [ ] Add `PendingStockOutConfirmationCard.tsx`.
- [ ] Extend `ChatScreen.tsx` to route `stock-out` confirmations to the new card.
- [ ] Extend `MockMediaEntryPanel.tsx` and `useSendVoiceDemoMutation.ts` with a stock-out demo flow.
- [ ] Run:
  - `npm.cmd test -- --runInBand -- ChatScreen.test.tsx`
  - `npm.cmd test -- --runInBand`
- [ ] Commit the mobile slice.

### Task 5: Update Docs And Verify

- [ ] Update `project_docs/02-api-contract.md` for the stock-out confirmation behavior.
- [ ] Update `project_docs/11-realtime-contract-implementation-status.md` to reflect runtime/chat stock-out coverage.
- [ ] Run final verification:
  - `$env:PYTHONPATH='backend'; python -m pytest backend/tests -q`
  - `npm.cmd test -- --runInBand`
  - `docker compose -f infra/docker/docker-compose.yml --env-file .env.example config`
- [ ] Commit the docs and verification slice.
