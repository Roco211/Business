# Phase 10A Ledger Stock-Out Design

## Goal

Add the missing manual `stock-out` write path so the MVP inventory truth supports all three essential owner operations:

- stock-in
- stock-out
- correction

This phase focuses on the ledger-driven path, not runtime language understanding. Owners should be able to reduce inventory directly from `LedgerScreen`, with the same durability guarantees already used by correction and approved stock-in flows.

## Approaches Considered

### 1. Add Runtime Stock-Out First

Teach text and voice routing to classify and confirm stock-out requests before adding a direct ledger write route.

Pros:

- keeps the AI-first interaction model front and center

Cons:

- introduces NLP ambiguity before the stock-out truth model is proven
- couples multiple problems: classification, confirmation UX, and inventory write semantics

### 2. Add Manual Ledger Stock-Out First

Add a direct `POST /api/v1/inventory-events/stock-out` route and a small Ledger UI so stock-out truth exists before runtime starts producing it.

Pros:

- smallest useful slice
- reuses the existing inventory, alert, audit, and realtime plumbing
- creates a stable backend primitive for later runtime-driven stock-out flows

Cons:

- less flashy than chat-driven stock-out

### 3. Fold Stock-Out Into Correction Only

Ask owners to use corrections whenever stock leaves inventory.

Pros:

- no new route or UI

Cons:

- loses semantic meaning between actual stock-out and recount
- weakens audit quality
- does not match the documented event model that already reserves `stock-out`

## Chosen Approach

Use approach 2.

This phase introduces a dedicated manual stock-out path in ledger while preserving the current runtime scope. That gives the system a proper `stock-out` truth model now, and later runtime phases can target that model instead of inventing it on the fly.

## Backend Design

### 1. API Contract

Add:

- `POST /api/v1/inventory-events/stock-out`

Request body:

```json
{
  "item_id": "item_001",
  "expected_quantity": 6,
  "stock_out_quantity": 2,
  "reason": "Walk-in sale"
}
```

Response body:

```json
{
  "data": {
    "stock_out_event_id": "inv_evt_123",
    "item_id": "item_001",
    "new_quantity": 4
  }
}
```

### 2. Validation Rules

The stock-out route must reject:

- unknown item
- inactive item
- empty reason
- `stock_out_quantity <= 0`
- `stock_out_quantity > current_stock`
- stale `expected_quantity`

These use the same conflict-first pattern as correction:

- `404 item_not_found`
- `409 inventory_conflict`
- `422 validation_error`

### 3. Inventory Truth

Add a dedicated `append_stock_out_event()` helper that:

- writes one `inventory_events` row with `event_type = stock-out`
- stores `quantity_delta` as a negative number
- updates `inventory_items.current_stock`
- keeps `current_price` unchanged

### 4. Audit And Realtime

Stock-out writes should behave like other durable inventory changes:

- refresh low-stock alert projection
- append `inventory.updated`
- append `alert.updated`
- append one audit log with action:
  - `inventory.stock_out_submitted`

Audit metadata should include:

- `inventory_event_id`
- `event_type`
- `item_id`
- `item_name`
- `previous_quantity`
- `quantity_delta`
- `quantity_after`
- `unit`
- `reason`
- `source`

## Mobile Design

### 1. Ledger Item Actions

Each ledger inventory row will expose two owner actions:

- `Correct <item>`
- `Stock out <item>`

### 2. Stock-Out Form

Selecting stock-out shows a simple inline form with:

- stock-out quantity
- stock-out reason

On success:

- clear the form
- refresh inventory and audit activity

On failure:

- keep the form open
- show the recoverable API error

### 3. Realtime Refresh

`LedgerScreen` already refreshes on `inventory.updated` and `confirmation.resolved`. No new websocket protocol is needed because manual stock-out writes will emit the existing inventory and alert events.

## Out Of Scope

This phase does not include:

- runtime/chat-driven stock-out understanding
- stock-out confirmations
- batch stock-out
- return/refund semantics
- negative inventory support

## Acceptance Criteria

This phase is complete when all of the following are true:

- the backend exposes `POST /api/v1/inventory-events/stock-out`
- successful stock-out writes one `stock-out` inventory event
- successful stock-out refreshes low-stock alerts and realtime projections
- successful stock-out writes an `inventory.stock_out_submitted` audit log
- stock-out rejects stale snapshots and insufficient stock
- `LedgerScreen` exposes a stock-out action and form
- mobile tests cover successful stock-out submission and failure handling
- backend tests cover success, stale snapshot conflict, and insufficient-stock validation
