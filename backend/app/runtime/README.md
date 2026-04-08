# Runtime Skeleton

Phase 6B keeps the Phase 6A runtime loop and ledger reads, then adds durable low-stock alerts plus the first dashboard summary surface.

Phase 7A extends the ledger from read-only browsing into the first manual correction write path.

It now includes:

- deterministic input routing for text and voice
- a minimal policy layer with `allow` and `require-confirmation`
- mock audio transcription fixtures
- runtime context assembly from persisted session data
- pending confirmation lookup for the current task run
- deterministic success and failure summarization
- task-run processing orchestration used by the worker
- approval-backed inventory and audit truth writes for `voice-stock-in`
- approval-backed low-stock alert refresh for the affected inventory item
- protected read routes for `inventory_items` and `audit_logs`
- protected read routes for `dashboard/summary` and `alerts?type=low-stock`
- a protected correction route at `POST /api/v1/inventory-events/corrections`
- a mobile ledger surface that reads the durable truth instead of static placeholder text
- a mobile dashboard surface that reads summary, low-stock alerts, and pending confirmations

Behavior in this phase:

- `voice-stock-query` still completes as a read-only runtime result
- `voice-stock-in` now creates or reuses a pending confirmation and transitions the task to `awaiting-confirmation`
- owner approval and rejection happen through explicit confirmation API routes
- owner approval now commits inventory truth and audit truth
- owner approval now also refreshes low-stock alert truth for the committed item
- owner correction now writes a `correction` inventory event, audit log, and refreshed alert truth in one transaction
- owner rejection still resolves workflow without mutating inventory
- owners can browse committed truth through:
  - `GET /api/v1/inventory-items`
  - `GET /api/v1/inventory-items/{item_id}`
  - `GET /api/v1/audit-logs?scope=inventory`
- owners can browse dashboard read models through:
  - `GET /api/v1/dashboard/summary`
  - `GET /api/v1/alerts?type=low-stock`
  - `GET /api/v1/confirmations?status=pending`
- owners can now correct ledger stock directly through:
  - `POST /api/v1/inventory-events/corrections`
- all protected read routes require `Authorization: Bearer <access_token>` from `POST /api/v1/auth/login`

Phase 8A adds the first durable session stream foundation on top of the existing runtime:

- the backend now persists `session_stream_events`
- the backend exposes `WS /api/v1/ws/sessions/{session_id}?token=<access_token>` where `access_token` comes from `POST /api/v1/auth/login`
- owner messages, runtime task transitions, confirmation lifecycle changes, inventory writes, and alert refreshes now append durable session events
- websocket clients receive `session.ready` and `stream.keepalive`, then pick up committed business events from the durable session stream
- the mobile app now boots one shared default session stream at the navigation shell level
- `DashboardScreen` and `LedgerScreen` refresh their reads from incoming session events
- `ChatScreen` now shows session connection state and recent session events instead of remaining a static placeholder

Phase 9A adds the missing upload-backed voice entry contract:

- the backend now persists `media_uploads`
- the backend exposes:
  - `POST /api/v1/media-uploads`
  - `POST /api/v1/media-uploads/{media_id}/complete`
- session message creation now rejects media references that are missing or not yet `uploaded`
- the mobile chat surface now includes voice demo entry actions that perform:
  - upload request
  - upload completion
  - final `voice` message post
- the runtime still reuses `text` as the mock transcript hint for those upload-backed voice messages

Phase 9B closes the remaining mock-first multimodal gap:

- the runtime now routes `image` messages into:
  - `photo-stock-query`
  - `photo-stock-in`
- the runtime now routes `receipt-image` messages into:
  - `receipt-ocr`
- `photo-stock-query` now completes as a read-only runtime result using persisted inventory truth
- `photo-stock-in` now reuses the existing confirmation flow with image-derived draft fields
- the backend now persists durable `ocr_documents`
- the backend now exposes:
  - `POST /api/v1/ocr-documents`
  - `GET /api/v1/ocr-documents/{ocr_document_id}`
  - `POST /api/v1/inventory-items/recognize-and-query`
- the mobile chat surface now exposes upload-backed:
  - `Photo Query Demo`
  - `Photo Stock-In Demo`
  - `Receipt OCR Demo`

Phase 9C turns receipt OCR into a real owner-confirmed inventory write path:

- `receipt-ocr` now persists durable OCR truth and then pauses in `awaiting-confirmation`
- runtime now creates `receipt-stock-in-batch` confirmations with editable draft receipt lines
- owner approval now atomically commits one inventory event per approved receipt line
- owner approval now also writes receipt-specific audit logs and refreshes low-stock alert projections for affected items
- `ChatScreen` now renders a dedicated receipt confirmation card instead of forcing receipt confirmations through the single-item stock-in card

The runtime still does not implement OCR-specific websocket events, upstream websocket message sending, stock-out flows, or replay endpoints.
