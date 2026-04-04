# Runtime Skeleton

Phase 4B extends the Phase 4A dry-run runtime with an explicit confirmation boundary.

It now includes:

- deterministic input routing for text and voice
- a minimal policy layer with `allow` and `require-confirmation`
- mock audio transcription fixtures
- runtime context assembly from persisted session data
- pending confirmation lookup for the current task run
- deterministic success and failure summarization
- task-run processing orchestration used by the worker

Behavior in this phase:

- `voice-stock-query` still completes as a read-only runtime result
- `voice-stock-in` now creates or reuses a pending confirmation and transitions the task to `awaiting-confirmation`
- owner approval and rejection happen through explicit confirmation API routes

The runtime still does not implement inventory writes, audit writes, alerts, session stream events, or WebSocket fanout.
