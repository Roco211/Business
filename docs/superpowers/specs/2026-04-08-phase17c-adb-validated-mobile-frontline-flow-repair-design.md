# Phase 17C ADB-Validated Mobile Frontline Flow Repair Design

## Goal

Turn the current Android Expo app from a screen-complete but flow-broken trial shell into a mobile frontline experience that survives a real `adb` walkthrough on a phone-sized viewport.

The success condition for Phase 17C is:

`a first-time operator can move from login to the intended action without getting lost, misled, or forced to hunt for the next step`

This phase is about fixing flow truthfulness, task continuity, and mobile feedback quality.

It is not a native microphone or camera integration phase.

## Why This Phase Is Next

Phase 17B framed the shell-hardening direction correctly, but the `adb` validation on 2026-04-08 showed that several important assumptions still fail in actual mobile use.

The real-device walkthrough covered:

1. launch in Expo Go from the local development server
2. login with the default owner credentials
3. dashboard quick-action taps
4. workbench scroll and guided-entry usage
5. guided voice, image, and receipt submissions
6. ledger inventory-card actions and form completion path discovery

That walkthrough confirmed the current shell is no longer failing because of raw rendering or broken navigation.

It is failing because the user journey still breaks trust in four places:

- actions promise one thing and land somewhere else
- the workbench hides the primary task entry below history and confirmation clutter
- guided entry actions do not explain what is happening before or after submission
- the ledger action flow splits selection and execution across distant scroll regions

Those are frontline blockers, not cosmetic issues.

## Evidence From The ADB Walkthrough

The validated findings from the phone-sized Android emulator are:

### 1. Dashboard Quick Actions Are Not Intent-Preserving

From the dashboard, tapping the voice-query quick action moved to the generic workbench header rather than to a voice-specific action state.

This breaks user expectation immediately because:

- the label promises a direct task
- the destination is a generic feed
- the user must rediscover the relevant control manually

The same structural issue applies to the dashboard quick actions for photo, receipt, and pending confirmation handling.

### 2. The Workbench Starts With History Instead Of Action

On mobile, the workbench initially presents:

- connection status
- result history
- confirmation cards

The actual guided entry area sits far below the fold and requires multiple scrolls to reach.

That means the default frontline page behaves like a log viewer before it behaves like a task launcher.

### 3. Guided Entry Actions Feel Like Invisible Script Triggers

The guided-entry buttons for voice inventory, photo recognition, and receipt entry do not provide a believable capture or processing experience.

Observed behavior:

- no explicit in-progress state is surfaced to the user
- no step-by-step feedback is shown
- no capture metaphor appears
- the button tap silently inserts a prewritten owner message
- the inserted content is English sample text such as `check stock left for cola`

From a user perspective, that feels like the app is faking work rather than helping with work.

### 4. Feedback After Guided Actions Is Too Weak

After tapping guided entry buttons and waiting, the page did not provide a clear task-status update near the entry zone.

The only visible outcome was a new message in the history list.

That creates ambiguity:

- did the app accept the action
- is processing still running
- did anything fail
- where should the user look next

### 5. Message And Confirmation Surfaces Still Leak Engineering Posture

The workbench still surfaces:

- English result strings
- `Mock runtime` phrasing
- receipt messages with weak or absent readable summaries
- long confirmation cards that behave like raw review forms

This undermines operator trust even when the underlying flow is technically functioning.

### 6. Ledger Action Continuity Is Broken

In the ledger, tapping `Inventory correction` on an inventory card did not visibly move the user to the action form.

The selected item only became obvious after manual scrolling to the lower `Action panel`.

The user flow currently requires:

1. choose an item in one screen region
2. infer that something changed off-screen
3. scroll down to rediscover the selected item
4. continue data entry in a different region

That is a classic mobile continuity failure.

### 7. Mobile Finishing Gaps Still Damage Trust

Real-device review also confirmed smaller but still important confidence problems:

- tab icons render as placeholder glyphs
- the dashboard allocates too much first-screen space to header and summary before actions
- the red `Connection limited` badge is visually strong but operationally weak because it offers no next action

## Product Standard For This Phase

At the end of Phase 17C, a first-time operator should be able to:

1. sign in and understand the first actionable next step
2. tap a dashboard quick action and land in the matching task context
3. use a guided entry action and receive immediate feedback that the request was accepted
4. understand whether the app is processing, awaiting confirmation, or blocked
5. resolve a confirmation without feeling buried under raw fields
6. trigger a ledger action and continue the form without hunting for the panel

## Constraints

Phase 17C should preserve these current boundaries:

