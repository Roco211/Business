# Phase 8B Chat Workgroup Interaction Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the mobile chat tab into the minimum real workgroup surface with durable messages, text send, inline confirmation actions, and realtime refresh.

**Architecture:** Keep the backend contract mostly unchanged and implement this slice primarily in the mobile app. Add focused chat hooks for message reads, message writes, and confirmation actions, then rebuild `ChatScreen` around a durable timeline plus inline stock-in confirmation cards that refresh from the shared session stream.

**Tech Stack:** TypeScript, Expo, React Native, Jest, Testing Library

---

### Task 1: Add chat message data hooks

**Files:**
- Create: `apps/mobile/src/features/chat/hooks/useSessionMessagesQuery.ts`
- Create: `apps/mobile/src/features/chat/hooks/useSendMessageMutation.ts`
- Modify: `apps/mobile/__tests__/ChatScreen.test.tsx`

- [ ] Write failing mobile tests that prove chat loads durable session messages and can submit a text message.
- [ ] Run `npm.cmd test -- --runInBand ChatScreen.test.tsx` in `apps/mobile` and observe failure.
- [ ] Implement the message query and text-send mutation using the existing session message APIs.
- [ ] Re-run `npm.cmd test -- --runInBand ChatScreen.test.tsx` until it passes.
- [ ] Commit with `feat: add chat message hooks`.

### Task 2: Add chat confirmation hooks and stock-in confirmation card UI

**Files:**
- Create: `apps/mobile/src/features/chat/hooks/useChatPendingConfirmationsQuery.ts`
- Create: `apps/mobile/src/features/chat/hooks/useApproveConfirmationMutation.ts`
- Create: `apps/mobile/src/features/chat/hooks/useRejectConfirmationMutation.ts`
- Create: `apps/mobile/src/features/chat/components/PendingStockInConfirmationCard.tsx`
- Modify: `apps/mobile/__tests__/ChatScreen.test.tsx`

- [ ] Write failing mobile tests that prove chat renders pending confirmations and supports approve plus reject actions with recoverable errors.
- [ ] Run `npm.cmd test -- --runInBand ChatScreen.test.tsx` in `apps/mobile` and observe failure.
- [ ] Implement the confirmation hooks and the focused stock-in confirmation card component.
- [ ] Re-run `npm.cmd test -- --runInBand ChatScreen.test.tsx` until it passes.
- [ ] Commit with `feat: add chat confirmation actions`.

### Task 3: Rebuild ChatScreen around the durable timeline and realtime refresh

**Files:**
- Modify: `apps/mobile/src/features/chat/screens/ChatScreen.tsx`
- Modify: `apps/mobile/__tests__/ChatScreen.test.tsx`

- [ ] Write failing screen tests for the real chat layout, inline confirmation placement, send error handling, and refresh on relevant session-stream events.
- [ ] Run `npm.cmd test -- --runInBand ChatScreen.test.tsx` in `apps/mobile` and observe failure.
- [ ] Implement the durable message timeline, text composer, inline confirmation rendering, and event-driven `refresh()` logic.
- [ ] Re-run `npm.cmd test -- --runInBand ChatScreen.test.tsx` until it passes.
- [ ] Commit with `feat: add workgroup chat interaction flow`.

### Task 4: Update implementation status docs and verify the phase

**Files:**
- Modify: `project_docs/11-realtime-contract-implementation-status.md`

- [ ] Update the realtime implementation status addendum so it reflects the new chat behavior.
- [ ] Run `npm.cmd test -- --runInBand` in `apps/mobile`.
- [ ] Run `python -m pytest backend/tests -q`.
- [ ] Run `docker compose -f infra/docker/docker-compose.yml --env-file .env.example config`.
- [ ] Run `git status --short --branch`.
- [ ] Commit docs with `docs: update chat realtime status`.
- [ ] Commit verification with `test: verify phase 8b chat interaction foundation`.
