# Phase 12C Mobile Demo Reset Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an in-app demo reset action on Dashboard and refresh the mounted mobile tabs after the reset succeeds.

**Architecture:** Add one mobile mutation hook for the Phase 12B demo bootstrap API, extend the shared session context with a local reset version signal, and make Dashboard, Chat, and Ledger rerun their existing reads when that signal changes.

**Tech Stack:** React Native, TypeScript, React hooks, Jest, Testing Library

---

## File Structure

- Create:
  - `apps/mobile/src/features/dashboard/hooks/useDemoBootstrapMutation.ts`
- Modify:
  - `apps/mobile/src/shared/session/SessionStreamProvider.tsx`
  - `apps/mobile/src/features/dashboard/screens/DashboardScreen.tsx`
  - `apps/mobile/src/features/chat/screens/ChatScreen.tsx`
  - `apps/mobile/src/features/ledger/screens/LedgerScreen.tsx`
  - `apps/mobile/__tests__/DashboardScreen.test.tsx`
  - `apps/mobile/__tests__/DashboardRealtime.test.tsx`
  - `apps/mobile/__tests__/ChatScreen.test.tsx`
  - `apps/mobile/__tests__/LedgerScreen.test.tsx`

### Task 1: Write Red Tests For Mobile Demo Reset

- [ ] Add a failing dashboard test that verifies pressing the reset control:
  - posts to `/api/v1/system/demo/bootstrap`
  - shows a submitting state
  - refreshes dashboard reads after success
- [ ] Add failing chat and ledger tests that verify mounted tabs refresh when the shared reset version changes.
- [ ] Run `npm.cmd test -- --runInBand DashboardScreen.test.tsx DashboardRealtime.test.tsx ChatScreen.test.tsx LedgerScreen.test.tsx` and confirm the new assertions fail first.

### Task 2: Add The Mutation Hook And Shared Reset Signal

- [ ] Create `apps/mobile/src/features/dashboard/hooks/useDemoBootstrapMutation.ts` to call the demo bootstrap API and expose `isSubmitting`, `error`, `successMessage`, and `runDemoBootstrap`.
- [ ] Extend `apps/mobile/src/shared/session/SessionStreamProvider.tsx` with:
  - `dataResetVersion`
  - `notifyDemoDataReset()`
- [ ] Keep the existing session bootstrap and websocket behavior intact.

### Task 3: Wire Dashboard, Chat, And Ledger Refresh

- [ ] Update `apps/mobile/src/features/dashboard/screens/DashboardScreen.tsx` to:
  - render a reset button
  - call the mutation hook
  - trigger `notifyDemoDataReset()` after success
  - refresh summary/alerts/pending confirmations on local reset changes
- [ ] Update `apps/mobile/src/features/chat/screens/ChatScreen.tsx` and `apps/mobile/src/features/ledger/screens/LedgerScreen.tsx` so they rerun their current `refresh()` paths when `dataResetVersion` changes.
- [ ] Re-run the targeted mobile tests until they pass.

### Task 4: Final Verification

- [ ] Run:
  - `npm.cmd test -- --runInBand`
  - `$env:PYTHONPATH='backend'; python -m pytest backend/tests -q`
  - `docker compose -f infra/docker/docker-compose.yml --env-file .env.example config`
- [ ] Commit the mobile demo reset slice.
