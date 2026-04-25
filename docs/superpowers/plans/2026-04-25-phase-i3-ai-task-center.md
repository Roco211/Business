# Phase I3 AI Task Center State Flow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 H5 的“AI待确认任务”从原始 JSON 列表升级为 AI-native 任务流视图，让用户看到 AI 员工处理阶段、证据、风险、确认边界和执行动作。

**Architecture:** 第一批不新增后端状态机表，复用现有 pending confirmations 作为安全边界，在前端派生可解释任务阶段：discovered -> analyzed -> draft_created -> awaiting_confirmation -> approve/reject。审批仍调用现有 `/api/v2/confirmations/{id}/approve|reject`，不绕过 confirmation-first。

**Tech Stack:** Vite + React + TypeScript, existing FastAPI V2 confirmations.

---

### Task 1: Model UI-level task stages

**Files:**
- Modify: `apps/h5/src/App.tsx`

- [x] Add helper functions to classify confirmation type into AI employee, readable title, business impact, risk label, and stage labels.
- [x] Add safe draft payload summary rendering instead of raw JSON-first display.
- [x] Keep raw payload available as collapsible/details content for debugging/audit transparency.

### Task 2: Replace TasksPage with task-flow UI

**Files:**
- Modify: `apps/h5/src/App.tsx`

- [x] Add hero summary for pending count and confirmation-first safety boundary.
- [x] Render each pending confirmation as a task flow card.
- [x] Show stage rail: 已发现 -> 已分析 -> 已生成草稿 -> 等待老板确认.
- [x] Show AI employee, confidence/risk/evidence, created time, task id.
- [x] Keep approve and reject actions wired to existing API.

### Task 3: Add styling

**Files:**
- Modify: `apps/h5/src/styles.css`

- [x] Add task center grid/card styles aligned to current white/purple dashboard design.
- [x] Ensure mobile/medium widths do not overflow.
- [x] Avoid emoji icons; use text/line-style indicators.

### Task 4: Verify and commit

- [x] Run `npm run build` in `apps/h5`.
- [x] Browser smoke: create one sales draft from Command Center or AI page, open task center, verify stage rail and actions visible.
- [x] Check browser console has zero JS errors.
- [x] Run `git diff --check`.
- [x] Stage only related files, not `dashboard.jpg`.
- [x] Commit and push.
