# Phase 7A Ledger Correction Foundation Design

## Context

After Phase 6B, the project now has:

- durable inventory truth
- durable audit truth
- durable low-stock alert truth
- readable dashboard and ledger surfaces

But the ledger is still only half-real.

Users can:

- browse inventory items
- browse audit history

Users still cannot:

- submit a manual correction when physical count does not match projected stock

That leaves an important gap in the documented product shape:

- `LedgerScreen` is supposed to support correction
- `POST /api/v1/inventory-events/corrections` already exists in the API docs
- alerts are documented as a derived state table maintained after inventory writes

So the next clean slice is to add the first manual correction write flow and make sure it updates inventory, audit, and low-stock alert truth in one transaction.

## Goal

Build the minimum end-to-end correction foundation so an owner can correct one inventory item's quantity from the ledger.

After this phase:

1. the backend exposes `POST /api/v1/inventory-events/corrections`
2. correction writes:
   - append an `inventory_event` with `event_type="correction"`
   - update `inventory_items.current_stock`
   - append an `audit_log`
   - refresh the derived low-stock alert state
3. the mobile `LedgerScreen` can submit a correction for one selected item
4. inventory, audit, and alert reads refresh after correction success
5. stock-out flows, websocket fanout, and session-stream events remain out of scope

## Options Considered

### Option A: Add backend correction route only

Pros:

- smallest backend slice

Why not now:

- the ledger would still be read-only from the user’s perspective
- the main user-facing benefit would stay hidden behind API tests

### Option B: Add backend correction route plus minimal ledger submission UI

Pros:

- completes the first actionable ledger workflow
- reuses Phase 6A inventory/audit reads and Phase 6B alert refresh logic
- keeps scope focused on one concrete write path

Tradeoff:

- slightly larger than backend-only work

### Option C: Bundle correction, stock-out, and websocket updates

Why not now:

- mixes separate write semantics with realtime delivery
- increases failure surface without improving iteration speed

## Chosen Approach

Use Option B.

Phase 7A will:

- add a correction command service
- add a correction API route
- add a small ledger mutation hook and form
- refresh inventory, audit, and alert reads after success

Phase 7A will not:

- add stock-out mutations
- add websocket/session stream push
- add optimistic concurrency tokens beyond current last-write-wins semantics
- add bulk correction UI

## Scope Decisions

### 1. Correction means “set quantity”, not “apply delta”

The documented API already uses:

- `corrected_quantity`

So this phase should keep the owner interaction simple:

- choose item
- enter corrected quantity
- enter reason
- submit

The backend computes:

- `quantity_delta = corrected_quantity - current_stock`
- `quantity_after = corrected_quantity`

To avoid stale-ledger overwrites, the request should also carry:

- `expected_quantity`

and the backend should return `409 inventory_conflict` when the current stock no longer matches that snapshot.

### 2. Reason is required

Corrections directly modify inventory truth.

So the backend should require:

- non-empty `reason`

This keeps the audit trail meaningful and matches the docs’ expectation that correction reason cannot be omitted.

### 3. Correction should preserve unit and current price

Correction is adjusting count, not changing the merchandising definition.

So the correction event should:

- reuse `item.default_unit`
- leave `item.current_price` unchanged
- write `price=item.current_price` on the event when available

### 4. Alert refresh must happen inside the same transaction

Alerts are already treated as derived state maintained after inventory writes.

So the correction flow should refresh low-stock alert truth using the same rules as stock-in:

- open when `current_stock <= low_stock_threshold`
- resolve when `current_stock > low_stock_threshold`
- resolve when threshold is `NULL`

### 5. Audit should be explicit about correction semantics

This phase should add a dedicated inventory audit action:

- `inventory.correction_submitted`

Metadata should include at least:

- `item_id`
- `item_name`
- `previous_quantity`
- `corrected_quantity`
- `quantity_delta`
- `reason`

### 6. Ledger UI should stay minimal

The first useful correction UI only needs:

- item list already on screen
- a way to pick one item for correction
- inputs for corrected quantity and reason
- submit button
- loading/error/success feedback

This phase should not add:

- modal libraries
- swipe actions
- bulk editing
- undo

## Architecture

### Backend

Add:

- correction request/response contracts
- a correction command service that owns validation and writes
- a route under `inventory-events`

The service should:

- load the item
- validate quantity and reason
- append one `correction` inventory event
- update `inventory_items.current_stock`
- append audit log
- refresh alert truth
- commit atomically

### Mobile

Add:

- `useCreateCorrectionMutation`
- minimal correction state in `LedgerScreen`

After success, the screen should re-fetch:

- inventory items
- audit logs

Alerts and dashboard do not need live refresh within the same screen in this phase.

## API Impact

### `POST /api/v1/inventory-events/corrections`

Request:

```json
{
  "item_id": "item_001",
  "expected_quantity": 5,
  "corrected_quantity": 3,
  "reason": "Physical count differs from projected inventory"
}
```

Response:

```json
{
  "data": {
    "correction_event_id": "inv_evt_001",
    "item_id": "item_001",
    "new_quantity": 3
  }
}
```

Errors:

- `401 unauthorized`
- `404 item_not_found`
- `409 inventory_conflict`
- `422 validation_error`

## Error Handling

Phase 7A should add stable error codes for:

- `item_not_found`
- `inventory_conflict`

Validation should reject:

- negative corrected quantity
- empty reason

## Testing Strategy

Cover:

1. correction service validation and write behavior
2. alert refresh integration after correction
3. correction API success and failure behavior
4. `LedgerScreen` correction submission and post-success refresh

## Acceptance Criteria

Phase 7A is complete when:

1. owners can submit `POST /api/v1/inventory-events/corrections`
2. correction writes a `correction` inventory event
3. item stock is updated to the corrected quantity
4. an audit log row is written
5. low-stock alert truth is refreshed
6. `LedgerScreen` can submit a correction and refresh its lists
7. verification passes across backend tests, mobile tests, and Docker compose config

## Out of Scope

- stock-out write flow
- websocket/session stream events
- optimistic locking version numbers
- correction approval workflow
- bulk corrections
