# Phase 12C Mobile Demo Reset Design

## Goal

Expose the new demo bootstrap API inside the mobile app so developers and QA can reset the MVP back to a known-good showcase state without leaving the app.

## Why This Matters

Phase 12A added a repeatable demo bootstrap service and script.
Phase 12B added an authenticated backend API wrapper.
The remaining gap is that the mobile app still has no first-class way to trigger that reset during demos or manual testing.

Without an in-app entry point:

- developers must jump back to shell or API tooling
- dashboards can drift into half-demo, half-manual-test states
- tabbed screens may keep stale data in memory after a reset

## Approaches Considered

### 1. Add Only A Dashboard Button

Pros:

- smallest UI change

Cons:

- other mounted tabs may keep stale data until navigation or manual actions refresh them

### 2. Add A Dashboard Button Plus App-Local Reset Broadcast

Pros:

- still small
- keeps one visible trigger surface
- refreshes Dashboard, Chat, and Ledger together after reset

Cons:

- requires a small extension to the shared session context

### 3. Build A Separate Debug Screen

Pros:

- room for more tooling later

Cons:

- overkill for the current need
- adds navigation complexity without delivering more value now

## Chosen Approach

Use approach 2.

This phase should:

- add a mobile mutation hook for `POST /api/v1/system/demo/bootstrap`
- place a simple reset control on Dashboard
- extend `SessionStreamProvider` with a local `dataResetVersion` signal
- make Dashboard, Chat, and Ledger refresh their existing queries when that signal changes

## Design

### 1. Keep Dashboard As The Trigger Surface

The reset action should live on Dashboard because that is already the high-level operational overview screen and the most natural place for a demo/QA control.

The UI should stay explicit and low ceremony:

- one button
- temporary submitting state
- short success or error message

### 2. Reuse The Existing Backend Contract

The mobile layer should not create a new reset-specific backend abstraction.
It should call the Phase 12B endpoint directly through the shared API client and consume the returned summary.

### 3. Add A Local Refresh Signal To Shared Session Context

Resetting the demo state rebuilds data behind the same `session_id`.
Because the tab screens may stay mounted, relying on remount behavior is not enough.

`SessionStreamProvider` should therefore expose:

- `dataResetVersion`
- a function to bump it after a successful demo reset

Dashboard, Chat, and Ledger can then reuse their existing `refresh()` functions whenever the reset version changes.

### 4. Keep Scope Narrow

This phase is not a full debug console.
No new navigation surface, no extra settings persistence, and no secondary admin flows should be added.

## Acceptance Criteria

This phase is complete when:

- Dashboard can trigger demo reset through the mobile app
- the action shows loading and success/error feedback
- Dashboard, Chat, and Ledger refresh after a successful reset even if tabs were already mounted
- mobile tests cover the reset flow and refresh propagation
