# Runtime Skeleton

Phase 4A turns this package into a real read-only dry-run runtime.

It now includes:

- deterministic input routing for text and voice
- mock audio transcription fixtures
- runtime context assembly from persisted session data
- deterministic success and failure summarization
- task-run processing orchestration used by the worker

The runtime still does not implement confirmations, inventory writes, audit writes, or WebSocket fanout.
