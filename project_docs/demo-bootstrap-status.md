# Demo Bootstrap Tooling Status

## Purpose

The MVP now includes a repeatable demo bootstrap entrypoint at `backend/scripts/bootstrap_demo_state.py`.
It resets the mutable state for the default demo shop/session and reseeds a representative operator-facing state using the real domain services.

## What It Creates

Running the bootstrap tool recreates a stable default demo state with:

- three active inventory items:
  - `Cola`
  - `Red Bull 250ml`
  - `Coca Cola 500ml`
- a completed stock-in history for chat-driven owner confirmation
- a completed receipt batch stock-in history
- one open low-stock alert on `Cola`
- one pending `stock-out` confirmation
- one pending `receipt-stock-in-batch` confirmation
- a populated chat timeline with owner messages and runtime system replies

## Why It Exists

This tooling makes the current MVP easier to demo and verify because the default session can be restored to a known-good state without manually replaying every flow.
It is intended for local demos, QA resets, and onboarding walkthroughs of the current mock-first product slice.

## Usage

1. Point `DATABASE_URL` at a migrated database.
2. Run `python backend/scripts/bootstrap_demo_state.py`.
3. Use the printed JSON summary to confirm the resulting demo state.

The tool only resets mutable records for the default demo shop/session.
It preserves the default shop/session identities while rebuilding their inventory, alerts, confirmations, tasks, messages, and session stream history.