- keep the current Expo managed app
- keep the bottom-tab information architecture
- keep the existing auth, dashboard, chat, ledger, and confirmation backend contracts
- avoid introducing native microphone, camera, or file-picker integrations in this phase
- keep debug tooling available for developers, but not in the frontline default path

This phase should primarily improve flow shaping, client-side state handling, copy, and layout ordering.

## Approaches Considered

### 1. Copy Cleanup Only

Pros:

- low risk
- fast to implement
- removes some obvious trust damage

Cons:

- does not fix quick-action misrouting
- does not make guided entry understandable
- does not solve ledger continuity

### 2. Big IA Redesign

Pros:

- could produce a cleaner long-term product shell
- allows deeper rethinking of workbench and ledger boundaries

Cons:

- too large for the immediate rescue need
- increases implementation and regression risk
- delays the highest-value flow repairs

### 3. Evidence-Driven Flow Repair

Pros:

- directly addresses the failures seen in `adb` validation
- keeps scope focused on the mobile frontline path
- can land without backend contract expansion
- prepares the shell for later native capture and provider improvements

Cons:

- leaves true native capture for a later phase
- requires careful client-side choreography to feel coherent

## Chosen Approach

Use approach 3.

Phase 17C should repair the existing mobile shell around five specific user-journey fixes:

1. preserve user intent from dashboard into workbench
2. move workbench task entry above passive history on mobile
3. add explicit guided-entry submission feedback
4. compress and clarify confirmation behavior
5. restore continuity between ledger selection and ledger form completion

## Design

### 1. Preserve Intent Across Dashboard And Workbench

Dashboard quick actions should no longer navigate to a generic workbench scene with no context.

They should navigate with an explicit `initialIntent` value such as:

- `voice-query`
- `photo-stock-in`
- `receipt-entry`
- `pending-confirmations`

The workbench should consume that intent and immediately:

- bring the corresponding task zone into view
- show a short contextual heading for the chosen action
- visually emphasize the matching entry chip or section

For example:

- tapping the voice-query quick action should land on the workbench with the guided voice chip highlighted and the page positioned at the task-entry section
- tapping the pending-confirmations quick action should land near pending confirmations rather than near historical results

This preserves promise-to-destination truth.

### 2. Reorder The Workbench For Mobile Task-First Use

On mobile phone widths, the workbench should change from:

`status -> long result history -> confirmations -> entry`

to:

`status -> current task entry -> pending confirmations -> recent results`

Recommended order:

1. connection and availability banner
2. guided entry section
3. direct text entry section
4. pending confirmations
5. recent results timeline

This does not require a new tab or new backend data.

It requires changing the content order and section emphasis for the mobile default path.

The history list should remain available, but it should stop outranking the next actionable controls.

### 3. Add A Real Guided-Entry Feedback Model

Guided entry actions should behave like accepted task submissions, not invisible script triggers.

When the user taps a guided entry action, the UI should immediately show a local task-feedback state near the entry area:

- `Submitting voice request...`
- `Submitting photo recognition request...`
- `Submitting receipt entry request...`

When the request succeeds, the entry zone should show a compact success handoff such as:

- `Submitted. Processing is in progress.`
- `If review is needed, check pending confirmations below.`

If the current implementation still relies on controlled sample payloads rather than true native capture, the UI must be honest about that boundary in a low-noise way.

Recommended treatment:

- business-first button labels remain
- a supporting hint explains that the current trial path submits a prepared sample request for flow rehearsal
- the debug disclosure retains the older explicit test actions

This preserves frontline clarity without pretending that native capture already exists.

### 4. Clarify Connection State With Actionable Guidance

The workbench connection surface should stop acting like a red warning label without next steps.

For degraded or disconnected states, the header or banner should explain:

- what is limited
- what still works
- what the user should do next

Recommended user-facing interpretation:

- `Connected`: results update automatically
- `Syncing`: data and results are still loading
- `Connection limited`: submissions still work, but refresh may be delayed
- `Unavailable`: the task area cannot complete requests right now

For recoverable states, the surface should provide a retry action or refresh affordance rather than only passive text.

### 5. Compress Confirmation Cards For Mobile Review

Confirmation cards should shift from raw editable forms toward summary-first review.

Recommended pattern:

- strong title and one-line summary
- compact key fields visible first
- optional expand or edit region for detailed adjustments
- primary confirm action
- quieter secondary reject action

Receipt confirmation should especially avoid presenting a wall of fields before the user understands the batch.

The card should first answer:

- what document was recognized
- how many lines were extracted
- what total was found
- what looks suspicious

Only then should line-item editing expand into view.

### 6. Restore Ledger Selection-To-Action Continuity

