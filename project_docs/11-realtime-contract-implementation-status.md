# 11 Realtime Contract Implementation Status

Date: `2026-04-05`

This addendum records what is actually implemented in the repository today relative to `11-realtime-contract.md`.

## Implemented Now

- Durable `session_stream_events` with strict per-session `seq`
- `GET /api/v1/sessions/{session_id}/stream-events`
- Durable `media_uploads` with explicit `pending -> uploaded` transition
- `WS /api/v1/ws/sessions/{session_id}?token=<opaque bearer token>`
- `POST /api/v1/media-uploads`
- `POST /api/v1/media-uploads/{media_id}/complete`
- `POST /api/v1/ocr-documents`
- `GET /api/v1/ocr-documents/{ocr_document_id}`
- `POST /api/v1/inventory-items/recognize-and-query`
- `POST /api/v1/inventory-events/stock-out`
- runtime routing for `voice-stock-out` with pending `stock-out` confirmations
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
- websocket delivery cursors are now tracked per connection instead of per session
- reconnecting websocket clients can provide `after_seq` to replay missed durable events
- This keeps the current MVP compatible with separate API and worker processes without adding a broker

## Mobile Behavior

- The mobile app bootstraps the default session once at the navigation shell
- One shared websocket connection is reused across the three top-level tabs
- the shared mobile session stream now remembers the latest accepted durable business `seq`
- reconnect attempts now include `after_seq=<latest durable seq>` when there is replayable history
- stale or duplicate replayed business events are ignored on the mobile side
- `DashboardScreen` and `LedgerScreen` react to incoming events by refreshing the relevant REST reads
- `LedgerScreen` now supports manual correction and manual stock-out writes
- `ChatScreen` renders the durable message timeline for the default session
- `ChatScreen` sends owner-authored text messages through the existing session message API
- `ChatScreen` also exposes upload-backed voice demo actions that request media upload, complete it, and then send a `voice` message
- `ChatScreen` now also exposes upload-backed:
  - `Photo Query Demo`
  - `Photo Stock-In Demo`
  - `Voice Stock-Out Demo`
  - `Receipt OCR Demo`
- `ChatScreen` renders pending stock-in confirmation cards and supports approve/reject actions
- `ChatScreen` now also renders dedicated stock-out confirmation cards with editable item name, quantity, and reason
- `ChatScreen` now also renders dedicated receipt confirmation cards with editable draft line items
- `ChatScreen` refreshes messages and confirmations when relevant session events arrive
- receipt OCR truth is now durable through `ocr_documents`
- receipt approval now commits multiple inventory events, audit logs, and projection refreshes through the existing confirmation flow
- manual ledger stock-out now writes durable inventory truth, audit logs, and refreshed alert projections through the same session stream
- runtime/chat stock-out now resolves through the same durable inventory truth as manual stock-out

## Still Out Of Scope

- OCR-specific realtime events
- Upstream websocket writes from the app
- Broker-backed cross-process push
- replay-specific UI surfaces or manual operator backfill tooling
