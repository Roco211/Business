# Phase 6B Dashboard and Low-Stock Alert Foundation Design

## Context

Phase 6A made committed inventory truth readable through:

- `GET /api/v1/inventory-items`
- `GET /api/v1/inventory-items/{item_id}`
- `GET /api/v1/audit-logs?scope=inventory`
- a minimally useful mobile `LedgerScreen`

That leaves the other major shell surface untouched:

- `DashboardScreen` still renders placeholder text
- there is still no `GET /api/v1/dashboard/summary`
- there is still no `GET /api/v1/alerts?type=low-stock`
- low-stock state is not persisted anywhere

So the next clean slice is to add durable low-stock alert truth and the smallest dashboard read-side that makes it visible.

## Goal

Build the minimum durable low-stock alert foundation plus dashboard reads so the app can show:

1. summary counts for the current shop
2. open low-stock alerts
3. pending confirmations on the dashboard

After this phase:

1. the backend persists low-stock alerts in an `alerts` table
2. approved stock-in commits refresh low-stock alert state for the affected item
3. the backend exposes:
   - `GET /api/v1/dashboard/summary`
   - `GET /api/v1/alerts?type=low-stock&limit=`
4. the mobile dashboard renders:
   - summary cards
   - low-stock alert list
   - pending confirmation list
5. websocket push, dashboard mutations, alert dismissal flows, and correction flows remain out of scope

## Options Considered

### Option A: Derive low-stock state entirely at read time

Pros:

- smallest short-term implementation
- no new persistence layer

Why not now:

- alert IDs and statuses would not exist
- summary counts and future event fanout would rely on duplicated ad hoc query logic
- it drifts from the existing project docs and DB schema, which already define `alerts`

### Option B: Add durable low-stock alerts plus minimal dashboard reads

Pros:

- matches the documented data model
- creates stable truth for both dashboard summary and alert list
- keeps scope narrow by only integrating the current stock-in write path

Tradeoff:

- requires a migration and one more write-side side effect

### Option C: Bundle dashboard reads, low-stock alerts, websocket pushes, and alert resolution UX

Why not now:

- mixes persistence, read-side projection, mobile rendering, and realtime fanout into one phase
- makes failures harder to localize

## Chosen Approach

Use Option B.

Phase 6B will:

- add a durable `alerts` table and model
- refresh low-stock alert state whenever a stock-in confirmation commit changes an inventory item
- add dashboard summary and low-stock alert read routes
- wire `DashboardScreen` to summary, alerts, and existing pending confirmations

Phase 6B will not:

- add websocket delivery
- add dashboard mutations
- add alert dismissal or snooze actions
- add manual correction flows

## Scope Decisions

### 1. Only low-stock alerts are in scope

The first alert surface should support one concrete documented type:

- `low-stock`

This phase should not introduce:

- expiry alerts
- failed-task alerts
- notification channels

### 2. Alert truth should be refreshed inside the stock commit transaction

The current inventory mutation path is owner approval of a pending stock-in confirmation.

That means Phase 6B should refresh alert truth inside the same transaction that already writes:

- `inventory_items`
- `inventory_events`
- `audit_logs`

Rules:

- if `low_stock_threshold` is `NULL`, any open low-stock alert for the item is resolved
- if `current_stock <= low_stock_threshold`, one open low-stock alert should exist
- if `current_stock > low_stock_threshold`, open low-stock alerts for the item should be resolved

This phase only needs to integrate that logic into the approved stock-in path.

### 3. Dashboard summary stays aggregate-only

`GET /api/v1/dashboard/summary` should return:

- `shop_id`
- `today_stock_in_count`
- `today_task_completed_count`
- `pending_confirmations_count`
- `open_low_stock_alert_count`
- `last_inventory_event_at`

It should not embed:

- alert rows
- confirmation rows
- audit history

Those stay on dedicated routes.

### 4. Alerts route stays narrow and read-only

`GET /api/v1/alerts` in this phase should support:

- `type=low-stock`
- optional `limit`

Rules:

- `type` defaults to `low-stock`
- any other type returns `422 unsupported_alert_type`
- only open alerts are returned
- results are newest-first by `created_at DESC`, then `alert_id DESC`

### 5. Dashboard mobile scope should stay lightweight

The mobile app already has a lightweight fetch client from Phase 6A.

So Phase 6B should add:

- `useDashboardSummaryQuery`
- `useLowStockAlertsQuery`
- `usePendingConfirmationsQuery`

and update `DashboardScreen` to consume them.

This phase should not introduce a new state-management or query dependency.

## Architecture

### Backend

Add:

- `Alert` ORM model
- Alembic migration for `alerts`
- `alerts` service for refresh and list operations
- `dashboard` service for aggregate summary reads
- read contracts and routes for dashboard summary and alerts

Integrate alert refresh into `commit_approved_stock_in_confirmation`.

### Mobile

Add dashboard-focused hooks and render:

- top-line summary metrics
- open low-stock alert items
- existing pending confirmations

The screen should show loading and error states without crashing.

## API Impact

### `GET /api/v1/dashboard/summary`

Response:

```json
{
  "data": {
    "shop_id": "shop_default",
    "today_stock_in_count": 0,
    "today_task_completed_count": 0,
    "pending_confirmations_count": 0,
    "open_low_stock_alert_count": 0,
    "last_inventory_event_at": null
  }
}
```

### `GET /api/v1/alerts?type=low-stock`

Suggested response item fields:

- `alert_id`
- `shop_id`
- `alert_type`
- `item_id`
- `item_name`
- `status`
- `stock`
- `threshold`
- `unit`
- `created_at`

## Error Handling

Phase 6B adds:

- `unsupported_alert_type`

Dashboard and alert fetch failures should surface as recoverable screen errors.

## Testing Strategy

Cover:

1. alert refresh service behavior for open/update/resolve transitions
2. dashboard summary aggregation
3. alerts route and dashboard route auth/validation behavior
4. approval path integration proving stock-in commits refresh low-stock alert state
5. `DashboardScreen` rendering summary, low-stock alerts, and pending confirmations

## Acceptance Criteria

Phase 6B is complete when:

1. the backend persists `alerts`
2. approved stock-in commits refresh low-stock alert truth
3. `GET /api/v1/alerts?type=low-stock` returns open alerts
4. `GET /api/v1/dashboard/summary` returns aggregate counts
5. `DashboardScreen` renders summary, low-stock alerts, and pending confirmations from real API hooks
6. verification passes across backend tests, mobile tests, and Docker compose config

## Out of Scope

- websocket alert pushes
- alert dismissal or resolution actions
- dashboard write actions
- inventory corrections
- stock-out flows
- multi-shop auth