The ledger should respond immediately when the user taps `Inventory correction` or `Stock-out registration`.

Minimum acceptable behavior for this phase:

- auto-scroll the selected item into the action panel region
- pin the selected item summary at the top of the panel
- visually confirm which action is active
- focus the first editable field

The user should never have to guess whether the tap worked.

Within current scope, the recommended implementation is to keep the shared `Action panel`, but make it self-revealing after selection.

If time permits, the better follow-on evolution is an inline expandable card form, but that is not required for Phase 17C.

### 7. Tighten Mobile Visual Hierarchy

This phase should also make a few deliberate mobile-first visual adjustments:

- reduce top-of-screen header height on dashboard and ledger
- ensure quick actions appear within or closer to the first screen on phone viewport
- replace placeholder tab glyphs with real icons or iconless-but-clean tab treatments
- demote older result history visually once guided entry and confirmations move above it

These are not decorative changes.

They improve scan speed and reduce the sense that the user must excavate the real workflow.

## Architecture And Component Impact

Phase 17C should remain a frontend-only coordination phase across existing mobile modules.

Likely touch points:

- dashboard quick-action navigation and route params
- root navigator param typing and tab handoff behavior
- workbench screen section ordering and scroll targeting
- guided entry dock local submission-feedback state
- workbench connection banner copy and actions
- confirmation card shells and receipt confirmation presentation
- ledger selection handling and panel auto-scroll behavior
- shared mobile UI primitives for icons, banners, and task-status messaging

No new backend contracts are required for the core phase.

## Data Flow

### Dashboard To Workbench

1. user taps a dashboard quick action
2. dashboard navigates to workbench with `initialIntent`
3. workbench resolves the target section from that intent
4. workbench scrolls to and emphasizes the matching section

### Guided Entry Submission

1. user taps a guided entry chip
2. chip enters submitting state
3. local task-feedback banner appears near the guided entry area
4. existing mutation submits the request
5. on success, banner switches to accepted state and the timeline refreshes
6. on failure, the banner explains the failure without relying only on a distant history update

### Ledger Action Continuity

1. user taps a card-level action
2. ledger records the selected item and action
3. screen scrolls to the action panel
4. panel shows the selected item summary and active form
5. first relevant field becomes the next clear action

## Error Handling

Phase 17C should explicitly separate these failure categories in the UI:

- navigation and intent handoff failure
- guided-entry submission failure
- timeline refresh failure after a successful submission
- confirmation action failure
- ledger mutation failure
- session connection degradation

Failure copy should tell the user whether to:

- retry now
- continue and wait for refresh
- review pending confirmation later
- stop because the current flow is unavailable

## Testing Strategy

Phase 17C should be verified in three layers.

### 1. Component And Screen Tests

Add or update React Native tests for:

- dashboard quick actions passing the correct intent
- workbench rendering the correct emphasized section for each intent
- guided entry showing submitting and accepted states
- confirmation cards defaulting to summary-first presentation
- ledger auto-scrolling or state-switching after card action selection

### 2. Integration Behavior Tests

Add integration coverage around:

- intent-preserving navigation from dashboard to workbench
- guided entry success and failure rendering
- workbench ordering on phone-sized layouts
- ledger selected-item continuity

### 3. ADB Regression Walkthrough

Repeat the validated manual path:

1. login
2. tap dashboard quick action
3. confirm landing in matching task context
4. trigger guided voice, image, and receipt actions
5. observe immediate feedback
6. resolve one confirmation
7. tap one ledger action and verify the form is surfaced automatically

The `adb` walkthrough should be considered a release gate for this phase because that is where the current failures were discovered.

## Out Of Scope

Phase 17C should not include:

- native microphone recording
- native camera capture
- native file picking
- backend contract redesign
- provider or model integration changes
- a new navigation model
- a major ledger architecture rewrite

Those can follow after the shell stops misleading the user about the flows it already has.

## Recommended Implementation Order

1. quick-action intent handoff from dashboard to workbench
2. workbench mobile section reorder
3. guided-entry feedback states
4. connection banner clarification
5. confirmation-card compression
6. ledger action continuity
7. mobile finishing details such as tab icon repair and first-screen density cleanup

## Success Criteria

Phase 17C is complete when:

- dashboard quick actions land in the matching workbench context
- guided entry is reachable and understandable without exploratory scrolling
- guided entry taps visibly submit and visibly succeed or fail
- confirmation cards are understandable on a phone without scrolling through a raw wall of fields first
- ledger selection immediately leads the user to the relevant action form
- the app no longer feels like a hidden demo harness during a basic frontline rehearsal
