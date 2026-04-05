# 11 Realtime Contract Implementation Status

Date: `2026-04-05`

This addendum records what is actually implemented in the repository today relative to `11-realtime-contract.md`.

## Implemented Now

- Durable `session_stream_events` with strict per-session `seq`
- `WS /api/v1/ws/sessions/{session_id}?token=mock_owner_token`
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
- `ChatScreen` shows connection state plus a rolling list of recent session events

## Still Out Of Scope

- OCR-specific realtime events
- Upstream websocket writes from the app
- Replay or backfill endpoints
- Broker-backed cross-process push
