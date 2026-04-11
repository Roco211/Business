# Mobile UI Productization And Debug Isolation Design

## Goal

Turn the current `codex/ui-yuanbao-dashboard-refresh` mobile branch from a partially refreshed engineering shell into a product-facing frontline app that:

- reads correctly
- feels cohesive across screens
- preserves the best parts of the current visual refresh
- keeps development aids out of the standard user path

This phase is successful when:

1. all user-visible Chinese copy in the mobile app is readable and correctly encoded
2. dashboard, workbench, ledger, and bottom navigation feel like one product surface
3. debug and demo utilities are absent from the default user path
4. Android validation no longer shows mojibake, escaped unicode leakage, or developer-facing controls in the primary flow

## Why This Phase Is Next

The branch already points in a stronger direction than the older mobile shell:

- warmer background treatment
- softer card styling
- better dashboard hierarchy
- more product-like shared UI surfaces

But it is still not ready for a user-facing demo or trial because three classes of issues remain visible.

### 1. Source-Level Text Corruption Is Still Present

The current branch contains source-level mojibake across user-visible mobile surfaces, including:

- `DashboardScreen`
- `DashboardSummaryHero`
- `DashboardQuickActions`
- `LedgerScreen`
- `LedgerActionPanel`
- `WorkbenchHeader`
- shared status copy in `frontlineStatus.ts`

This is not just a rendering problem. The broken strings already exist in source, so the fix must happen at the source text layer.

### 2. Debug And Demo Posture Still Leaks Into The Frontline Path

The normal user path still exposes or depends on development-era affordances such as:

- `DebugDisclosure`
- demo reset controls
- legacy mock/demo media panels
- developer-facing wording in workbench interactions

Even when visually demoted, these surfaces still make the app feel like an internal QA shell rather than a trustworthy store-facing product.

### 3. Navigation And Screen Hierarchy Still Feel Unfinished

The branch already improved several layouts, but the app still shows instability:

- bottom-tab labels and icon treatment are not consistently trustworthy on Android
- dashboard, workbench, and ledger do not yet fully share one product voice
- some loading, empty, and failure states still read like engineering fallback copy rather than calm product guidance

## Chosen Approach

Use the approved productization approach with an explicit bias toward being both:

- **steady**: preserve the current screen architecture, business flows, and three-tab information architecture
- **bold**: do not stop at string replacement; turn the current refresh into a clearly productized frontline experience

This phase should:

- keep the current tab structure
- keep the current dashboard overview-first structure
- keep the current workbench message and confirmation flow
- keep the current ledger read-and-act flow
- remove debug leakage from the user path
- normalize copy and state language into one consistent frontline voice

This phase should not turn into a broad mobile architecture refactor.

## Scope Decisions

### 1. Repair User-Facing Copy At The Source

All user-visible corrupted strings should be replaced with valid UTF-8 Chinese source text.

This includes:

- screen titles
- subtitles
- button labels
- loading states
- empty states
- error states
- status labels
- helper guidance
- action descriptions
- bottom-tab labels

This phase should not rely on:

- runtime transcoding
- post-render text cleanup
- string escaping tricks that merely mask corrupted source

### 2. Remove Debug Utilities From The Default User Path

The standard mobile user path should contain:

- dashboard actions
- workbench actions
- inventory operations
- connection and task-status messaging

It should not contain:

- debug disclosures
- demo reset buttons
- explicit mock/demo labels
- legacy demo panels

Development utilities may remain available only behind an explicit developer opt-in inside development builds, without introducing a large new environment system in this phase.

Boundary:

- default app path: no debug controls rendered
- development builds: debug controls appear only when a developer-only opt-in is enabled

### 3. Keep The Existing Navigation Model

The app should keep the current bottom-tab structure:

- home
- workbench
- ledger

This phase should not add:

- a settings tab
- a debug tab
- new nested navigation
- a redesigned auth routing model

The goal is to make the existing IA trustworthy, not to invent a new one.

### 4. Preserve The Best Parts Of The Current Refresh

The branch already has real value in its current visual direction. That value should be preserved and strengthened.

Keep:

- the warm neutral background and soft-surface palette
- the dashboard status-strip and hero-card posture
- card-based quick actions and exception lists
- the branded workbench header and status badge pattern
- calmer, more product-like shared UI primitives

### 5. Treat Android Validation As A Hard Acceptance Gate

The app has already shown gaps between source expectations and device reality.

This phase should therefore treat Android validation as required, especially for:

- bottom navigation label rendering
- workbench header rendering
- dashboard copy
- ledger copy
- absence of debug controls

## Product Language Rules

The frontline mobile copy should follow one stable voice:

- business-facing rather than engineering-facing
- actionable rather than explanatory
- calm rather than verbose
- consistent across dashboard, workbench, and ledger

Rules:

- say what the user should look at or do next
- avoid surfacing internal implementation language
- avoid `mock`, `demo`, `runtime`, or `debug` wording in the user path
- use shared status vocabulary for connected, connecting, unavailable, degraded, failed, and pending states

## Design

### 1. Dashboard

The dashboard should remain the operational starting surface.

Keep the current high-level structure:

- connection-aware status strip
- summary hero
- recommended next step
- common actions
- exception lists

Refine it in these ways:

- restore all strings to readable Chinese
- keep the stronger "today / next action / risks" hierarchy
- make the status strip the single health summary rather than splitting health messaging across competing blocks
- ensure recommendation copy sounds like store guidance, not test setup
- remove debug surfaces entirely from the user-facing dashboard path

The dashboard should answer:

1. is the app healthy enough to use
2. what is most urgent today
3. where should the user go next

### 2. Workbench

The workbench should become the execution surface, not a developer console.

Keep:

- branded header
- connection state
- results timeline
- confirmation cards
- guided entry dock
- message composer

Change:

- fix all broken copy in screen-level and component-level strings
- keep connection language short and human
- ensure guided actions describe business actions only
- remove user-visible debug disclosure and legacy mock/demo panels from the standard screen
- keep confirmation cards visually more important than passive result messages
- keep user input available but secondary to the "what can I do next" posture

The workbench should feel like:

- a place to act
- a place to confirm
- a place to review outcomes

not:

- a place to inspect internal tooling

### 3. Ledger

The ledger should remain a lightweight inventory workspace with two jobs:

1. find inventory items and act on them
2. review recent inventory activity

Keep:

- search input
- inventory list
- action panel
- activity timeline

Refine:

- replace all corrupted strings with clean Chinese
- tighten titles and helper copy so users can immediately scan "search / inventory / action / timeline"
- make submit, loading, and error copy feel operational rather than technical
- preserve the current flow without adding new sheets or navigation

The ledger should feel calm and practical, not experimental.

### 4. Bottom Navigation

The bottom tab bar should stay visually distinctive but must become fully trustworthy on Android.

Requirements:

- tab labels render as the correct final Chinese text for home, workbench, and ledger
- no escaped unicode or placeholder-like strings appear in labels
- no broken icon fallback or glyph leakage appears in the tab surface
- the selected state remains obvious without making the bar noisy

If the current icon treatment cannot be made reliable quickly, the implementation should prefer stable label-first navigation over decorative but unstable icon behavior.

### 5. Shared Status And Copy Layer

User-facing copy currently lives in a mix of screen-local constants and shared helpers. This phase should normalize that layer without turning it into a large architecture rewrite.

Recommended direction:

- clean corrupted shared copy first, especially `frontlineStatus.ts` and workbench connection helpers
- keep screen-local copy where it is screen-specific
- use shared helpers only for truly shared state language

The important boundary is consistency, not maximal abstraction.

### 6. Development-Only Utility Boundary

Current utilities such as demo reset and legacy mock media panels should move behind a single development-only rendering boundary.

Recommended implementation rule:

- use a development-build gate plus explicit developer opt-in at the component render layer
- do not let user-path tests depend on debug controls being present
- update tests to assert their absence from the default product path

This keeps local development possible without leaking development posture into the demo path.

## Architecture And File-Level Intent

This phase will touch these categories of files.

### Screen Surfaces

