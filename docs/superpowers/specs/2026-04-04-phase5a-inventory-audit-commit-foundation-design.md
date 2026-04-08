# Phase 5A Inventory and Audit Commit Foundation Design

## Context

Phase 4B established a durable human-approval boundary:

- `voice-stock-in` runtime work pauses in `awaiting-confirmation`
- one pending `Confirmation` exists per stock-in `TaskRun`
- the owner can approve or reject through explicit backend routes
- approval and rejection are visible in the session message ledger

What is still missing is the actual business-truth commit behind approval.

Today, approving a stock-in confirmation only records:

- `confirmations.status = "approved"`
- `task_runs.status = "completed"`
- one runtime/system resolution message

But the project docs consistently describe a stricter boundary:

1. approved stock-in should append an `InventoryEvent`
2. `InventoryItem.current_stock` should be updated in the same transaction
3. an `AuditLog` entry should be written for the committed business action
4. alert maintenance and realtime fanout can land later

So the next clean slice is not inventory read APIs or WebSocket delivery yet. It is the minimum transactional truth-write path behind confirmation approval.

## Goal

Build the smallest durable inventory-commit foundation so approving a pending stock-in confirmation writes real business truth instead of only closing workflow state.

After this phase:

1. approving a pending stock-in confirmation writes:
   - one `inventory_items` row if needed
   - one `inventory_events` row
   - one `audit_logs` row
2. the linked `inventory_items.current_stock` projection is updated in the same transaction as the new event
3. the linked `task_run` is completed only if the business write succeeds
4. the session ledger receives a success message that reflects committed inventory truth
5. rejecting a confirmation still performs no inventory or audit write
6. alerts, inventory read APIs, audit query APIs, session stream events, and WebSocket fanout remain out of scope

## Options Considered

### Option A: Expose direct `POST /api/v1/inventory-events` first

Deliver:

- inventory tables
- inventory event write route
- audit write route or implicit audit side effect

Pros:

- closer to the public API contract in `project_docs`
- reusable for manual correction later

Why not now:

- the current product flow already has an approval seam, so bypassing it would weaken the workflow the repo just established
- there is no UI or runtime path yet for selecting an existing `item_id`
- it adds a second write path before the confirmation-backed one is trustworthy

### Option B: Make confirmation approval the only truth-write entrypoint for now

Deliver:

- inventory and audit persistence
- one transactional commit orchestrator behind `POST /confirmations/{id}/approve`
- no new public inventory write route yet

Pros:

- matches the current implemented user flow exactly
- keeps truth-writing behind a single narrow seam
- lets inventory persistence land without inventing extra client behavior

Tradeoff:

- the documented direct inventory-event route still remains future work

### Option C: Bundle inventory writes, alerts, and websocket fanout together

Deliver:

- business write
- derived alert maintenance
- session stream events
- WebSocket push

Why not now:

- violates the project's stated layering to land transport before truth is stable
- adds too many failure surfaces to a phase that should prove transaction boundaries first

## Chosen Approach

Use Option B.

Phase 5A will turn confirmation approval into the minimum real inventory commit and stop there.

That means:

- only approval for `voice-stock-in` gains business side effects
- approval becomes an all-or-nothing transaction:
  - approve confirmation
  - resolve or create inventory item
  - append inventory event
  - update stock projection
  - append audit log
  - complete task run
  - write runtime/system ledger message
- any failure during that flow rolls the whole transaction back

This phase will not:

- expose public inventory read routes
- expose public audit query routes
- maintain `alerts`
- write `session_stream_events`
- publish WebSocket updates
- support stock-out or correction commits

## Scope Decisions

### 1. Only stock-in approval commits business truth

The current runtime only produces one confirmation-backed write path:

- `voice-stock-in`

So Phase 5A should only commit inventory truth for confirmations whose linked task run represents stock-in work.

If a later phase introduces other confirmation-backed actions, they should get their own commit paths rather than being folded into this one prematurely.

### 2. Approval payload becomes the stock-in source of truth

The current runtime confirmation payload is intentionally draft-shaped. It does not contain trustworthy structured extraction, only a transcript and empty draft fields.

So the owner-submitted approval payload should be treated as the authoritative business input for this phase.

The minimum accepted approved fields are:

```json
{
  "item_id": "item_001",
  "item_name": "Apple",
  "quantity": 3,
  "unit": "box",
  "price": 18.5
}
```

Rules:

- `item_id` is optional
- `item_name` is required and non-empty when `item_id` is absent
- `quantity` is required and must be `> 0`
- `unit` is required and non-empty
- `price` is required and must be `>= 0`
- when `item_id` is present, the resolved inventory row remains authoritative for the persisted item name

Why keep both `item_id` and `item_name`:

- current clients only know how to send `item_name`
- future clients can send `item_id` after inventory search exists
- this preserves forward compatibility without blocking current development

### 3. Inventory item resolution rules must be explicit

Phase 5A needs a deterministic rule for turning approved fields into one `inventory_items` row.

Use this order:

1. if `item_id` is present:
   - load that item
   - require it to belong to the same `shop_id` as the task session
   - require it to be active
2. else:
   - search active items in the same shop by exact trimmed `name`
   - if none exists, create a new item
   - if exactly one exists, use it
   - if more than one exists, fail with an ambiguity error and leave the confirmation pending

This phase should not invent fuzzy matching, barcode lookup, or category heuristics.

### 4. New inventory item defaults must be stable

When approval resolves to a brand-new item, create a row with these defaults:

- `item_id`: new prefixed id
- `shop_id`: from the linked session
- `sku`: `null`
- `name`: approved `item_name`
- `category`: `null`
- `barcode`: `null`
- `default_unit`: approved `unit`
- `current_stock`: `0` before event application, then projected to the committed after-value in the same transaction
- `current_price`: approved `price`
- `low_stock_threshold`: inherit `shops.default_low_stock_threshold`
- `image_media_id`: `null`
- `is_active`: `true`

This keeps the row honest without pretending the system already has classification, barcode, or image enrichment.

### 5. Unit handling stays conservative

Unit conversion is not in scope for this phase.

So if approval resolves to an existing inventory item, the approved `unit` must exactly match that item's `default_unit`.

If the unit does not match:

- do not append an inventory event
- do not complete the task
- do not approve the confirmation
- return a domain error such as `inventory_unit_mismatch`

This is intentionally strict. It avoids silently corrupting stock by mixing incompatible units.

### 6. Inventory stock remains a projection, not a source of truth

The project docs explicitly keep `inventory_items.current_stock` as a projection field derived from committed events.

So Phase 5A should:

- calculate `quantity_after = current_stock + quantity_delta`
- write one `inventory_events` row
- update `inventory_items.current_stock = quantity_after`
- update `inventory_items.current_price = approved price`
- update `inventory_items.updated_at`

All of that must happen in the same transaction.

For this phase:

- `event_type = "stock-in"`
- `quantity_delta = approved quantity`
- `source = "voice-confirmed"`
- `created_by = approved_by_actor_id`
- `reason = null`

### 7. Audit log contract should be explicit and minimal

Phase 5A should append one `audit_logs` row for each committed stock-in approval.

Use:

- `scope = "inventory"`
- `action = "inventory.stock_in_confirmed"`
- `actor_type = "owner"`
- `actor_id = approved_by_actor_id`
- `task_run_id = linked task_run_id`
- `target_type = "inventory_item"`
- `target_id = resolved item_id`

`metadata` should be a stable JSON object with at least:

```json
{
  "confirmation_id": "conf_123",
  "inventory_event_id": "inv_evt_123",
  "event_type": "stock-in",
  "item_id": "item_001",
  "item_name": "Apple",
  "quantity_delta": 3,
  "quantity_after": 8,
  "unit": "box",
  "price": 18.5,
  "source": "voice-confirmed"
}
```

This gives later UI and debugging work a stable base without overdesigning a generic audit taxonomy.

### 8. Approval remains all-or-nothing

The most important invariant in this phase is transactional honesty.

`POST /api/v1/confirmations/{id}/approve` must not produce partial truth.

So if any step fails after request validation:

- confirmation stays `pending`
- task run stays `awaiting-confirmation`
- no inventory item is partially created
- no inventory event is appended
- no audit log is appended
- no success runtime/system message is written

This is the key reason to keep the entire commit flow inside one service-level transaction.

### 9. Rejection behavior remains unchanged

Rejecting a pending confirmation should continue to:

- mark `confirmations.status = "rejected"`
- mark `task_runs.status = "rejected"`
- write a rejection message to the session ledger

It should still not touch inventory or audit truth in this phase.

## Architecture

### 1. New persistence models

Add durable ORM models and Alembic migration for:

- `InventoryItem`
- `InventoryEvent`
- `AuditLog`

The migration should align with the existing project docs for field names and basic indexes, while staying within the repo's current SQLAlchemy/Alembic style.

At minimum this phase needs indexes for:

- `inventory_items(shop_id, name)`
- `inventory_events(shop_id, item_id, created_at desc)`
- `audit_logs(shop_id, created_at desc)`

### 2. Inventory write service boundary

Add focused services under `backend/app/services` for:

- resolving or creating inventory items from approved fields
- appending a stock-in inventory event
- appending one audit log entry

These services should not know about FastAPI or HTTP responses.

They should operate on ORM/session inputs and raise narrow domain errors for:

- item not found in shop
- ambiguous item match
- inactive item
- unit mismatch
- invalid approved fields

