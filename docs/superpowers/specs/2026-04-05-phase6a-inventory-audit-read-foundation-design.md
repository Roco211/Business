# Phase 6A Inventory and Audit Read Foundation Design

## Context

Phase 5A established real inventory truth behind confirmation approval:

- approving a pending stock-in confirmation can now create or reuse an `inventory_item`
- the backend appends an `inventory_event`
- `inventory_items.current_stock` is updated in the same transaction
- one `audit_log` row is written for the committed business action

That means the system finally has durable read-worthy truth for:

- inventory items
- inventory stock projections
- recent inventory audit activity

But the repo still has a major gap between truth and usability:

- there is no read-side backend API for `inventory_items`
- there is no read-side backend API for `audit_logs`
- `LedgerScreen` is still a shell and cannot display the truth that now exists

So the next clean slice is not alerts or realtime fanout yet. It is the minimum read-side foundation that makes the newly-written truth visible to both backend consumers and the mobile client.

## Goal

Build the smallest inventory and audit read-side foundation so committed truth can be queried through stable backend routes and rendered in the mobile ledger surface.

After this phase:

1. the backend exposes:
   - `GET /api/v1/inventory-items?query=&limit=`
   - `GET /api/v1/inventory-items/{item_id}`
   - `GET /api/v1/audit-logs?scope=inventory&limit=`
2. inventory item search and detail read from the durable Phase 5A tables
3. audit log listing returns newest-first inventory audit history
4. the mobile app gains a minimal shared API client and query hooks for ledger reads
5. `LedgerScreen` can render:
   - a searchable inventory list
   - recent inventory audit activity
6. alerts, dashboard summary, manual correction flows, session stream events, and WebSocket fanout remain out of scope

## Options Considered

### Option A: Backend-only read APIs

Deliver:

- inventory list/detail routes
- audit log list route
- tests only on the backend

Pros:

- smallest backend-only scope
- easiest to finish quickly

Why not now:

- the user-visible value remains hidden inside database rows and API tests
- `LedgerScreen` would still be a shell even though the project docs already position it as the ledger surface

### Option B: Backend read APIs plus minimal `LedgerScreen` consumption

Deliver:

- read-side backend contracts and services
- mobile shared API client
- two ledger query hooks
- `LedgerScreen` rendering inventory and recent audit activity

Pros:

- makes Phase 5A truth visible end-to-end
- stays focused on one mobile surface instead of broad app-wide UI work
- aligns directly with `project_docs/04-client-state-and-flows.md`, which already lists `useInventoryItemsQuery` and `useAuditLogsQuery`

Tradeoff:

- slightly larger scope than backend-only work

### Option C: Bundle ledger reads, dashboard summary, low-stock alerts, and correction entry

Deliver:

- ledger read APIs
- dashboard read APIs
- alert routes
- manual correction mutations

Why not now:

- mixes read-side foundation, derived alerts, and write-side correction behavior into one phase
- makes it harder to tell whether failures come from raw truth reads or derived projections

## Chosen Approach

Use Option B.

Phase 6A will turn the new inventory truth into the first real read surface and stop there.

That means:

- add backend inventory/audit read routes
- add minimal mobile read plumbing for `LedgerScreen`
- keep the scope strictly read-only on the new surface

This phase will not:

- add low-stock alert computation
- add dashboard summary APIs
- add manual correction writes
- add session stream events
- add WebSocket pushes
- add photo or OCR ledger entrypoints

## Scope Decisions

### 1. Inventory list route stays intentionally narrow

The first inventory read route should solve one concrete use case:

- find items in the current shop by name for ledger browsing and future correction targeting

So `GET /api/v1/inventory-items` should support:

- optional `query`
- optional `limit`

Rules:

- only active items are returned
- results are scoped to the single current shop
- query matching is name-based in this phase
- results are ordered by `updated_at DESC`, then `item_id DESC`

This phase should not add:

- category filters
- barcode search
- pagination cursors
- multi-shop visibility

### 2. Inventory detail route returns only the item, not joined history

`GET /api/v1/inventory-items/{item_id}` should return one item record.

It should not embed:

- inventory event history
- low-stock alert state
- related confirmations

Why:

- that would turn a simple read-side foundation into a composite projection phase
- recent history is already better represented by the audit log route in this slice

### 3. Audit log route stays inventory-scoped in this phase

The documented API already uses:

- `GET /api/v1/audit-logs?scope=inventory&limit=20`

Phase 6A should support exactly that shape.

Rules:

- `scope` defaults to `inventory`
- any non-`inventory` scope is rejected with validation-style error
- results are newest-first by `created_at DESC`, then `audit_log_id DESC`
- `limit` is capped at `50`

This keeps the route honest without pretending the repo already has generalized audit browsing requirements.

### 4. Mobile read layer should stay dependency-light

The mobile app currently has no shared API client, no React Query layer, and no established data fetching library.

So Phase 6A should not add a new client dependency just to read two endpoints.

Instead:

- add one lightweight fetch-based client
- add focused hooks for ledger reads
- keep cache behavior local to the screen and hooks

This is enough for the current MVP shell without locking the repo into a premature mobile data stack.

### 5. `LedgerScreen` should be informative, not complete

The first useful ledger surface only needs to answer:

- what inventory items exist right now
- what recent committed inventory actions happened

So `LedgerScreen` should render:

- a search input
- loading and error states
- an inventory item list with:
  - name
  - stock
  - unit
  - current price
- a recent audit activity list with:
  - action
  - item name
  - quantity change or resulting stock when available from metadata
  - created time

