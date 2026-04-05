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

### Script Entry Point

1. Point `DATABASE_URL` at a migrated database.
2. Run `python backend/scripts/bootstrap_demo_state.py`.
3. Use the printed JSON summary to confirm the resulting demo state.

### API Entry Point

For app-adjacent tooling and QA workflows, the backend also exposes:

- `POST /api/v1/system/demo/bootstrap`

Current access control matches the rest of the mock owner surface:

- `Authorization: Bearer mock_owner_token`

The API returns the same stable bootstrap summary as the script so callers can verify the resulting demo state without reading the database directly.

The tool only resets mutable records for the default demo shop/session.
It preserves the default shop/session identities while rebuilding their inventory, alerts, confirmations, tasks, messages, and session stream history.

## Recommended Post-Startup Verification

After the local stack is running, the preferred verification path is now:

```powershell
python backend/scripts/run_local_demo_smoke.py
```

That smoke runner:

- checks `GET /health`
- calls `POST /api/v1/system/demo/bootstrap`
- validates session bootstrap, dashboard summary, low-stock alerts, pending confirmations, messages, and replay events
- prints a compact JSON summary of the verified local demo state

This gives developers and QA one repeatable proof that the running local stack matches the expected MVP demo shape before they open the mobile app or start manual walkthroughs.
