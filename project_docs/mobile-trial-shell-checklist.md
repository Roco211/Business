# Mobile Trial Shell Manual Checklist (Android + Expo)

## Scope
Phase 17B trial-shell manual verification for:
- Login
- Dashboard
- Workbench
- Ledger
- Debug tools

## Environment Setup
- [ ] Android device or emulator is available. Real device + Expo Go is preferred.
- [x] In `apps/mobile`, dependencies are installed.
- [x] Expo is running on the LAN host for the current workspace.
- [x] Backend health is reachable from the same LAN as the mobile device.
- [x] Local-demo API smoke passes against the sqlite backend.
- [ ] The app launches to the login screen without a crash or red screen.

## Current Local Endpoints
- Expo / Metro: `http://192.168.1.4:8081`
- Backend API: `http://192.168.1.4:8001`
- Current readiness mode: `local-demo` (usable for guided rehearsal, not trial-ready)

## 1. Login Validation
- [ ] Submit valid credentials and enter the 3-tab shell (`首页 / 工作台 / 台账`).
- [ ] Login button loading and disabled state are correct while submitting.
- [ ] Login failure shows friendly copy and does not expose raw backend endpoints.
- [ ] Android keyboard no longer collapses the login form while editing fields.
- [ ] Record result: pass/fail + screenshot.

## 2. Dashboard Validation
- [ ] Header, health section, and empty/error copy are readable and business-facing.
- [ ] Low-stock and pending-confirmation cards render correctly in both data and empty states.
- [ ] Dashboard action to go to the workbench navigates correctly.
- [ ] No raw `Loading...` placeholder or backend error leak appears in user-facing copy.
- [ ] Record result: pass/fail + screenshot.

## 3. Workbench Validation
- [ ] Timeline renders messages and confirmation cards.
- [ ] Text send flow works end-to-end: input -> sending -> refreshed result.
- [ ] Default guided entry dock shows only business-language actions for voice, photo, and receipt.
- [ ] Legacy demo actions appear only after opening the debug disclosure.
- [ ] Connection hint copy is readable and updates across connected/reconnecting/degraded states.
- [ ] Record result: pass/fail + screenshot.

## 4. Ledger Validation
- [ ] Ledger title and key sections are readable Chinese: `搜索库存 / 库存工作区 / 最近活动`.
- [ ] Search input filters inventory cards as expected.
- [ ] Both ledger card actions work: `库存修正` and `出库登记`.
- [ ] Loading, empty, and error states are readable and do not leak backend internals.
- [ ] Activity timeline displays recent inventory-related records.
- [ ] Record result: pass/fail + screenshot.

## 5. Debug Tool Validation
- [ ] Dashboard and workbench debug disclosure are collapsed by default.
- [ ] Debug disclosure stays easy to open/close, but remains visually secondary to the main workflow.
- [ ] Debug actions still work after expansion and show clear outcome feedback.
- [ ] Debug tools do not block the primary rehearsal path.
- [ ] Record result: pass/fail + screenshot.

## 6. Exit Criteria
- [ ] All five areas pass.
- [ ] No P0/P1 crash, white screen, or flow-blocking defect remains.
- [ ] No unreadable copy, mojibake, or raw backend error copy remains in user-facing UI.
- [ ] Trial rehearsal notes and screenshots are attached to the current run record.
