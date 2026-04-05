# Phase 9C Receipt Batch Stock-In Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend `receipt-image` from read-only OCR into an owner-confirmed batch stock-in flow that writes inventory truth, audit logs, and realtime projections.

**Architecture:** Reuse the existing confirmation and inventory commit path by introducing a new `receipt-stock-in-batch` confirmation type. Runtime will persist OCR truth, move the task into `awaiting-confirmation`, and chat will submit editable receipt line items through the existing approval endpoint.

**Tech Stack:** FastAPI, SQLAlchemy, Alembic, pytest, Expo React Native, Jest

---

## File Structure

- Create:
  - `backend/app/services/approved_receipt_stock_in_commits.py`
  - `apps/mobile/src/features/chat/components/PendingReceiptConfirmationCard.tsx`
- Modify:
  - `backend/app/api/routes/confirmations.py`
  - `backend/app/contracts/confirmation.py`
  - `backend/app/runtime/policy.py`
  - `backend/app/runtime/processor.py`
  - `backend/app/runtime/summarizer.py`
  - `backend/app/services/audit_logs.py`
  - `backend/app/services/inventory_events.py`
  - `backend/tests/test_confirmations_api.py`
  - `backend/tests/test_runtime_processor.py`
  - `apps/mobile/__tests__/ChatScreen.test.tsx`
  - `apps/mobile/src/features/chat/hooks/useApproveConfirmationMutation.ts`
  - `apps/mobile/src/features/chat/hooks/useChatPendingConfirmationsQuery.ts`
  - `apps/mobile/src/features/chat/screens/ChatScreen.tsx`
  - `project_docs/11-realtime-contract-implementation-status.md`
  - `backend/app/runtime/README.md`

### Task 1: Write Red Tests For Receipt Confirmation Runtime And Approval

- [ ] Add a failing runtime processor test in `backend/tests/test_runtime_processor.py` asserting that `receipt-image` ends in `awaiting-confirmation`, persists an OCR document, and creates a `receipt-stock-in-batch` confirmation.
- [ ] Add a failing confirmations API test in `backend/tests/test_confirmations_api.py` asserting that approving a receipt confirmation writes multiple `inventory_events`, multiple receipt audit logs, and completes the task.
- [ ] Add a failing confirmations API validation test asserting that approving a receipt confirmation with empty `items` returns `422 confirmation_fields_invalid`.
- [ ] Run:
  - `$env:PYTHONPATH='backend'; python -m pytest backend/tests/test_runtime_processor.py -q`
  - `$env:PYTHONPATH='backend'; python -m pytest backend/tests/test_confirmations_api.py -q`
- [ ] Confirm the new tests fail for the expected missing behavior.
- [ ] Commit the red-test slice.

### Task 2: Implement Receipt Batch Commit Service

- [ ] Add `backend/app/services/approved_receipt_stock_in_commits.py` with:
  - receipt payload parsing
  - atomic multi-line inventory commit
  - per-line audit log creation
  - task completion + runtime message writeback
- [ ] Extend `backend/app/services/audit_logs.py` with a helper for `inventory.receipt_stock_in_confirmed`.
- [ ] Reuse `resolve_inventory_item_for_stock_in` and `append_stock_in_event` instead of creating a second inventory write model.
- [ ] Update `backend/app/api/routes/confirmations.py` to dispatch approval by `confirmation_type`.
- [ ] Run the targeted confirmation API tests and make them pass.
- [ ] Commit the backend batch-commit slice.

### Task 3: Update Runtime For Receipt Awaiting-Confirmation

- [ ] Change `backend/app/runtime/policy.py` so `receipt-ocr` requires confirmation.
- [ ] Update `backend/app/runtime/processor.py` to:
  - create the OCR document before confirmation creation
  - derive receipt draft items from OCR fields
  - create a `receipt-stock-in-batch` confirmation
  - mark the task as `awaiting-confirmation`
  - write a receipt-specific runtime/system prompt
- [ ] Update `backend/app/runtime/summarizer.py` only as needed so completed receipt summaries still work for direct OCR routes while runtime-confirmation messaging stays explicit.
- [ ] Run:
  - `$env:PYTHONPATH='backend'; python -m pytest backend/tests/test_runtime_processor.py -q`
  - `$env:PYTHONPATH='backend'; python -m pytest backend/tests/test_confirmations_api.py -q`
  - `$env:PYTHONPATH='backend'; python -m pytest backend/tests -q`
- [ ] Commit the runtime slice.

### Task 4: Add Receipt Confirmation UI In Chat

- [ ] Add `apps/mobile/src/features/chat/components/PendingReceiptConfirmationCard.tsx` with editable receipt line rows and approve/reject actions.
- [ ] Extend `useChatPendingConfirmationsQuery.ts` types to represent receipt confirmation fields without breaking the existing stock-in card.
- [ ] Make `useApproveConfirmationMutation.ts` accept generic `Record<string, unknown>` fields so both confirmation cards share one mutation hook.
- [ ] Update `ChatScreen.tsx` to render confirmation cards by `confirmation_type`.
- [ ] Extend `apps/mobile/__tests__/ChatScreen.test.tsx` to cover receipt confirmation rendering and approval payload submission.
- [ ] Run:
  - `npm.cmd test -- --runInBand -- ChatScreen.test.tsx`
  - `npm.cmd test -- --runInBand`
- [ ] Commit the mobile slice.

### Task 5: Update Documentation And Final Verification

- [ ] Update `project_docs/11-realtime-contract-implementation-status.md` so receipt inventory commit is described as implemented rather than deferred.
- [ ] Update `backend/app/runtime/README.md` with the receipt confirmation/commit lifecycle.
- [ ] Run final verification:
  - `$env:PYTHONPATH='backend'; python -m pytest backend/tests -q`
  - `npm.cmd test -- --runInBand`
  - `docker compose -f infra/docker/docker-compose.yml --env-file .env.example config`
- [ ] Commit the docs and verification slice.
