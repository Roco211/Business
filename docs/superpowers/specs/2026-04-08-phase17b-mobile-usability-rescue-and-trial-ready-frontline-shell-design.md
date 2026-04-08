# Phase 17B Mobile Usability Rescue And Trial-Ready Frontline Shell Design

## Goal

Turn the current Android Expo app from a partially redesigned engineering shell into a trial-ready frontline shell that a non-developer can actually open, understand, connect, and use for a basic workflow.

Phase 17B is intentionally not a "make the AI smarter" phase.

Its success condition is:

`the Android app becomes understandable and usable enough for guided trial rehearsal`

not:

`the runtime reaches its final cognitive/provider architecture`

## Why This Phase Is Next

Phase 17A improved the mobile visual language and added a stronger shared UI system, but the real device experience still shows major pilot blockers:

- user-visible text still contains mojibake, escaped unicode, and engineering-era wording
- Android/Expo runtime behavior still has fragile connection defaults and unclear error states
- the workbench default path still exposes demo-shaped media actions and debug-era interaction assumptions
- user-visible backend responses still surface `Mock runtime` posture
- the app can still feel broken or untrustworthy even when the backend itself is healthy

That means the next highest-value step is not adding more intelligence first. The next step is to remove the reasons a real user would reject the app within the first minute.

## Product Standard For This Phase

Phase 17B should move the Android app to a:

`trial-ready frontline shell`

This is deliberately narrower than "production-ready store app."

At the end of the phase, a first-time non-developer should be able to:

1. open the app without blank screens or broken text
2. understand whether they are connected to the backend
3. sign in successfully
4. navigate across login, dashboard, workbench, and ledger without confusion
5. complete one basic request flow and understand the outcome
6. distinguish normal results, pending confirmations, and connection failures

## Current Constraints

Phase 17B should respect the existing product boundaries:

- keep the Expo managed mobile shell
- keep the current bottom-tab information architecture
- keep the existing auth, session bootstrap, and session-stream backend contracts
- keep the current dashboard, chat, ledger, and confirmation data sources
- preserve debug and demo tooling for development, but demote them from the default frontline path

This phase should not depend on `coding plan` integration or new multimodal provider contracts to be successful.

Those capabilities remain strategically important, but they should land after the app becomes usable enough to host them safely.

## User-Visible Problems To Solve

From a real user perspective, the current app still fails in six ways:

### 1. Trust Is Broken Immediately

Broken Chinese strings, mojibake, escaped unicode, and user-visible mock language make the app feel unfinished and unsafe.

### 2. Connection State Is Opaque

Users cannot clearly tell whether a failure is caused by:

- the backend API being unreachable
- login failing
- session bootstrap failing
- workbench realtime failing
- a task-specific runtime failure

### 3. The Default Path Still Feels Like A Demo

Even after the visual redesign, too much of the chat/workbench experience still reflects engineering validation language and demo-driven flow shape.

### 4. Screen States Are Not Yet Productized Enough

The app still has too many places where empty, loading, or failure states feel like fallback text rather than product behavior.

### 5. Real User Intent Is Not Separated From Debug Utilities

Debug controls, demo reset posture, and legacy demo media flows still leak too close to the frontline default experience.

### 6. The App Is Not Yet A Safe Shell For Later Cognitive Integration

Even if `coding plan` and real multimodal providers were integrated now, the user experience would still feel unstable because the shell itself does not yet communicate status, outcome, and next actions reliably.

## Approaches Considered

### 1. Provider Integration First

Pros:

- moves the backend closer to the intended long-term intelligence stack
- may improve perceived capability for some tasks

Cons:

- does not solve broken copy, connection clarity, or default-path confusion
- makes it harder to distinguish frontend usability failures from provider failures
- risks spending time on intelligence inside a shell that users still distrust

### 2. Mixed Rescue Plus Provider Integration

Pros:

- feels ambitious and end-to-end
- can deliver some realism improvements alongside UI rescue

Cons:

- scope grows too large for a single clean phase
- mixes UX rescue, runtime integration, and provider rollout risks together
- weakens verification clarity because many failures can appear at once

### 3. Usability Rescue First

Pros:

- directly addresses the current blocking user experience issues
- creates a stable shell for later cognitive and provider integration
- shortens feedback loops because user-reported problems will map more clearly to specific layers

Cons:

- defers `coding plan` and real multimodal value one more phase

## Chosen Approach

Use approach 3.

Phase 17B should be a usability rescue and shell hardening phase first.

The sequence should be:

1. normalize copy and user-visible states
2. fix connectivity and runtime status clarity
3. remove demo-first posture from the default path
4. harden the four core screens into one stable trial shell

Only after that should the project move into a dedicated cognitive/provider phase where:

- `coding plan` acts as the reasoning brain
- multimodal API keys power image and related recognition providers

## Design

### 1. Normalize User-Visible Copy And State Language

Phase 17B should introduce a mobile copy cleanup pass across all four frontline screens.

The cleanup should enforce these rules:

- no mojibake or broken-encoding Chinese
- no user-visible escaped unicode sequences
- no `Mock runtime` copy in frontline surfaces
- no `Demo` naming in the default user path
- no raw engineering phrasing where human wording is available

This work should cover:

- screen titles
- section titles
- button labels
- loading text
- failure text
- empty states
- confirmation copy
- banner and inline notice copy

Phase 17B should also define one shared state vocabulary for the mobile app:

- connecting
- connected
- syncing
- unavailable
- failed
- retry available
- awaiting confirmation
- completed
- degraded

Every frontline screen should reuse this language instead of inventing its own wording ad hoc.

### 2. Establish A Clear Connectivity Baseline

The app should help a user and developer distinguish which layer is failing.

Phase 17B should add a clear frontend model for:

- API reachability
- login success/failure
- session bootstrap success/failure
- workbench realtime connection state
- task mutation success/failure

This does not require new backend contracts. It requires stronger client-side interpretation and presentation of the contracts that already exist.

Recommended treatment:

- login screen shows friendly network/auth failure copy
- dashboard can surface whether the app is connected and when data last synchronized
- workbench header reflects `connecting`, `connected`, `degraded`, or `disconnected`
- task-level failures remain local to the action surface instead of turning the entire app into a vague broken state

The mobile default API strategy should also be improved for Expo Go and real-device testing so that the app no longer silently assumes emulator-only addresses as the most common path.

### 3. Make The Default User Path Non-Demo

Phase 17B should not remove all debug/demo tooling, but it should change what a normal user sees first.

The default workbench path should look like:

- voice
- photo
- receipt
- text input

It should not look like:

- voice query demo
- receipt OCR demo
- mock media panel
- explicit demo upload wording

The important design boundary is:

- internal helper hooks may still use controlled development flows where necessary
- frontline UI should describe business actions, not developer fixtures

Debug-only surfaces should remain available behind a clearly labeled secondary disclosure or environment area.

### 4. Harden Login Into A Real Entry Screen

The login screen should become a reliable entry point rather than just a styled form.

It should provide:

- stable and correct Chinese copy
- one dominant primary action
- explicit loading state
- clear credential vs network failure distinctions
- optional environment hint in a secondary debug area

It should also avoid layout structures that can collapse or disappear on Android under real device conditions.

### 5. Harden Dashboard Into A Practical Starting Screen

The dashboard should answer:

`what should I do first, and is the app currently healthy enough to do it`

It should keep the current summary/alerts/confirmations structure, but raise the visibility of:

- current connection health
- current shop context
- pending confirmations
- low-stock issues
- the primary next action

Lower-priority debug tools such as demo reset should remain accessible but visually demoted.

### 6. Harden Workbench Into A Stable Task Surface

The workbench should become the most trustworthy screen in the app.

It should clearly separate:

- conversation/result content
- confirmation content
- connection/system state
- input actions
- debug tools

Phase 17B should especially improve the workbench in these ways:

- users always understand whether the session is connected
- failures say what failed in human terms
- confirmation cards visually outrank passive result messages
- task actions look like business actions, not test triggers
- the default path does not expose demo-first terminology

This phase should not yet add full native capture flows if that would widen scope too far. It should instead make the existing flow shell understandable and honest.

### 7. Harden Ledger Into A Calm Inventory Workspace

The ledger should become easier to scan and safer to act within.

Phase 17B should improve:

- copy quality
- action clarity
- submit feedback
- empty and error states
- separation between list browsing and mutation actions

The goal is that the ledger feels like a legitimate inventory workspace, not a development CRUD panel.

### 8. Standardize Shared Frontline State Components

Phase 17B should use the Phase 17A UI foundation, but extend it with stricter frontline state rules.

Important shared surfaces include:

- inline notices
- status badges
- empty states
- loading placeholders or loading copy
- connection banners
- error-retry affordances
- debug disclosures

These components should become the single way the app expresses:

- network failure
- degraded runtime state
- unavailable data
- pending confirmations
- success acknowledgements

This keeps the app visually consistent and reduces the chance of another screen drifting back toward engineering-shell behavior.

### 9. Separate Frontline Copy From Backend Runtime Internals

Phase 17B should also clean up user-visible wording across client/backend interaction boundaries.

If the backend still internally uses mock-first runtime paths, the frontend should not surface that internal posture directly to users.

This means:

- user-facing result summaries should use business language
- backend-originated copy that still says `Mock runtime` should be normalized before becoming visible in frontline screens
- the mobile client should prefer stable human-facing labels over internal task language where possible

This can be implemented either by cleaning upstream response text or by adding explicit presentation-layer normalization in the mobile app where needed.

### 10. Keep Debug Utilities But Demote Them

Phase 17B should preserve the current development and operator aids:

- demo reset
- environment hints
- legacy demo panels if still needed for local development
- extra failure detail that helps diagnosis

But these should move behind:

- a debug disclosure
- an environment sheet
- a clearly secondary utilities area

The default user path must feel clean enough that a real store operator is not forced to think like a developer.

## Architecture And Execution Sequence

Phase 17B should be implemented in four ordered workstreams:

### 17B1 Copy And State Normalization

Focus:

- copy cleanup
- encoding cleanup
- removal of user-visible mock/demo wording
- shared state wording alignment

### 17B2 Connectivity And Runtime Status Baseline

Focus:

- API base URL behavior for real-device use
- login and bootstrap failure clarity
- session-stream connection clarity
- recoverable error presentation

### 17B3 Default User Path De-Demoization

Focus:

- business-language input actions
- removal of demo-first labeling from the primary path
- debug tools relocation

### 17B4 Trial-Shell Screen Hardening

Focus:

- login stability
- dashboard operational clarity
- workbench trust and confirmation clarity
- ledger usability polish
- end-to-end manual validation on Android/Expo

## Success Criteria

- all four frontline screens use readable, correct user-visible copy
- no obvious mojibake or escaped-unicode leakage remains in frontline Android flows
- the app can clearly communicate API, bootstrap, and realtime connection states
- the default workbench path no longer reads as a demo tool
- a user can log in, navigate, run a basic task flow, understand a result, and find confirmations
- dashboard and ledger both feel usable enough for guided rehearsal
- debug and demo controls remain available without dominating the main workflow
- Expo Android manual validation shows no blank-screen or collapsed-layout regressions in the core path

## Out Of Scope

Phase 17B should explicitly not include:

- `coding plan` integration as the runtime reasoning brain
- real router/summarizer LLM integration
- real multimodal provider cutover
- native recording/camera capture expansion if it requires a larger architecture shift
- backend contract redesign
- operator admin portal expansion
- full dark-mode rollout

## Follow-On Phase

The intended next phase after Phase 17B should be a dedicated cognitive/runtime integration phase, for example:

`Phase 17C Cognitive Runtime Integration And Real Multimodal Providers`

That later phase should cover:

- `coding plan` as the reasoning brain
- real image recognition provider integration via supplied multimodal API keys
- optional later expansion of OCR/routing/summarization integration

That work should happen only after the Android app is trustworthy enough to host it.

## Verification Strategy

Phase 17B should be verified in four layers:

1. mobile unit/screen tests for copy, states, and component behavior
2. integration-style mobile tests for login, workbench, and ledger user paths
3. Android/Expo manual validation for real-device startup, login, navigation, and workbench usability
4. explicit regression checks that debug/demo tools remain reachable but secondary

The final success test for this phase is simple:

`a non-developer can use the Android shell without first learning the internal implementation model`
