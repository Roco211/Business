# Mobile Trial Shell Manual Checklist (Android + Expo)

## Scope
Phase 17B trial-shell manual verification for:
- Login
- Dashboard
- Workbench
- Ledger
- Debug tools

## Environment Setup
- [ ] Android emulator or device is available (recommended Android 12+).
- [ ] In `apps/mobile`, run `npm install`.
- [ ] Start Expo with `npx expo start --android`.
- [ ] Confirm the app launches to login without crash/red screen.

## 1. Login Validation
- [ ] Submit valid credentials and enter the 3-tab shell (首页 / 工作台 / 台账).
- [ ] Login button loading and disabled state are correct while submitting.
- [ ] Login failure shows friendly copy and does not expose test-backend endpoints.
- [ ] Record result: pass/fail + screenshot.

## 2. Dashboard Validation
- [ ] Header, health section, and empty/error copy are readable and business-facing.
- [ ] Low-stock and pending-confirmation cards render correctly in both data and empty states.
- [ ] Dashboard action to go to workbench navigates correctly.
- [ ] No raw `Loading...` placeholder or backend error leak in user-facing copy.
- [ ] Record result: pass/fail + screenshot.

## 3. Workbench Validation
- [ ] Timeline renders messages and confirmation cards.
- [ ] Text send flow works end-to-end: input -> sending -> refreshed result.
- [ ] Default guided entry dock shows only voice, photo, and receipt actions.
- [ ] Do **not** fail trial QA for missing stock-out in default workbench guided entry; stock-out legacy demo lives under debug disclosure only.
- [ ] Connection hint copy is readable and updates across connected/reconnecting/degraded states.
- [ ] Record result: pass/fail + screenshot.

## 4. Ledger Validation
- [ ] Ledger title and key sections are readable Chinese: 搜索与筛选 / 操作面板 / 活动时间线.
- [ ] Search input filters inventory cards as expected.
- [ ] Both ledger card actions work: 库存修正 and 出库登记.
- [ ] Loading, empty, and error states are readable and do not leak test-backend internals.
- [ ] Activity timeline displays recent inventory-related records.
- [ ] Record result: pass/fail + screenshot.

## 5. Debug Tool Validation (Secondary But Reachable)
- [ ] Dashboard and workbench debug disclosure is collapsed by default.
- [ ] Debug disclosure remains easy to open/close, but is visually secondary to primary workflow controls.
- [ ] Debug actions (for example demo reset, legacy media demos) work after expansion and show outcome feedback.
- [ ] Debug tools do not block primary trial-shell paths.
- [ ] Record result: pass/fail + screenshot.

## 6. Trial-Shell Exit Criteria
- [ ] All five areas (Login / Dashboard / Workbench / Ledger / Debug tools) pass.
- [ ] No P0/P1 crash, white-screen, or flow-blocking defect.
- [ ] No unreadable copy, no mojibake, and no test-backend raw error copy in user-facing UI.
- [ ] Validation summary and issue list are synced to the current trial run record.
