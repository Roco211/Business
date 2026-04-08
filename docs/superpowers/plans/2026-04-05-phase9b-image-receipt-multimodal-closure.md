# Phase 9B Image And Receipt Multimodal Closure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add upload-backed image and receipt entry flows, runtime support for `photo-stock-in` / `photo-stock-query` / `receipt-ocr`, and durable OCR APIs while keeping the MVP mock-first architecture intact.

**Architecture:** Reuse the existing message-driven runtime loop. Extend the runtime mock tooling and router for image/receipt inputs, persist OCR truth via `ocr_documents`, and keep mobile changes focused on a generalized media demo panel plus readable chat summaries.

**Tech Stack:** FastAPI, SQLAlchemy, Alembic, pytest, Expo React Native, Jest

---

## File Structure

- Create:
  - `backend/alembic/versions/20260405_04_create_ocr_documents.py`
  - `backend/app/models/ocr_document.py`
  - `backend/app/contracts/ocr_document.py`
  - `backend/app/services/ocr_documents.py`
  - `backend/app/services/mock_multimodal.py`
  - `backend/app/api/routes/ocr_documents.py`
  - `apps/mobile/src/features/chat/components/MockMediaEntryPanel.tsx`
  - `apps/mobile/src/features/chat/hooks/useSendImageDemoMutation.ts`
  - `apps/mobile/src/features/chat/hooks/useSendReceiptDemoMutation.ts`
- Modify:
  - `backend/app/models/__init__.py`
  - `backend/app/api/router.py`
  - `backend/app/api/routes/inventory_items.py`
  - `backend/app/contracts/inventory_item.py`
  - `backend/app/runtime/router.py`
  - `backend/app/runtime/processor.py`
  - `backend/app/runtime/policy.py`
  - `backend/app/runtime/summarizer.py`
  - `backend/app/runtime/README.md`
  - `backend/tests/test_alembic_bootstrap.py`
  - `backend/tests/test_runtime_router.py`
  - `backend/tests/test_runtime_processor.py`
  - `backend/tests/test_inventory_items_api.py`
  - `backend/tests/test_messages.py`
  - `backend/tests/test_message_service.py`
  - `apps/mobile/src/features/chat/screens/ChatScreen.tsx`
  - `apps/mobile/__tests__/ChatScreen.test.tsx`
  - `project_docs/11-realtime-contract-implementation-status.md`

### Task 1: Write Backend Red Tests For Multimodal Routing And OCR Truth

- [ ] Add failing router tests in `backend/tests/test_runtime_router.py` for `image -> photo-stock-query`, `image -> photo-stock-in`, and `receipt-image -> receipt-ocr`.
- [ ] Add failing processor tests in `backend/tests/test_runtime_processor.py` for:
  - image query completing with readable runtime message
  - image stock-in entering confirmation
  - receipt OCR completing and persisting `ocr_documents`
- [ ] Add failing API tests in `backend/tests/test_inventory_items_api.py` for `POST /api/v1/inventory-items/recognize-and-query`.
- [ ] Add failing API tests in a new `backend/tests/test_ocr_documents_api.py` for create/get OCR document routes.
- [ ] Run only the new backend tests and confirm they fail for missing behavior.
- [ ] Commit the red-test slice.

### Task 2: Implement Mock Multimodal Services And Persistence

- [ ] Add `ocr_documents` model, contracts, service, and Alembic migration.
- [ ] Add one mock multimodal service module that owns deterministic image recognition and receipt extraction fixtures.
- [ ] Register the model and route imports in `backend/app/models/__init__.py` and `backend/app/api/router.py`.
- [ ] Implement `POST /api/v1/ocr-documents` and `GET /api/v1/ocr-documents/{ocr_document_id}`.
- [ ] Implement `POST /api/v1/inventory-items/recognize-and-query` using the shared mock recognition service.
- [ ] Run the new persistence/API tests and make them pass.
- [ ] Commit the persistence/API slice.

### Task 3: Implement Runtime Image And Receipt Processing

- [ ] Update `backend/app/runtime/router.py` so image and receipt inputs no longer fail with `runtime_input_not_supported`.
- [ ] Extend `backend/app/runtime/policy.py` so `photo-stock-in` requires confirmation and the read-only tasks complete directly.
- [ ] Update `backend/app/runtime/processor.py` to:
  - create photo stock-in confirmation fields from mock recognition
  - write query summary runtime messages for `photo-stock-query`
  - create/read OCR documents and write OCR summary runtime messages for `receipt-ocr`
- [ ] Update `backend/app/runtime/summarizer.py` with task-type-specific summaries for the new task types.
- [ ] Run the targeted runtime tests and then the full backend test suite.
- [ ] Commit the runtime slice.

### Task 4: Add Mobile Media Entry And Chat Coverage

- [ ] Replace `MockVoiceEntryPanel` usage in `apps/mobile/src/features/chat/screens/ChatScreen.tsx` with a generalized `MockMediaEntryPanel`.
- [ ] Add image and receipt demo hooks that reuse the existing upload create/complete hooks plus `useSendMessageMutation`.
- [ ] Keep the existing voice hook intact unless a tiny shared helper clearly reduces duplication.
- [ ] Extend `apps/mobile/__tests__/ChatScreen.test.tsx` to cover:
  - photo query demo submission
  - photo stock-in demo submission
  - receipt OCR demo submission
  - one media failure path beyond voice
  - stable loading synchronization on cold runs
- [ ] Run the mobile chat test file first, then the full mobile suite.
- [ ] Commit the mobile slice.

### Task 5: Update Docs And Final Verification

- [ ] Update `backend/app/runtime/README.md` to describe the new multimodal behavior and the explicit receipt batching deferment.
- [ ] Update `project_docs/11-realtime-contract-implementation-status.md` with the newly implemented media flows and OCR truth status.
- [ ] Run final verification:
  - `$env:PYTHONPATH='backend'; python -m pytest backend/tests -q`
  - `npm.cmd test -- --runInBand`
  - `docker compose -f infra/docker/docker-compose.yml --env-file .env.example config`
- [ ] Commit the docs + verification slice.
