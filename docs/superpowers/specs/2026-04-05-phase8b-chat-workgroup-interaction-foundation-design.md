# Phase 8B Chat Workgroup Interaction Foundation Design

## Context

After Phase 8A, the project now has:

- durable message truth
- durable task truth
- durable confirmation truth
- durable inventory, audit, and alert truth
- durable session stream events with websocket fanout
- dashboard and ledger screens that already react to realtime updates

The remaining weakest product surface is still the workgroup chat.

Today:

- `ChatScreen` only renders recent session events
- the mobile app does not render the real session message timeline
- the owner cannot send a text task from the chat screen
- pending confirmations cannot be reviewed or acted on inside chat
- the documented "workgroup-style task interaction" still exists more in docs than in the app

The project docs consistently describe the workgroup screen as a real operating surface, not a debug event viewer. So the next slice should make chat useful before the codebase expands into stock-out, OCR follow-ups, or richer multimodal capture.

## Goal

Build the minimum real workgroup interaction loop for the chat screen by connecting it to the existing message, confirmation, and realtime contracts.

After this phase:

1. chat renders the durable session message timeline
2. the owner can send a text message from chat
3. chat shows pending confirmation cards for the active session flow
4. the owner can approve or reject a pending confirmation from chat
5. chat refreshes messages and confirmations when relevant session-stream events arrive
6. the implementation stays mock-first and text-only for authoring input

## Options Considered

### Option A: Keep chat as a stream monitor and build stock-out next

Pros:

- moves inventory coverage forward
- avoids touching the most interactive mobile surface

Why not now:

- leaves one of the three core MVP screens functionally hollow
- conflicts with the docs, which position the workgroup as the main interaction entry point
- would keep confirmation handling split awkwardly between dashboard and backend-only truth

### Option B: Turn chat into the minimum real workgroup surface using existing APIs

Pros:

- closes the most visible product gap with the smallest new backend surface
- reuses already-built message, confirmation, and websocket foundations
- creates a stable base for later voice, image, and OCR inputs

Tradeoff:

- requires more UI state management than the current dashboard and ledger screens

### Option C: Jump directly to the full multimodal chat composer

Pros:

- gets closer to the final product vision faster

Why not now:

- would pull audio capture, media drafts, upload flows, and OCR entry into one phase
- would make the slice too large to validate cleanly
- would create a lot of UI without first proving the core chat data loop

## Chosen Approach

Use Option B.

Phase 8B will turn chat into the minimum real workgroup operating surface by wiring the mobile app to the existing backend contracts.

Phase 8B will add:

- a message query hook for the active session
- a text message send mutation
- pending confirmation rendering inside chat
- approve and reject confirmation actions from chat
- realtime-driven refresh logic for messages and confirmations
- focused tests for the new interaction loop

Phase 8B will not add:

- voice recording
- media uploads
- image or receipt composer flows
- stock-out flows
- replay endpoints
- cache framework adoption

## Scope Decisions

### 1. Chat should render durable messages, not just ephemeral events

The source of truth for the timeline should be `GET /api/v1/sessions/{session_id}/messages`.

The session stream remains a trigger mechanism for refresh and connection-state display, not the primary message store. This keeps chat aligned with the same durable truth model already used elsewhere in the project.

### 2. Authoring input stays text-only in this phase

The mobile chat composer should support:

- text input
- send button
- submitting state
- recoverable error state

This phase should not expose:

- voice capture controls
- `+` media panel behavior
- local attachment drafts

Those are documented future capabilities, but they are not needed to prove the chat data loop.

### 3. Confirmation cards should be task-centric and editable enough to complete the current stock-in flow

For the current runtime slice, pending confirmations are stock-in confirmations whose `fields` payload includes:

- `summary`
- `transcript`
- `draft_fields`
- `required_fields`

The mobile chat UI should render one compact confirmation card per pending confirmation and allow the owner to:

- inspect summary and transcript
- edit the approval payload fields needed by the current backend contract
- approve
- reject

The approval form only needs to support the currently required stock-in fields:

- `item_name`
- `quantity`
- `unit`
- `price`

If later confirmation types appear, this phase can safely fall back to showing a read-only summary instead of attempting dynamic forms.

### 4. Confirmation cards should be correlated to the message/task timeline when possible

Messages already carry `task_run_id`, and confirmations already carry `task_run_id`.

So Phase 8B should correlate pending confirmations to the message timeline by `task_run_id` when possible:

- if a confirmation matches a message-linked task, show the confirmation card immediately after the related message cluster
- if a pending confirmation has no matching rendered message yet, show it in a dedicated pending section near the bottom of chat

This gives the screen a real workgroup feel without requiring a complex generalized timeline engine.

### 5. Realtime behavior should invalidate reads, not mutate local copies

