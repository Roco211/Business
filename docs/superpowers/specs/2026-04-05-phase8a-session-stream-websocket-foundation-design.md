# Phase 8A Session Stream WebSocket Foundation Design

## Context

After Phase 7A, the project now has:

- durable message truth
- durable task lifecycle truth
- durable confirmation truth
- durable inventory, alert, and audit truth
- readable dashboard and ledger surfaces

What it still does not have is the realtime fabric that the project docs already expect.

Today:

- the backend has no `session_stream_events` table
- the backend exposes no websocket session stream endpoint
- the mobile app has no shared session bootstrap or stream hook
- dashboard and ledger only refresh on first load or local mutation success
- chat is still a static placeholder

That means the codebase can write the right business truth, but it still cannot push that truth back to the app in the way the product docs describe.

## Goal

Build the minimum durable session-stream foundation so the backend can persist ordered session events and broadcast them over websocket, and the mobile app can react to those events by refreshing the right reads.

After this phase:

1. the backend persists ordered `session_stream_events`
2. the backend exposes `WS /api/v1/ws/sessions/{session_id}?token=mock_owner_token`
3. new business events are appended to the stream with strict per-session sequencing
4. the websocket endpoint sends `session.ready`, `stream.keepalive`, and committed business events
5. the mobile app holds one shared default session stream at the app shell level
6. dashboard and ledger refresh themselves when relevant session events arrive
7. chat at least shows session connection state and recent session events instead of remaining a dead placeholder

## Options Considered

### Option A: Keep polling and postpone websocket work

Pros:

- smallest implementation slice
- avoids connection management complexity

Why not now:

- directly conflicts with the documented realtime contract
- leaves `session_stream_events` and websocket behavior as pure documentation debt
- does not improve the currently weakest user-facing surface, which is chat

### Option B: Add a durable session stream table plus an in-process websocket hub

Pros:

- matches the current MVP scope in the docs
- keeps event ordering anchored in the database instead of in process memory
- avoids the overhead of a generic event bus
- is enough to unblock Chat, Dashboard, and Ledger refresh behavior

Tradeoff:

- requires touching multiple existing write paths so events are appended before commit and published after commit

### Option C: Introduce a generic event bus or broker now

Pros:

- potentially more scalable later

Why not now:

- far beyond current MVP needs
- adds deployment and operational complexity before there is a second backend process or external consumer
- would slow iteration more than it helps

## Chosen Approach

Use Option B.

Phase 8A will add:

- a persisted `session_stream_events` ledger
- a focused session event append service
- an in-process websocket connection manager
- a websocket endpoint for one session subscription at a time
- a shared mobile session bootstrap plus session stream provider
- screen-level refresh reactions for dashboard and ledger
- a minimal chat session stream view so realtime is visible in the app

Phase 8A will not add:

- upstream websocket message sending from the mobile app
- a generic event bus
- event replay or backfill endpoints
- OCR-specific realtime events
- stock-out write flows

## Scope Decisions

### 1. Persist only business events

The durable stream table should persist only business events that reflect committed business truth.

Persisted in this phase:

- `message.created`
- `task.updated`
- `confirmation.created`
- `confirmation.resolved`
- `inventory.updated`
- `alert.updated`

Ephemeral only in this phase:

- `session.ready`
- `stream.keepalive`

Out of scope in this phase:

- `ocr.updated`
- standalone `error` events

Runtime failures already surface through `task.updated` with `failed` status and error metadata, which is enough for the current product slice.

### 2. Sequence numbers must come from the database transaction

This phase should follow the documented rule:

1. write business truth
2. lock the session row
3. increment `sessions.last_event_seq`
4. insert `session_stream_events`
5. commit
6. publish to websocket

The websocket layer must never invent `seq` values in memory.

### 3. Use an append service plus explicit post-commit publish

The codebase already has several write paths that commit in different places:

- REST routes
- runtime processor
- confirmation approval flow
- correction flow

So the clean MVP boundary is:

- append durable session events before commit
- return the committed event records to the caller
- publish them only after commit succeeds

This avoids hidden transaction hooks while still keeping ordering correct.

### 4. Keep the websocket server single-process and best-effort

For the current MVP, one in-process connection hub is enough.

Rules:

- publish failures must not roll back committed database work
- missing subscribers are normal and should not be treated as errors
- connections are scoped by `session_id`