It should not add:

- correction sheets
- inline editing
- item picker sheets
- photo capture

### 6. Mobile base URL must be explicit

The app currently has no backend configuration.

Phase 6A should add one deterministic base URL strategy:

- use `EXPO_PUBLIC_API_BASE_URL` when present
- otherwise default to:
  - `http://10.0.2.2:8001` on Android
  - `http://127.0.0.1:8001` on non-Android Expo targets

This keeps local development workable without introducing a full environment system.

### 7. Auth remains the same mock owner contract

All new read routes should use the same owner bearer token contract already used elsewhere:

- `Authorization: Bearer mock_owner_token`

Phase 6A should not introduce:

- anonymous read access
- per-screen guest fallbacks
- token refresh behavior

## Architecture

### 1. Backend contracts and routes

Add backend contracts for:

- inventory item list/detail response data
- audit log list response data

Add backend routes under `backend/app/api/routes`:

- `inventory_items.py`
- `audit_logs.py`

Responsibilities:

- auth guard
- query parameter validation
- mapping ORM/service results into response contracts
- stable error codes

### 2. Backend read services

Add focused services for:

- listing inventory items
- loading one inventory item by id
- listing audit logs by scope

These services should remain read-only and not know about FastAPI.

They should accept a DB session and explicit filter arguments, then return typed service results or raise domain lookup/validation errors.

### 3. Mobile shared API client

Add one small mobile API module responsible for:

- base URL resolution
- auth header injection using the current mock owner token
- JSON fetch helpers
- stable error objects for non-2xx responses

Keep it focused enough that future screens can reuse it, but avoid inventing a generalized SDK.

### 4. Mobile ledger hooks

Add hooks under the ledger feature for:

- `useInventoryItemsQuery(searchText)`
- `useAuditLogsQuery()`

Responsibilities:

- manage loading state
- execute fetches
- surface typed data
- support explicit refresh

`useInventoryItemsQuery` should use a deferred search value so typing into the ledger search input does not immediately thrash network requests.

### 5. `LedgerScreen` rendering boundary

`LedgerScreen` should remain a presentation-focused consumer of the hooks.

It should:

- own the search text UI state
- call the two hooks
- show loading, empty, and error states
- render lists

It should not perform raw fetches inline.

## API and Contract Impact

### 1. Inventory list

Add:

- `GET /api/v1/inventory-items?query=<optional>&limit=<optional>`

Suggested response item fields:

- `item_id`
- `shop_id`
- `sku`
- `name`
- `category`
- `barcode`
- `default_unit`
- `current_stock`
- `current_price`
- `low_stock_threshold`
- `image_media_id`
- `is_active`
- `created_at`
- `updated_at`

### 2. Inventory detail

Add:

- `GET /api/v1/inventory-items/{item_id}`

Errors:

- `401 unauthorized`
- `404 inventory_item_not_found`

### 3. Audit log list

Add:

- `GET /api/v1/audit-logs?scope=inventory&limit=20`

Suggested response item fields:

- `audit_log_id`
- `shop_id`
- `scope`
- `action`
- `actor_type`
- `actor_id`
- `task_run_id`
- `target_type`
- `target_id`
- `metadata`
- `created_at`

Errors:

- `401 unauthorized`
- `422 unsupported_audit_scope`

## Error Handling

Phase 6A should add these new stable error codes:

- `inventory_item_not_found`
- `unsupported_audit_scope`

Mobile read behavior should treat backend read failures as recoverable UI errors:

- show an inline error message
- keep the screen mounted
- allow retry via pull-to-refresh or re-open

## Testing Strategy

Phase 6A should stay test-first and cover both backend and mobile:

1. Backend service tests for:
   - inventory list ordering and search filtering
   - inventory detail lookup
   - audit log ordering and scope validation
2. Backend API tests for:
   - inventory list route
   - inventory detail route
   - audit log list route
   - auth and not-found behavior
3. Mobile hook or screen tests for:
   - `LedgerScreen` renders loaded inventory items and audit activity
   - `LedgerScreen` shows loading and error states
   - search input re-queries inventory using the hook path
4. Fresh full-suite verification for:
   - backend tests
   - mobile tests
   - Docker compose config

## Acceptance Criteria

Phase 6A is complete when all of the following are true:

1. The backend can list active inventory items through `GET /api/v1/inventory-items`.
2. The backend can return one inventory item through `GET /api/v1/inventory-items/{item_id}`.
3. The backend can list recent inventory audit logs through `GET /api/v1/audit-logs?scope=inventory`.
4. Inventory list search filters by item name within the default shop.
5. Audit log results are newest-first and expose the stored metadata.
6. `LedgerScreen` can fetch and render inventory items from the backend.
7. `LedgerScreen` can fetch and render recent audit activity from the backend.
8. `LedgerScreen` surfaces loading and error states without crashing.
9. No alert routes, dashboard summary routes, manual correction flows, session stream events, or WebSocket dependencies are introduced.

## Out of Scope

This phase explicitly does not implement:

- low-stock alerts
- dashboard summary data
- manual correction mutation routes
- correction sheet UI
- item picker UI
- barcode search
- fuzzy search
- inventory event history routes
- session stream events
- WebSocket delivery
- multi-shop auth

## Follow-On Work

Once Phase 6A lands, the next clean slices are:

1. low-stock alert derivation and dashboard summary reads
2. manual correction write flows on top of the new ledger reads
3. session stream events and WebSocket fanout after read/write surfaces are stable
