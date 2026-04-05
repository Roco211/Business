# Phase 9A Voice Entry Media Upload Foundation Design

## Context

After Phase 8B, the mobile app now has:

- a durable workgroup chat timeline
- owner-authored text sends
- inline stock-in confirmation handling
- realtime refresh from the shared session stream

What it still does not have is the documented media intake contract that should sit underneath voice-first interaction.

Today:

- the backend exposes no `media-uploads` routes
- the backend persists no `media_uploads` truth
- `POST /api/v1/sessions/{session_id}/messages` accepts `media_ids`, but it does not verify that the referenced media actually exists or is uploaded
- the mobile chat screen has no voice-first entry affordance
- the mobile app cannot exercise the existing `message_type = "voice"` path through a real upload-first workflow

The project docs consistently position voice as the primary owner input, with upload-backed media as the contract boundary before runtime processing. So the next slice should not jump straight to real recorder SDKs or photo OCR; it should first build the missing upload truth layer and a minimal voice entry path that uses it.

## Goal

Build the minimum mock-first media upload contract plus a voice-first chat entry path so the app can send upload-backed voice messages through the existing runtime loop.

After this phase:

1. the backend persists `media_uploads`
2. the backend exposes `POST /api/v1/media-uploads`
3. the backend exposes `POST /api/v1/media-uploads/{media_id}/complete`
4. session message creation validates that referenced media exists and is in `uploaded` status
5. chat exposes a minimal voice demo entry surface
6. voice demo sends follow `request upload -> complete upload -> post voice message`
7. the existing runtime loop processes those voice messages into either query results or confirmations

## Options Considered

### Option A: Add real device recording and camera capture now

Pros:

- closer to the final product vision
- would make the chat surface feel more realistic immediately

Why not now:

- requires new Expo packages and platform integration work before the upload contract even exists
- mixes device capture concerns with backend contract work
- would make the next slice too large and harder to validate

### Option B: Add mock-first media upload truth plus voice demo chat entry

Pros:

- closes a real architectural gap in the backend
- activates the existing voice runtime path without introducing heavy device dependencies
- keeps the slice narrow enough to verify end-to-end

Tradeoff:

- the mobile voice affordance will still be a demo workflow rather than true audio recording

### Option C: Skip media upload and send `voice` messages directly from chat

Pros:

- smallest implementation

Why not now:

- preserves a major contract gap between docs and code
- allows the app to bypass the very upload lifecycle the backend is supposed to enforce
- makes later real media support harder because clients would already depend on the shortcut

## Chosen Approach

Use Option B.

Phase 9A will introduce the durable `media_uploads` truth layer and wire chat to it through a voice-first demo flow.

Phase 9A will add:

- a `media_uploads` model and migration
- media upload request and completion routes
- media validation in message creation
- mobile hooks for request-upload, complete-upload, and voice demo send
- a compact chat voice demo panel that triggers the new flow

Phase 9A will not add:

- real microphone recording
- real image picking
- photo or receipt runtime handling
- object-storage verification against actual uploaded bytes
- offline upload queues

## Scope Decisions

### 1. Persist the full media upload truth model, but only exercise audio from the mobile app

The backend contract should support the documented media types:

- `audio`
- `image`
- `receipt-image`

That keeps the persistence model aligned with the docs and avoids a schema rewrite later.

But the mobile app in this phase should only author `audio` uploads. That keeps the delivered behavior tightly focused on the primary voice path.

### 2. Keep upload completion explicit even in mock mode

The upload contract should still require two steps:

1. request upload
2. mark upload complete

Even though this phase is mock-first and does not verify bytes in MinIO, the explicit completion step matters because it teaches the rest of the system that media is not usable until the upload lifecycle is complete.

### 3. Message creation must enforce uploaded-media readiness

`POST /api/v1/sessions/{session_id}/messages` should reject media references when:

- the `media_id` does not exist
- the `media_id` belongs to a different shop
- the `media_uploads.status` is not `uploaded`

This phase should return stable contract-level errors instead of silently accepting bad media references.

### 4. The mobile voice entry should be demo-driven, not fake recording UI

The chat surface should present a lightweight voice-first entry area with explicit demo actions such as:

- `Voice Query Demo`
- `Voice Stock-In Demo`

Each action should:

1. request an audio upload
2. complete the upload immediately in mock mode
3. post a `voice` message with the uploaded `media_id`
4. include a text hint that the current mock runtime can treat as the transcript

