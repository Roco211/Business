# Phase 9B Image And Receipt Multimodal Closure Design

## Goal

Close the remaining mock-first multimodal gap after Phase 9A by adding upload-backed `image` and `receipt-image` entry flows, durable OCR truth, and runtime support for:

- `photo-stock-in`
- `photo-stock-query`
- `receipt-ocr`

This phase should keep the existing MVP constraints intact:

- reuse the current message -> task_run -> runtime -> session stream loop
- keep AI capabilities behind deterministic mock providers
- avoid introducing a second state machine for “interactive OCR editing”
- avoid inventing batch inventory-write semantics that the current confirmation commit path does not support

## Chosen Approach

Use the same upload-backed owner message contract that already exists for voice:

1. mobile requests a media upload
2. mobile marks the upload complete
3. mobile posts a session message with `message_type = image | receipt-image`
4. runtime classifies and processes the message

The runtime split for this phase is:

- `photo-stock-in`
  - recognized from an `image` message
  - enters the existing confirmation flow
  - approval continues to use the existing stock-in commit path
- `photo-stock-query`
  - recognized from an `image` message
  - completes as a read-only task
  - writes a readable runtime/system message summarizing recognized item + inventory result
- `receipt-ocr`
  - recognized from a `receipt-image` message
  - persists an `ocr_documents` record
  - completes as a read-only task
  - writes a readable runtime/system message summarizing extracted fields and low-confidence paths

## Why This Is The Best Next Slice

This keeps the implementation aligned with the existing architecture instead of forcing a large redesign:

- `photo-stock-in` can reuse the proven confirmation and inventory commit path
- `photo-stock-query` can reuse existing inventory read truth without introducing new write semantics
- `receipt-ocr` gains durable truth and explicit APIs now, while deferring multi-line receipt-to-inventory batching until a later phase that can design that model properly

The alternative would be to teach confirmation approval how to atomically commit multiple receipt line items in one shot. That is a valid future direction, but it would expand scope into new inventory batching rules, new chat confirmation UI, and new audit semantics. That is too much coupling for the current phase.

## Backend Design

### 1. Mock Multimodal Tooling

Extend the runtime mock tooling with deterministic fixtures for:

- image recognition for stock-in
- image recognition for stock query
- receipt OCR extraction

The fixture source remains:

- `media_id`
- optional owner-provided `text` hint

The runtime must not call external providers in this phase.

### 2. Runtime Routing

`backend/app/runtime/router.py` will change from blocking image inputs to deterministic routing:

- `image`
  - query hint -> `photo-stock-query`
  - otherwise -> `photo-stock-in`
- `receipt-image`
  - always -> `receipt-ocr`

Routing still returns one worker/employee owner for now (`xiaoya`).

### 3. Runtime Processing

`backend/app/runtime/processor.py` will gain two new completed paths and one reused confirmation path:

- `photo-stock-in`
  - create or reuse pending confirmation
  - confirmation fields mirror the existing stock-in schema:
    - `item_name`
    - `quantity`
    - `unit`
    - `price`
  - include image-specific metadata for observability:
    - `image_media_id`
    - `recognized_confidence`
- `photo-stock-query`
  - complete task directly
  - write runtime/system message with:
    - recognized item name
    - confidence
    - current stock
    - unit
    - low-stock state
- `receipt-ocr`
  - create durable OCR document truth
  - complete task directly
  - write runtime/system message with:
    - extracted line-item summary
    - total amount
    - low-confidence field paths when present

### 4. Durable OCR Truth

Add `ocr_documents` to the real schema and model layer.

Fields should follow the existing project docs:

- `ocr_document_id`
- `shop_id`
- `task_run_id`
- `media_id`
- `document_type`
- `status`
- `provider_name`
- `raw_text`
- `extracted_fields`
- `low_confidence_fields`
- timestamps

This phase uses one document type:

- `purchase-receipt`

Status flow:

- request creation from runtime or route
- immediately persist mock-completed result in the same transaction path for this MVP

### 5. OCR APIs

Implement the documented routes:

- `POST /api/v1/ocr-documents`
- `GET /api/v1/ocr-documents/{ocr_document_id}`

These routes expose the durable OCR truth for both direct testing and future mobile UI reuse.

### 6. Photo Query API

Implement the documented route:

- `POST /api/v1/inventory-items/recognize-and-query`

This route should reuse the same mock recognition service used by runtime so the codebase has one recognition contract, not two independent fixture implementations.

### 7. Session Stream

No new websocket protocol is needed.

The existing message and task events are enough because:

- owner image/receipt messages already emit `message.created`
- runtime completion/awaiting-confirmation already emits `task.updated`
- runtime/system summaries already emit `message.created`

OCR-specific event types remain out of scope for this phase.

## Mobile Design

### 1. Generalized Media Demo Panel

Replace the voice-only demo panel with a generalized media demo panel that exposes:

- `Voice Query Demo`
- `Voice Stock-In Demo`
- `Photo Query Demo`
- `Photo Stock-In Demo`
- `Receipt OCR Demo`

The UI remains intentionally simple and demo-oriented. We do not need native camera integration yet; upload-backed mock media is enough.

### 2. Reusable Upload-Backed Demo Hooks

Keep the existing upload primitives:

- `useCreateMediaUploadMutation`
- `useCompleteMediaUploadMutation`
- `useSendMessageMutation`

Then add small higher-level hooks for:

- image demo send
- receipt demo send

The hook contract should mirror the existing voice demo flow so the screen keeps one simple “submit and refresh” pattern.

### 3. Chat Readability

Chat does not need rich OCR/result card components in this phase.

Instead:

- owner-authored image/receipt messages remain visible in the durable timeline
- runtime/system messages summarize recognition/OCR results in readable text
- existing pending confirmation card support is reused for `photo-stock-in`

This keeps the final UI intentionally small while still demonstrating the complete multimodal loop.

### 4. Test Stability

The fresh worktree baseline exposed a cold-cache mobile test flake where the first full `jest --runInBand --no-cache` run can time out on the initial `ChatScreen` loading transition.

This phase should opportunistically stabilize the chat tests by preferring stronger synchronization points over narrow default waits, so the expanded media coverage does not worsen that flake.

## Out Of Scope

The following remain explicitly deferred:

- native camera, photo library, or audio recording integration
- direct Android build/export fixes unless they block verification for this phase
- multi-line receipt approval that writes multiple inventory events in one confirmation approval
- OCR-specific websocket event types
- rich visual result cards with structured payload rendering
- real ASR/OCR/vision providers

## Acceptance Criteria

This phase is complete when all of the following are true:

- image uploads can be requested, completed, and sent as session messages
- receipt-image uploads can be requested, completed, and sent as session messages
- runtime routes `image` inputs into `photo-stock-in` or `photo-stock-query`
- runtime routes `receipt-image` into `receipt-ocr`
- `photo-stock-in` reaches `awaiting-confirmation`
- `photo-stock-query` completes and writes a readable runtime/system summary
- `receipt-ocr` persists an `ocr_documents` row and exposes it via API
- chat exposes the three media demo entry modes and refreshes after submission
- backend and mobile tests cover the new flows
- repo docs clearly state that receipt OCR persistence is implemented while batch receipt inventory commit is still deferred