### 3. Confirmation approval commit orchestrator

Add one orchestration service that owns the whole approval-backed stock-in commit.

It should do this in order:

1. load the confirmation and linked task run
2. verify the confirmation is still pending
3. verify the linked task run is still `awaiting-confirmation`
4. validate and normalize approved fields
5. approve the confirmation in-memory / within the same transaction
6. resolve or create the inventory item
7. append the stock-in event and update `current_stock`
8. append the audit log
9. complete the task run with a committed-truth result summary
10. write one runtime/system message describing the committed stock-in
11. commit the transaction

The route should delegate to this orchestrator rather than composing seven different service calls inline.

### 4. API impact

`POST /api/v1/confirmations/{confirmation_id}/approve`

External route shape remains the same:

- same path
- same mock owner auth
- same `fields` object in the request body

But the semantics change materially:

- success now means business truth was committed
- conflict or validation errors now include inventory-domain failures when relevant

Suggested additional error codes for this phase:

- `confirmation_fields_invalid`
- `inventory_item_not_found`
- `inventory_item_ambiguous`
- `inventory_item_inactive`
- `inventory_unit_mismatch`

`GET /api/v1/task-runs/{task_run_id}` remains the primary polling seam and does not need new fields for this phase.

### 5. Runtime and ledger behavior

Runtime routing still stops at pending confirmation for stock-in.

Only the approval route performs the truth write.

On successful approval, the session ledger should receive a visible runtime/system text message like:

- `Mock runtime: stock-in committed for Apple (+3 box). Current stock: 8 box.`

The exact wording can vary, but it should communicate committed truth rather than merely workflow completion.

## Error Handling

Phase 5A should preserve the existing confirmation-domain errors and add inventory-domain ones.

Rules:

- missing confirmation id -> `404 confirmation_not_found`
- already resolved confirmation -> `409 confirmation_not_pending`
- malformed or incomplete approved fields -> `422 confirmation_fields_invalid`
- unknown `item_id` for the shop -> `404 inventory_item_not_found`
- duplicate active name matches -> `409 inventory_item_ambiguous`
- inactive item target -> `409 inventory_item_inactive`
- unit mismatch on existing item -> `409 inventory_unit_mismatch`

For all of these cases, the confirmation should remain pending unless it was already resolved before the request started.

## Testing Strategy

Phase 5A should remain strictly test-first and add coverage at four layers:

1. Inventory service tests for:
   - create new item from approved fields
   - reuse existing item by `item_id`
   - reuse existing item by exact name match
   - fail on ambiguous name match
   - fail on unit mismatch
2. Commit orchestrator tests for:
   - approval writes confirmation, inventory event, stock projection, audit log, task completion, and runtime message
   - rejection path still performs no inventory write
   - transactional rollback leaves confirmation pending when an inner write fails
3. Confirmation API tests for:
   - approving a pending confirmation produces committed inventory truth
   - error responses for invalid fields, missing item, ambiguous item, and unit mismatch
4. Fresh full-suite verification for:
   - backend tests
   - mobile test shell
   - Docker compose config

## Acceptance Criteria

Phase 5A is complete when all of the following are true:

1. A pending `voice-stock-in` confirmation can be approved and produce one committed `inventory_events` row.
2. The approval transaction updates `inventory_items.current_stock` in the same transaction as the new event.
3. The approval transaction writes one `audit_logs` row with stable inventory metadata.
4. If the approved item does not yet exist, one new `inventory_items` row is created with the documented defaults.
5. If the approved item already exists and the unit matches, stock is incremented instead of creating a duplicate item.
6. If an existing-item match is ambiguous or the unit is incompatible, the route returns a domain error and leaves the confirmation pending.
7. On successful approval:
   - `confirmations.status = "approved"`
   - `task_runs.status = "completed"`
   - the session ledger contains a committed-truth runtime/system message
8. On rejection:
   - `confirmations.status = "rejected"`
   - `task_runs.status = "rejected"`
   - no inventory or audit write occurs
9. No alert maintenance, inventory query API, audit query API, session stream event, or WebSocket dependency is introduced.

## Out of Scope

This phase explicitly does not implement:

- `alerts`
- low-stock threshold evaluation
- inventory list/detail APIs
- audit log query APIs
- session stream events
- WebSocket delivery
- stock-out commits
- correction commits
- OCR-backed item extraction
- barcode matching
- fuzzy name matching
- unit conversion
- multi-shop or multi-owner authorization

## Follow-On Work

Once Phase 5A lands, the next clean slices are:

1. inventory read APIs and UI polling surfaces
2. low-stock alert derivation and maintenance
3. session stream events plus WebSocket fanout after truth writes
4. richer confirmation payloads that include known `item_id` selections and OCR/photo-assisted fields
