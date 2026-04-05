# Phase 9C Receipt Batch Stock-In Design

## Goal

Turn the current durable `receipt-ocr` capability into a real business flow:

- a `receipt-image` owner message still produces durable OCR truth
- the same task then pauses for owner confirmation
- owner approval atomically writes multiple inventory stock-in events, audit logs, and alert refreshes
- chat exposes an editable receipt confirmation card instead of forcing receipt handling back out into manual ledger correction

This phase should keep the existing MVP architecture intact:

- reuse `message -> task_run -> runtime -> confirmation -> inventory/audit/session_stream`
- keep OCR and recognition deterministic and mock-first
- avoid introducing a second receipt-only workflow engine
- keep writes atomic at the confirmation approval boundary

## Approaches Considered

### 1. Keep Receipt OCR Read-Only

Keep `receipt-image` as a completed `receipt-ocr` task and let owners manually recreate the extracted lines elsewhere.

Pros:

- smallest code change
- no new confirmation semantics

Cons:

- leaves the most important receipt workflow incomplete
- forces duplicate data entry after OCR
- weakens the value of durable OCR truth

### 2. Add A Separate Receipt Approval Subsystem

Create receipt-specific approval tables, APIs, and UI distinct from the existing confirmation flow.

Pros:

- can model receipt editing in a very specialized way
- leaves existing confirmation logic untouched

Cons:

- duplicates workflow state
- introduces a second write orchestration path
- increases long-term maintenance burden for little MVP benefit

### 3. Extend The Existing Confirmation Flow For Receipt Batches

Treat receipt processing as another `confirmation_type`, using durable OCR truth as the source for draft line items and committing all accepted lines when the owner approves.

Pros:

- reuses the proven task and confirmation lifecycle
- keeps all writes behind one approval boundary
- minimizes architectural sprawl

Cons:

- confirmation payloads become more polymorphic
- chat needs a second confirmation card type

## Chosen Approach

Use approach 3.

`receipt-image` will now become a two-stage flow:

1. runtime persists an `ocr_documents` record
2. runtime creates a pending confirmation with receipt line drafts
3. owner edits or accepts the line drafts in chat
4. approval atomically writes inventory truth for every accepted line

The task stays in the existing `task_runs` lifecycle by moving into `awaiting-confirmation` instead of completing immediately.

## Backend Design

### 1. Runtime Behavior

`receipt-image` inputs continue to route to task type `receipt-ocr`, but policy changes from `allow` to `require-confirmation`.

Runtime processing for `receipt-ocr` becomes:

- create durable `ocr_document`
- build pending confirmation fields from `ocr_document.extracted_fields.items`
- mark the task as `awaiting-confirmation`
- write a runtime/system message instructing the owner to confirm receipt line items

The receipt confirmation type will be:

- `receipt-stock-in-batch`

### 2. Confirmation Shape

Pending confirmation `fields` for receipt batches will contain:

- `summary`
- `ocr_document_id`
- `document_type`
- `provider_name`
- `total_amount`
- `low_confidence_fields`
- `draft_items`
- `required_item_fields`

Each `draft_items` entry will contain:

- `line_id`
- `item_id` nullable
- `item_name`
- `quantity`
- `unit`
- `price`

This keeps the confirmation contract generic while making the receipt UI deterministic.

### 3. Approval Contract

`POST /api/v1/confirmations/{confirmation_id}/approve` remains the single approval route.

The route will dispatch by `confirmation_type`:

- `low-confidence-recognition`
  - existing single stock-in commit path
- `receipt-stock-in-batch`
  - new batch stock-in commit path

Receipt approval payload shape inside `fields`:

```json
{
  "items": [
    {
      "line_id": "line_1",
      "item_id": null,
      "item_name": "Red Bull 250ml",
      "quantity": 3,
      "unit": "can",
      "price": 41.0
    }
  ]
}
```

The payload stays nested inside `fields` so the public route shape does not fork.

### 4. Batch Commit Semantics

Receipt approval commits all accepted line items atomically in one database transaction.

For each approved line:

- parse and validate line fields
- resolve or create the target inventory item with the existing stock-in item resolver
- append one `inventory_event`
- refresh low-stock alert projection for the item
- append one inventory audit log entry
- append `inventory.updated` and `alert.updated` session events

After all lines succeed:

- confirmation becomes `approved`
- task run becomes `completed`
- a runtime/system message summarizes how many lines were committed and the resulting totals

If any line fails validation or item resolution:

- the whole approval fails
- no inventory truth is written
- confirmation remains pending

### 5. Validation Rules

Receipt approval must reject:

- missing or empty `items`
- non-object line entries
- missing `item_name` when `item_id` is absent
- missing `unit`
- non-numeric `quantity` or `price`
- `quantity <= 0`
- `price < 0`
- unknown `item_id`
- unit mismatch against an existing item
- ambiguous `item_name`

This mirrors the single stock-in validation semantics instead of inventing a separate rule set.

### 6. Audit Semantics

Receipt commits should be distinguishable from voice/photo confirmation commits.

Each committed line will write an audit log action:

- `inventory.receipt_stock_in_confirmed`

Metadata will include:

- `confirmation_id`
- `ocr_document_id`
- `inventory_event_id`
- `line_id`
- `item_id`
- `item_name`
- `quantity_delta`
- `quantity_after`
- `unit`
- `price`
- `source`

### 7. Session Stream And Read Models

No new websocket event types are required.

The existing events remain sufficient:

- `confirmation.created`
- `confirmation.resolved`
- `inventory.updated`
- `alert.updated`
- `message.created`
- `task.updated`

Dashboard and ledger refresh behavior can continue to key off those event types.

## Mobile Design

### 1. Chat Confirmation Rendering

Chat will render confirmation cards by `confirmation_type`:

- `low-confidence-recognition` -> existing stock-in card
- `receipt-stock-in-batch` -> new receipt batch card

This avoids overloading the single-item card with receipt-specific form state.

### 2. Receipt Confirmation Card

The new receipt card will show:

- summary
- OCR document id
- total amount
- low-confidence fields when present
- editable line-item rows

Each row exposes editable:

- item name
- quantity
- unit
- price

The card submits the edited list as `fields.items`.

### 3. Mutation Contract

The current approval mutation becomes generic so it can submit either:

- single-item stock-in fields
- receipt batch `items`

This keeps one approval hook and one endpoint while still allowing specialized UIs.

## Out Of Scope

This phase still does not include:

- native camera or gallery integration
- OCR-specific websocket event types
- partial line acceptance with per-line skip flags
- supplier normalization, tax parsing, or receipt header modeling
- stock-out receipt semantics
- automatic reconciliation against existing purchase orders

## Acceptance Criteria

This phase is complete when all of the following are true:

- `receipt-image` runtime processing creates a durable `ocr_document`
- `receipt-image` runtime processing creates a pending `receipt-stock-in-batch` confirmation
- receipt tasks stop at `awaiting-confirmation`
- approving a receipt confirmation writes one inventory event per approved line in a single transaction
- approving a receipt confirmation writes matching audit logs and session stream updates
- rejecting a receipt confirmation leaves inventory truth untouched and rejects the task
- chat renders and submits an editable receipt confirmation card
- backend tests cover runtime, approval success, and approval validation failures
- mobile tests cover receipt confirmation rendering and approval submission
- docs no longer describe receipt inventory commit as deferred
