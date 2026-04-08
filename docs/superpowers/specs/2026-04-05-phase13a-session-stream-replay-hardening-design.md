# Phase 13A Session Stream Replay Hardening Design

## Goal

Turn the current durable session stream into a truly recoverable realtime surface by adding replay/catch-up support across reconnects and multiple websocket consumers.

## Why This Matters

The repository already persists durable `session_stream_events`, but the delivery layer still has one important weakness:

- websocket delivery progress is tracked per session, not per connection
- reconnecting clients do not pass a durable cursor back to the server
- there is no owner-facing replay endpoint for controlled catch-up or diagnostics

That means the current MVP can look realtime in the happy path while still being lossy in exactly the moments that matter most:

- app reconnect after short network loss
- two mobile clients connected to the same session
- late subscribers joining an active session stream

This phase keeps the existing mock-first boundaries intact while making realtime recovery consistent with the durable event ledger that already exists.

## Approaches Considered

### 1. Fix Only The In-Memory Cursor Bug

Pros:

- smallest backend-only change

Cons:

- reconnecting clients still cannot ask for missed events
- mobile still falls back to broad REST refreshes instead of durable catch-up
- does not expose any replay contract for future QA or diagnostics

### 2. Add Replay Endpoint Plus Connection-Level Catch-Up

Pros:

- uses the existing durable event ledger instead of inventing a new sync model
- fixes multi-connection correctness and reconnect correctness together
- keeps the mobile app on the current one-session, one-stream architecture
- stays small enough for one bounded phase

Cons:

- requires coordinated backend, mobile, and contract updates

### 3. Build Full Bidirectional Realtime Sync

Pros:

- strongest long-term sync model

Cons:

- far beyond current MVP scope
- would add acknowledgements, richer error recovery, and likely a more opinionated client cache model

## Chosen Approach

Use approach 2.

This phase should:

- add a durable replay read route for `session_stream_events`
- make websocket replay use a caller-provided `after_seq` cursor
- track delivery progress per websocket connection instead of per session
- make the mobile session stream client reconnect with its latest durable business `seq`
- ignore duplicates and stale transport events on the mobile side

## Design

### 1. Add A Replay Read Contract

Expose:

- `GET /api/v1/sessions/{session_id}/stream-events?after_seq=<int>&limit=<int>`

Contract rules:

- returns only durable business events from `session_stream_events`
- excludes ephemeral transport events such as `session.ready` and `stream.keepalive`
- sorts ascending by `seq`
- uses the same mock owner auth as the rest of the current MVP
- clamps `limit` to a small safe upper bound

This gives the stack one explicit replay surface instead of making replay an internal websocket-only behavior.

### 2. Make Catch-Up Cursor Connection-Scoped

The current connection manager stores one last delivered `seq` per session, which means one websocket can accidentally advance delivery state for another websocket.

This phase should move that cursor down to the websocket connection level:

- each connected websocket tracks its own last delivered durable `seq`
- keepalive flushes look up missing events for that websocket only
- publish updates each websocket cursor only after that websocket actually receives the event

This keeps durable replay semantics correct for:

- multiple concurrent subscribers to one session
- reconnect-after-loss scenarios
- slow consumers

### 3. Let Websocket Connect Resume From `after_seq`

The websocket contract should accept an optional durable cursor:

- `WS /api/v1/ws/sessions/{session_id}?token=mock_owner_token&after_seq=<int>`

Connect behavior:

- validate auth and session as before
- accept the websocket
- initialize the connection cursor from `after_seq`
- emit `session.ready`
- flush any durable events with `seq > after_seq`
- continue normal keepalive/publish behavior from the connection-local cursor

Transport event rules stay the same:

- `session.ready` and `stream.keepalive` remain ephemeral
- they may carry the current known `seq`
- they do not create rows in `session_stream_events`
- they do not advance the durable replay cursor on the client

### 4. Track Durable Cursor In The Mobile Provider

`SessionStreamProvider` should remember the most recent durable business `seq` it has accepted.

The mobile layer should:

- pass a getter for the latest durable `seq` into the websocket client
- reconnect with `after_seq=<latest durable seq>`
- ignore duplicate or stale business events whose `seq` is already known
- continue ignoring `stream.keepalive` as a transport-only event

This phase should stay intentionally lightweight:

- no new local cache graph
- no upstream websocket sends
- no offline queueing
- no replay UI surface

### 5. Keep Existing Screen Refresh Semantics

Dashboard, Chat, and Ledger should continue to respond to session events exactly as they do today.

The improvement in this phase is reliability, not a new UI contract:

- missed events after reconnect are now replayed instead of silently skipped
- mounted screens still use their existing REST refresh paths
- no new screen-level state model is introduced

## Acceptance Criteria

This phase is complete when:

- owners can replay durable session events through a protected REST route
- a reconnecting websocket client can pass `after_seq` and receive missed business events in order
- two websocket consumers on the same session do not interfere with each other's delivery cursor
- the mobile session stream reconnects with its latest durable `seq`
- duplicate or stale replayed events are ignored on the mobile side
- backend and mobile tests cover replay/catch-up behavior
