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
- all read routes continue to require `Authorization: Bearer mock_owner_token`

The runtime still does not implement alerts, session stream events, or WebSocket fanout.