The mobile data layer still uses focused fetch hooks instead of a shared cache.

So chat should follow the same stable pattern as dashboard and ledger:

- subscribe once via the shared session stream
- when relevant events arrive, refresh the message and confirmation queries

Relevant events in this phase:

- `message.created`
- `task.updated`
- `confirmation.created`
- `confirmation.resolved`
- `inventory.updated`

`inventory.updated` matters because an approved confirmation leads to a follow-up runtime/system message and inventory truth changes that the user should see reflected quickly.

### 6. The backend contract stays mostly stable

Phase 8B should prefer using the existing backend routes:

- `GET /api/v1/sessions/{session_id}/messages`
- `POST /api/v1/sessions/{session_id}/messages`
- `GET /api/v1/confirmations?status=pending&limit=20`
- `POST /api/v1/confirmations/{confirmation_id}/approve`
- `POST /api/v1/confirmations/{confirmation_id}/reject`

The only backend changes allowed in this phase are small contract-shaping improvements that reduce ambiguity for the mobile client, such as projecting fields the UI already needs. No new subsystem should be introduced.

## Architecture

### Mobile data hooks

Add focused chat hooks under `apps/mobile/src/features/chat/hooks`:

- `useSessionMessagesQuery`
- `useSendMessageMutation`
- `useChatPendingConfirmationsQuery`
- `useApproveConfirmationMutation`
- `useRejectConfirmationMutation`

Responsibilities:

- load durable chat messages for the shared session
- submit owner-authored text messages with generated `client_request_id`
- load pending confirmations needed by chat
- submit approval or rejection actions
- expose loading, error, and refresh behavior in the same style as existing dashboard and ledger hooks

### Chat screen composition

`ChatScreen` should move from an event-list placeholder to three visible sections:

1. chat header
   - session title
   - websocket connection state
2. timeline
   - owner and system messages from the durable message query
   - inline pending confirmation cards when correlated by `task_run_id`
3. composer
   - text input
   - send action
   - inline submission error if send fails

If the session bootstrap failed, the existing unavailable state should still win.

### Confirmation card component boundary

Add a focused presentational component for stock-in confirmation handling so `ChatScreen` does not own all input state directly.

Suggested responsibility split:

- `ChatScreen` owns loading, refresh, and high-level screen state
- confirmation card component owns local field edits and approve/reject button behavior for one card

The component should remain narrow and explicitly stock-in shaped for now instead of pretending to support every future confirmation type.

### Realtime refresh boundary

`ChatScreen` should refresh its reads when the shared session stream receives relevant events.

That refresh logic should live in the screen layer, matching the current dashboard and ledger pattern, instead of being hidden inside each hook.

## Data and UI Rules

### Message rendering

Render at least:

- actor label derived from `actor_type`
- message text
- creation timestamp as a lightweight secondary label

Behavior:

- if a message has no text, show a simple fallback label based on `message_type`
- order messages chronologically from oldest to newest within the fetched page
- keep the empty state explicit when no messages exist yet

### Text send behavior

Rules:

- trim whitespace before submission
- do not submit empty text
- generate a fresh `client_request_id` per submission
- disable the send action while submitting
- clear the draft only after success
- refresh the message list after a successful submit

The send flow should stay pessimistic rather than optimistic in this phase.

### Pending confirmation behavior

Rules:

- only render pending confirmations
- prefill editable fields from `fields.draft_fields` when present
- send the approve payload as a plain `fields` object matching the backend contract
- on approve or reject success, refresh both messages and confirmations
- surface backend validation or conflict errors inline on the card

### Error behavior

Chat should keep the rest of the screen usable when one mutation fails.

Examples:

- send failure should not hide existing messages
- one failed confirmation action should not block other cards
- a confirmations query failure should show a local error block while still rendering loaded messages if available

## Testing Strategy

Cover:

1. message query hook behavior
2. message send mutation success and failure behavior
3. chat rendering of durable messages instead of session events
4. inline confirmation card rendering and local field editing
5. approve and reject actions with success and failure paths
6. chat refresh reactions to relevant session-stream events

Prefer mobile tests for this phase unless a small backend contract adjustment is introduced.

## Acceptance Criteria

Phase 8B is complete when:

1. `ChatScreen` renders durable session messages from the backend
2. the owner can submit a text message from chat
3. the screen renders pending stock-in confirmation cards
4. the owner can approve or reject a confirmation from chat
5. relevant session-stream events trigger chat refreshes
6. failed send or confirmation actions surface recoverable UI errors
7. mobile tests pass and broader regression verification remains green

## Out of Scope

- voice recording UI
- image capture or receipt capture UI
- media upload APIs
- stock-out and correction authoring from chat
- timeline virtualization
- offline draft persistence
- generalized dynamic confirmation schema rendering