This preserves the upload-backed shape of the workflow without pretending the app is actually recording audio yet.

### 5. Chat should keep text entry and voice demo entry side by side

The current text composer is still useful and already tested.

So this phase should extend the composer instead of replacing it:

- keep text message send
- add a small voice demo panel near the composer
- surface upload/send errors locally without breaking the existing timeline

### 6. Realtime behavior should keep following read invalidation, not local patching

Voice demo sends already pass through the same message and runtime write paths as text messages.

So chat should continue using the shared session stream to refresh:

- the message list
- the pending confirmation list

No new local cache-patching layer should be introduced.

## Architecture

### Backend persistence and services

Add:

- `MediaUpload` ORM model
- Alembic migration for `media_uploads`
- request/complete contracts for the API
- focused media upload service functions for:
  - create pending upload
  - mark upload complete
  - validate media readiness for message creation

`messages.create_message()` should call the media readiness validator before persisting a media-backed message.

### Backend API surface

Add routes under `/api/v1/media-uploads`:

- `POST /api/v1/media-uploads`
- `POST /api/v1/media-uploads/{media_id}/complete`

Authentication stays on the existing mock owner contract.

The response can stay mock-friendly:

- `upload_url` and `public_url` may be generated mock URLs in this phase
- the important truth is the persisted media record and the explicit `uploaded` transition

### Mobile hooks and UI

Add focused chat-side hooks:

- `useCreateMediaUploadMutation`
- `useCompleteMediaUploadMutation`
- `useSendVoiceDemoMutation`

Add a small presentational component, for example:

- `MockVoiceEntryPanel`

Responsibilities:

- initiate the two-step upload lifecycle
- post the final `voice` message
- expose submitting and error state cleanly to `ChatScreen`

### Runtime compatibility

The existing runtime path for `voice` inputs already works when it receives either:

- a meaningful `text` hint
- or a known demo `media_id`

Phase 9A should keep runtime changes minimal by using the message `text` field as the transcript hint for voice demo submissions. That lets the system reuse the current `transcribe_audio(..., text_hint=...)` behavior without adding a media lookup dependency yet.

## Data and Contract Rules

### `media_uploads`

Persist at least:

- `media_id`
- `shop_id`
- `uploader_actor_type`
- `uploader_actor_id`
- `media_type`
- `file_name`
- `content_type`
- `size_bytes`
- `status`
- `upload_url`
- `public_url`
- `checksum_sha256`
- `uploaded_at`
- `created_at`
- `updated_at`

Statuses in this phase:

- `pending`
- `uploaded`
- `failed`

### Upload request behavior

Rules:

- `media_type` must be one of the supported contract values
- `file_name`, `content_type`, and `size_bytes` are required
- a successful request creates one `pending` media upload row
- the response includes the generated `media_id`, `upload_url`, and `public_url`

### Upload completion behavior

Rules:

- only `pending` uploads can transition to `uploaded`
- completion stores the provided checksum and size confirmation
- re-completing an already uploaded record should return a conflict instead of silently changing state

### Message validation behavior

Rules:

- text-only messages continue working unchanged
- any non-empty `media_ids` list requires every referenced media upload to be `uploaded`
- validation failures should stop message creation before any message or task row is written

## Testing Strategy

Cover:

1. media upload creation and completion service behavior
2. media upload API success and conflict/error paths
3. message creation rejecting missing or not-yet-uploaded media
4. mobile voice demo flow from upload request through final message post
5. chat UI error handling when upload creation, completion, or message post fails
6. chat timeline and confirmation refresh after a successful voice demo send

Backend and mobile both need focused tests in this phase because the slice bridges the contract boundary between them.

## Acceptance Criteria

Phase 9A is complete when:

1. the backend persists `media_uploads` and exposes request/complete routes
2. message creation rejects media that is missing or not uploaded
3. chat shows a voice-first demo entry area without removing the text composer
4. a successful voice demo send goes through request-upload, complete-upload, and post-message
5. the existing runtime loop processes the resulting `voice` message into either a query completion or pending confirmation
6. backend tests, mobile tests, and Docker compose validation all pass

## Out of Scope

- actual microphone recording
- actual camera or image picker integration
- receipt OCR processing
- photo stock-in or photo query runtime support
- object store byte verification
- upload retry queues
- generalized media gallery UI
