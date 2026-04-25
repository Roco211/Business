# Phase I Command Center UI Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 H5 首页落地 AI-native Command Center，并同步修复当前 Dashboard 布局错位/溢出问题。

**Architecture:** 第一批不新增复杂后端模型，复用现有 `/api/v2/chat`、`/api/v2/sales/order-drafts/from-text`、`/api/v2/confirmations`、`/api/v2/pc-dashboard/overview`。前端首页新增 Command Center 组件，输入自然语言后根据意图调用查询聊天或销售草稿接口；高风险写入仍生成 confirmation，不直接落账。

**Tech Stack:** Vite + React + TypeScript, FastAPI V2 API, existing confirmation-first backend.

---

### Task 1: Add Command Center API/client support

**Files:**
- Reuse existing: `apps/h5/src/api.ts`
- Reuse existing: `apps/h5/src/types.ts`

- [x] Confirmed existing `api.chat` returns `reply`, `intent`, `confirmation_id`, `session_id` fields used by the dashboard.
- [x] Kept existing `api.chat` and `api.createSalesOrderDraft` contracts; no backend mutation from dashboard except confirmation draft creation.
- [x] Ran `npm run build` from `apps/h5` after UI integration.

### Task 2: Add Dashboard AI Command Center

**Files:**
- Modify: `apps/h5/src/App.tsx`

- [x] Pass `auth` and `onChanged` into `Dashboard`.
- [x] Add `AiCommandCenter` component above KPI cards.
- [x] Support quick commands:
  - 今天卖了多少钱？
  - 哪些商品快没货了？
  - 帮我看看今天要补什么货
  - 卖出1把电动螺丝刀，单价99，客户老王
- [x] For “卖出/销售/开单” style commands call `createSalesOrderDraft` and show pending confirmation + CTA to task center.
- [x] For query commands call `chat` and show AI employee、intent、reply、真实后端返回。
- [x] Do not fake order/customer/finance data.

### Task 3: Fix layout misalignment and responsive overflow

**Files:**
- Modify: `apps/h5/src/styles.css`

- [x] Add `min-width:0` to flex/grid children likely to overflow.
- [x] Make top bar wrap safely on medium widths.
- [x] Replace duplicated dashboard grid with dedicated `.operations-grid`.
- [x] Make employee grid auto-fit rather than fixed cramped columns.
- [x] Add Command Center styling using same light/purple dashboard prototype style.
- [x] Normalize table selector to current markup (`.table-wrap table`) so tables render consistently.

### Task 4: Verify and commit

**Files:**
- Modified app/doc files only.

- [x] Run `npm run build` in `apps/h5`.
- [x] Browser smoke on `http://127.0.0.1:8082/` or 8001 if available: login, dashboard visible, command center visible, no obvious overlap.
- [x] Check browser console has zero JS errors.
- [x] Run `git diff --check`.
- [x] Stage only related files, not `dashboard.jpg`.
- [x] Commit and push.
