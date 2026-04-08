# Phase 9A Voice Entry Media Upload Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the missing media upload truth layer and let Chat send upload-backed voice demo messages through the existing runtime loop.

**Architecture:** First add a durable `media_uploads` model, service layer, and request/complete routes in the backend, then enforce uploaded-media validation in session message creation. On the mobile side, add small upload and voice-demo hooks plus a compact voice entry panel so Chat can run a mock voice flow without adding real recorder dependencies yet.

**Tech Stack:** Python, FastAPI, SQLAlchemy, Alembic, pytest, TypeScript, Expo, React Native, Jest, Testing Library

---

### Task 1: Add durable media upload persistence and service tests

**Files:**
- Create: `backend/app/models/media_upload.py`
- Modify: `backend/app/models/__init__.py`
- Create: `backend/app/contracts/media_upload.py`
- Create: `backend/app/services/media_uploads.py`
- Create: `backend/alembic/versions/20260405_03_create_media_uploads.py`
- Create: `backend/tests/test_media_upload_service.py`
- Modify: `backend/tests/test_alembic_bootstrap.py`

- [ ] Write failing backend tests for pending upload creation, upload completion, and media readiness validation.
- [ ] Run `python -m pytest backend/tests/test_media_upload_service.py -q` and observe failure.
- [ ] Implement the `MediaUpload` model, migration, contracts, and service functions.
- [ ] Re-run `python -m pytest backend/tests/test_media_upload_service.py -q` until it passes.
- [ ] Run `python -m pytest backend/tests/test_alembic_bootstrap.py -q` to verify the migration chain still boots.
- [ ] Commit with `feat: add media upload persistence`.

### Task 2: Add media upload routes and enforce message media validation

**Files:**
- Create: `backend/app/api/routes/media_uploads.py`
- Modify: `backend/app/api/router.py`
- Modify: `backend/app/services/messages.py`
- Create: `backend/tests/test_media_uploads_api.py`
- Modify: `backend/tests/test_messages.py`
- Modify: `backend/tests/test_message_service.py`
- Modify: `backend/tests/test_runtime_processor.py`

- [ ] Write failing backend tests for upload request, upload completion, message rejection for missing/not-uploaded media, and runtime tests that seed uploaded voice media before use.
- [ ] Run the focused backend test set for media uploads, messages, and runtime and observe failure.
- [ ] Implement the media upload routes and wire uploaded-media validation into message creation.
- [ ] Re-run the focused backend test set until it passes.
- [ ] Commit with `feat: add media upload routes and message validation`.

### Task 3: Add mobile media upload and voice demo hooks

**Files:**
- Create: `apps/mobile/src/features/chat/hooks/useCreateMediaUploadMutation.ts`
- Create: `apps/mobile/src/features/chat/hooks/useCompleteMediaUploadMutation.ts`
- Create: `apps/mobile/src/features/chat/hooks/useSendVoiceDemoMutation.ts`
- Modify: `apps/mobile/__tests__/ChatScreen.test.tsx`

- [ ] Write failing mobile tests that prove a voice demo send performs upload request, upload completion, and final voice message post.
- [ ] Run `npm.cmd test -- --runInBand ChatScreen.test.tsx` in `apps/mobile` and observe failure.
- [ ] Implement the upload request, upload completion, and composed voice demo send hooks.
- [ ] Re-run `npm.cmd test -- --runInBand ChatScreen.test.tsx` until it passes.
- [ ] Commit with `feat: add voice demo upload hooks`.

### Task 4: Add the chat voice demo entry panel and integrate it into ChatScreen

**Files:**
- Create: `apps/mobile/src/features/chat/components/MockVoiceEntryPanel.tsx`
- Modify: `apps/mobile/src/features/chat/screens/ChatScreen.tsx`
- Modify: `apps/mobile/__tests__/ChatScreen.test.tsx`

- [ ] Write failing mobile tests for the visible voice demo entry panel, recoverable upload/send errors, and chat refresh after a successful voice demo send.
- [ ] Run `npm.cmd test -- --runInBand ChatScreen.test.tsx` in `apps/mobile` and observe failure.
- [ ] Implement the panel, wire it into `ChatScreen`, and keep the existing text composer intact.
- [ ] Re-run `npm.cmd test -- --runInBand ChatScreen.test.tsx` until it passes.
- [ ] Commit with `feat: add chat voice demo entry flow`.

### Task 5: Update status docs and verify the phase

**Files:**
- Modify: `backend/app/runtime/README.md`
- Modify: `project_docs/11-realtime-contract-implementation-status.md`

- [ ] Update the runtime and realtime implementation docs so they reflect upload-backed voice entry.
- [ ] Run `npm.cmd test -- --runInBand` in `apps/mobile`.
- [ ] Run `$env:PYTHONPATH='backend'; python -m pytest backend/tests -q`.
- [ ] Run `docker compose -f infra/docker/docker-compose.yml --env-file .env.example config`.
- [ ] Run `git status --short --branch`.
- [ ] Commit docs with `docs: update voice upload status`.
- [ ] Commit verification with `test: verify phase 9a voice upload foundation`.