If the backend later runs multiple replicas, the stream table remains the source of truth and a broker can be added then.

### 5. Share one default session stream in the mobile app shell

The app currently has three top-level tabs that all describe the same default workgroup session.

So this phase should add a shared provider at the navigation shell level that:

- bootstraps the default session once
- opens one websocket connection for that session
- exposes connection state, current session id, and the latest received business event

This keeps the mobile side aligned with the docs' preference to reuse the same session stream instead of opening one websocket per tab.

### 6. React to events by invalidating reads, not by patching local caches

The current mobile data layer is simple local `useEffect` fetching without a cache library.

So the most stable MVP behavior is:

- receive a session event
- decide which screen-level reads are affected
- call each hook's existing `refresh()` function

This phase should not introduce manual in-memory list patching.

### 7. Chat should become visibly alive, not fully featured

Chat is still a skeleton. Fully implementing a complete composer, message history, and task timeline would make this phase too large.

So the minimum useful upgrade is:

- show session title or session id
- show websocket connection state
- show a short rolling list of recent session events

That makes realtime observable now without expanding scope into the full chat product.

## Architecture

### Backend

Add:

- `SessionStreamEvent` ORM model and Alembic migration
- websocket event contracts for outbound stream payloads
- a session event append service responsible for sequence assignment and inserts
- a websocket connection manager responsible for per-session fanout
- a websocket route under `/api/v1/ws/sessions/{session_id}`

Integrate event appends into current write paths:

- owner message creation appends `message.created`
- task lifecycle transitions append `task.updated`
- pending confirmation creation appends `confirmation.created`
- confirmation approval or rejection appends `confirmation.resolved`
- approved stock-in commits and manual corrections append `inventory.updated`
- alert refresh writes append `alert.updated` only when alert truth actually changes

### Mobile

Add:

- a bootstrap helper for `POST /api/v1/sessions/bootstrap`
- a shared session stream provider mounted above the tab navigator
- a lightweight websocket client helper for React Native
- screen reactions:
  - dashboard refreshes summary, alerts, and pending confirmations
  - ledger refreshes inventory items and audit logs
  - chat renders connection state and recent event cards

## API Impact

### Websocket endpoint

`WS /api/v1/ws/sessions/{session_id}?token=mock_owner_token`

Connection behavior:

- invalid token -> close as unauthorized
- unknown session -> close as not found
- successful connect -> send `session.ready`
- every keepalive interval -> send `stream.keepalive`
- every committed business event for that session -> send the stored stream event envelope

### Event envelope

```json
{
  "event_id": "evt_01J...",
  "seq": 12,
  "event_type": "task.updated",
  "session_id": "sess_01J...",
  "task_run_id": "task_01J...",
  "message_id": null,
  "occurred_at": "2026-04-05T08:15:30.123Z",
  "data": {
    "status": "awaiting-confirmation",
    "task_type": "voice-stock-in",
    "error_code": null
  }
}
```

Ephemeral events follow the same top-level shape, but `session.ready` and `stream.keepalive` do not consume new durable sequence numbers.

## Error Handling

Backend expectations:

- websocket auth failure closes the connection without mutating state
- websocket fanout errors are logged and swallowed
- session event append failures must fail the surrounding business transaction

Mobile expectations:

- reconnect with bounded backoff
- if the stream disconnects and later reconnects, refresh the affected reads instead of attempting event replay
- show a lightweight connection status in chat

## Testing Strategy

Cover:

1. session event append service sequencing and payload persistence
2. websocket route handshake, authorization, and keepalive behavior
3. event emission from existing business write paths
4. mobile session provider connection lifecycle
5. dashboard and ledger refresh reactions to received events
6. chat rendering of connection state and recent events

## Acceptance Criteria

Phase 8A is complete when:

1. `session_stream_events` exists with strict per-session sequencing
2. the backend serves a working session websocket endpoint
3. message, task, confirmation, inventory, and alert writes append session events
4. committed events are published after commit without risking data rollback
5. the mobile app opens one shared default session stream
6. dashboard and ledger refresh on relevant incoming events
7. chat displays session stream state and a recent event list
8. backend tests, mobile tests, and Docker compose validation all pass

## Out of Scope

- stock-out flow
- OCR document realtime flow
- offline replay or replay endpoints
- broker-backed cross-process websocket fanout
- generic cache framework adoption
- full chat composer and rich message timeline
