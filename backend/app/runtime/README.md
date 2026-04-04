# Runtime Skeleton

Phase 5A keeps the Phase 4B runtime loop and confirmation boundary, but approval is no longer workflow-only.

It now includes:

- deterministic input routing for text and voice
- a minimal policy layer with `allow` and `require-confirmation`
- mock audio transcription fixtures
- runtime context assembly from persisted session data
- pending confirmation lookup for the current task run
- deterministic success and failure summarization
- task-run processing orchestration used by the worker
- approval-backed inventory and audit truth writes for `voice-stock-in`

Behavior in this phase:

- `voice-stock-query` still completes as a read-only runtime result
- `voice-stock-in` now creates or reuses a pending confirmation and transitions the task to `awaiting-confirmation`
- owner approval and rejection happen through explicit confirmation API routes
- owner approval now commits inventory truth and audit truth
- owner rejection still resolves workflow without mutating inventory

The runtime still does not implement alerts, session stream events, or WebSocket fanout.
