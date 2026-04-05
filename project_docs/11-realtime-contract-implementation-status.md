# 11 Realtime Contract Implementation Status

Date: `2026-04-05`

This addendum records what is actually implemented in the repository today relative to `11-realtime-contract.md`.

## Implemented Now

- Durable `session_stream_events` with strict per-session `seq`
- Durable `media_uploads` with explicit `pending -> uploaded` transition
- `WS /api/v1/ws/sessions/{session_id}?token=mock_owner_token`
- `POST /api/v1/media-uploads`
- `POST /api/v1/media-uploads/{media_id}/complete`
- Emitted event types:
  - `message.created`
  - `task.updated`
  - `confirmation.created`
  - `confirmation.resolved`
  - `inventory.updated`
  - `alert.updated`
  - `session.ready`
  - `stream.keepalive`

## Delivery Model

- Business writes append durable session events in the same transaction as business truth
- The API process then delivers committed events to websocket clients by tailing `session_stream_events`
- This keeps the current MVP compatible with separate API and worker processes without adding a broker

## Mobile Behavior

- The mobile app bootstraps the default session once at the navigation shell
- One shared websocket connection is reused across the three top-level tabs
- `DashboardScreen` and `LedgerScreen` react to incoming events by refreshing the relevant REST reads
- `ChatScreen` renders the durable message timeline for the default session
- `ChatScreen` sends owner-authored text messages through the existing session message API
- `ChatScreen` also exposes upload-backed voice demo actions that request media upload, complete it, and then send a `voice` message
- `ChatScreen` renders pending stock-in confirmation cards and supports approve/reject actions
- `ChatScreen` refreshes messages and confirmations when relevant session events arrive

## Still Out Of Scope

- OCR-specific realtime events
- Upstream websocket writes from the app
- Replay or backfill endpoints
- Broker-backed cross-process push
