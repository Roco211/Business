# Phase 10B Runtime Stock-Out Design

## Goal

Extend the MVP from manual ledger-only `stock-out` into the runtime/chat workflow so owners can describe outgoing inventory in chat, review a confirmation card, and then commit the same durable `stock-out` truth already introduced in Phase 10A.

This phase should keep the scope intentionally narrow:

- support text and voice-driven stock-out intents
- require owner confirmation before commit
- reuse the existing confirmation lifecycle and chat timeline
- commit through the same inventory truth, alert refresh, audit, and realtime projection layers as manual stock-out

## Approaches Considered

### 1. Reuse Ledger Stock-Out Route Only

Have Chat call `POST /api/v1/inventory-events/stock-out` directly after parsing owner text on-device.

Pros:

- smallest backend delta

Cons:

- bypasses runtime and confirmation lifecycle
- moves parsing responsibility into the mobile client
- breaks the current architecture where chat-generated inventory changes originate from runtime task runs

### 2. Add Runtime Stock-Out With Confirmation

Teach the runtime router to classify stock-out language, create a pending confirmation, and on approval commit a durable `stock-out` event through a dedicated confirmation commit service.

Pros:

- matches the existing stock-in runtime pattern
- preserves auditability between owner message, task run, confirmation, and inventory event
- keeps the mobile client thin

Cons:

- requires touching runtime, confirmation approval routing, and Chat UI together

### 3. Skip Confirmation And Auto-Commit Runtime Stock-Out

Let runtime immediately reduce stock after parsing a stock-out request.

Pros:

- fastest owner flow

Cons:

- too risky for an MVP where language understanding is still mock-driven
- inconsistent with the current guarded write path for stock-in

## Chosen Approach

Use approach 2.

Runtime/chat stock-out should mirror the current stock-in confirmation pattern, but commit to the dedicated `stock-out` truth model instead of creating a stock-in event. This keeps the behavior legible and lets us reuse most of the existing workflow machinery.

## Backend Design

### 1. Runtime Classification

Extend transcript classification so text or voice phrases like `stock out`, `sold`, or `remove` route to:

- `voice-stock-out`

This remains the task type for both text and voice-originated chat inputs, consistent with the current `voice-stock-in` naming pattern.

### 2. Runtime Policy

`voice-stock-out` must require confirmation with a new confirmation type:

- `stock-out`

### 3. Confirmation Fields

Pending stock-out confirmations should carry fields shaped for the outgoing inventory use case:

```json
{
  "summary": "Please confirm the stock-out details before commit.",
  "transcript": "stock out 2 cola",
  "draft_fields": {
    "item_id": null,
    "item_name": null,
    "stock_out_quantity": null,
    "unit": null,
    "reason": "stock out via chat"
  },
  "required_fields": ["item_name", "stock_out_quantity", "reason"]
}
```

Rules:

- `item_name` is allowed because the runtime may not know the canonical item id yet
- `item_id` can be optionally supplied by future callers, but this phase does not require item-id-first UX
- `unit` is display-only if available; approval should not require it
- `reason` defaults to a runtime-friendly string and remains editable

### 4. Confirmation Approval Commit

Add a dedicated approval service for stock-out confirmations that:

- validates confirmation type is `stock-out`
- validates fields:
  - non-empty `item_name`
  - `stock_out_quantity > 0`
  - non-empty `reason`
- resolves the inventory item by:
  - explicit `item_id` when supplied
  - otherwise by unique active item-name match within the shop
- rejects:
  - unknown item
  - inactive item
  - ambiguous item name
  - insufficient stock
- writes one durable `stock-out` inventory event via the Phase 10A helper
- refreshes low-stock alerts
- writes one audit log with `inventory.stock_out_submitted`
- resolves confirmation + task run
- appends a system runtime message describing the committed stock-out

### 5. Approval Route Branching

`POST /api/v1/confirmations/{id}/approve` should branch by `confirmation_type`:

- `receipt-stock-in-batch` -> existing receipt batch commit
- `stock-out` -> new stock-out confirmation commit
- everything else -> existing stock-in confirmation commit

Reject behavior stays unchanged in this phase.

## Mobile Design

### 1. Chat Confirmation Rendering

Chat should render a dedicated stock-out card when:

- `confirmation.confirmation_type === "stock-out"`

The existing stock-in card should remain unchanged for stock-in confirmations.

### 2. Stock-Out Confirmation Card

The card should expose a minimal owner form:

- item name
- stock-out quantity
- reason

On approve:

- submit the edited fields
- refresh the timeline and pending confirmation list

On reject:

- reuse the existing reject mutation

### 3. Demo Entry

Extend `MockMediaEntryPanel` with a `Voice Stock-Out Demo` button so this workflow is reachable without manual audio capture.

The demo transcript should be explicit enough to deterministically route as stock-out.

## Out Of Scope

This phase does not include:

- image-driven stock-out
- batch stock-out
- refund/return semantics
- item-id picker UI
- automatic parsing of structured quantities from arbitrary natural language beyond the mock router heuristics

## Acceptance Criteria

This phase is complete when all of the following are true:

- runtime classifies explicit stock-out text/voice into `voice-stock-out`
- runtime creates pending `stock-out` confirmations instead of auto-completing the task
- approving a `stock-out` confirmation writes one durable `stock-out` inventory event
- stock-out approval refreshes alerts and writes the existing audit action
- insufficient stock or ambiguous item resolution returns recoverable API errors
- Chat renders a dedicated stock-out confirmation card with approve/reject
- Chat exposes a voice stock-out demo button
- backend and mobile tests cover the new workflow
