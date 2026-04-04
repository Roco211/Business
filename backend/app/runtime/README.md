# Runtime Skeleton

Phase 6A keeps the Phase 5A runtime loop and confirmation boundary, then adds the first read-side surface on top of the newly-written inventory truth.

It now includes:

- deterministic input routing for text and voice
- a minimal policy layer with `allow` and `require-confirmation`
- mock audio transcription fixtures
- runtime context assembly from persisted session data
- pending confirmation lookup for the current task run
- deterministic success and failure summarization
- task-run processing orchestration used by the worker
- approval-backed inventory and audit truth writes for `voice-stock-in`
- protected read routes for `inventory_items` and `audit_logs`
- a mobile ledger surface that reads the durable truth instead of static placeholder text

Behavior in this phase:

- `voice-stock-query` still completes as a read-only runtime result
- `voice-stock-in` now creates or reuses a pending confirmation and transitions the task to `awaiting-confirmation`
- owner approval and rejection happen through explicit confirmation API routes
- owner approval now commits inventory truth and audit truth
- owner rejection still resolves workflow without mutating inventory
- owners can browse committed truth through:
  - `GET /api/v1/inventory-items`
  - `GET /api/v1/inventory-items/{item_id}`
  - `GET /api/v1/audit-logs?scope=inventory`
- all read routes continue to require `Authorization: Bearer mock_owner_token`

The runtime still does not implement alerts, session stream events, or WebSocket fanout.