- `apps/mobile/src/features/dashboard/screens/DashboardScreen.tsx`
- `apps/mobile/src/features/chat/screens/ChatScreen.tsx`
- `apps/mobile/src/features/ledger/screens/LedgerScreen.tsx`
- `apps/mobile/src/app/navigation/RootNavigator.tsx`

### Supporting Screen Components

- dashboard components
- workbench header and guided-entry components
- ledger action and display components

### Shared Copy And UI Primitives

- `apps/mobile/src/shared/copy/frontlineStatus.ts`
- `apps/mobile/src/shared/session/getWorkbenchConnectionCopy.ts`
- `apps/mobile/src/shared/ui/DebugDisclosure.tsx` or its call sites
- shared status, empty-state, and notice primitives where copy or rendering rules change

### Tests

- dashboard screen tests
- chat/workbench screen tests
- ledger tests
- shared UI primitive tests
- navigation tests when tab label behavior changes

## Execution Sequence

The implementation plan should follow this order.

### 1. Shared Copy And Debug-Visibility Guardrails

First:

- restore shared copy to readable Chinese
- define the development-only render gate
- update or add tests proving debug controls are absent from the default user path

This prevents later screen work from reintroducing mixed-state behavior.

### 2. Dashboard Productization Pass

Then:

- repair dashboard strings
- preserve the current visual direction
- remove debug controls
- verify next-action and health language

### 3. Workbench Productization Pass

Then:

- repair workbench strings
- remove user-visible debug/demo panels
- keep guided actions and status presentation aligned with the dashboard voice

### 4. Ledger Productization Pass

Then:

- repair ledger strings
- tighten operation and timeline copy
- keep the existing mutation flow intact

### 5. Navigation Reliability Pass

Then:

- verify bottom-tab labels and any icon treatment
- adjust navigation presentation only as needed to guarantee stable device rendering

### 6. Android Verification Pass

Finally:

- run mobile tests
- run Android emulator validation
- confirm no user-visible debug or mojibake remains in the core path

## Error Handling

This phase should preserve existing data-fetch and mutation behavior while improving presentation.

Rules:

- loading states should stay visible and calm
- recoverable fetch failures should remain inline and actionable
- connection degradation should be described in user terms
- task-level errors should stay local to the relevant area
- removing debug surfaces must not remove user understanding of failures

## Testing Strategy

This phase should remain test-first.

Required coverage:

1. screen tests for dashboard, workbench, and ledger user-visible copy
2. tests proving debug controls are absent from the default user path
3. tests proving bottom navigation labels are stable and correct
4. tests for shared status copy helpers and connection-state presentation
5. Android manual validation using the emulator after code changes land

Important expectations:

- no mojibake strings in assertions
- no user-path debug-tools disclosure
- no user-path demo-reset control
- no visible legacy mock/demo labels
- friendly connected, unavailable, and degraded messaging remains intact

## Acceptance Criteria

This phase is complete when all of the following are true:

1. Dashboard, workbench, ledger, and bottom navigation display readable Chinese copy on Android.
2. No source-level mojibake remains in the user-facing mobile path.
3. Debug-tools disclosure, demo-reset controls, and legacy mock/demo controls are absent from the default user path.
4. Dashboard still communicates app health, next action, pending confirmations, and low-stock context clearly.
5. Workbench still supports guided entry, message review, and confirmation handling without developer-facing leakage.
6. Ledger still supports search, inventory action handling, and activity review with clearer product copy.
7. Bottom-tab labels render reliably as the intended final Chinese labels for home, workbench, and ledger.
8. Shared status messaging remains consistent across loading, unavailable, degraded, and connected states.
9. Automated mobile tests and Android emulator validation both pass for the core user path.

## Out Of Scope

This phase does not include:

- adding new tabs or navigation structure
- changing backend contracts
- re-architecting the mobile data layer
- replacing current business flows with new ones
- adding new camera, recording, or media workflows
- adding a dedicated operator or settings surface
- broad UI-system refactoring unrelated to the current user-facing cleanup

## Follow-On Work

Once this phase lands cleanly, the next logical slices are:

1. a focused implementation plan for the approved UI productization work
2. any structural cleanup that implementation proves necessary
3. later cognitive or provider integration on top of a trustworthy mobile shell
