# Phase 17A Frontline Pilot UX And Guided Mobile Flows Design

## Goal

Turn the current Expo mobile app from a developer-oriented validation shell into a frontline-ready pilot app by redesigning the login, dashboard, chat, and ledger experiences around one Apple-inspired but operations-focused visual system, guided task flows, and confirmation-first interactions without changing the existing business API contracts or widening scope into a large admin surface.

## Why This Matters

After Phase 15A through 16C, the repository now has:

- formal auth and shop context
- protected HTTP and WebSocket flows
- real-provider boundaries for ASR, OCR, and Vision
- trial readiness, cutover, calibration, and incident recovery tooling
- an Expo mobile shell that can authenticate, render data, and exercise core flows

That is enough to say:

`the mobile app can prove the backend works`

It is not enough to say:

`a real store operator can confidently use the app during a pilot`

The current mobile surfaces still carry the posture of an engineering tool:

- the login screen is a plain form with little hierarchy or trust signaling
- the dashboard is a text dump of counts plus a demo reset button
- the chat screen still centers on `MockMediaEntryPanel` demo buttons rather than guided operator actions
- the ledger page behaves like a raw CRUD/testing surface instead of a usable inventory workspace

That mismatch now matters more than adding further backend capability. The remaining product risk is no longer "can the system do the job at all." It is "can a store user understand what to do, what happened, and what requires confirmation."

## Current Constraints

Phase 17A should respect the current codebase and runtime boundaries:

- the app is still an Expo managed app
- current navigation is a simple bottom-tab shell
- existing auth, dashboard, chat, ledger, confirmation, and stream contracts should remain stable
- current media flows already have upload-backed backend boundaries, even though the mobile UI still exposes them through demo-oriented controls
- the app should become light-mode-first now while reserving semantic tokens for a later dark-mode pass

This phase should redesign how the mobile client presents and guides existing capability. It should not redefine the backend product model.

## Approaches Considered

### 1. Cosmetic Restyling Only

Pros:

- fast
- low implementation risk
- would make screenshots look better quickly

Cons:

- leaves the task model unchanged
- keeps demo-first interaction patterns in place
- does not solve frontline confusion about states, confirmations, or next actions

### 2. Apple-Inspired Frontline Workbench

Pros:

- preserves the clarity, restraint, and hierarchy found in the Apple reference system
- adapts that visual language to a real operations app rather than a marketing page
- gives the app a coherent identity across login, dashboard, chat, and ledger
- directly addresses operator trust, state clarity, and guided action entry

Cons:

- requires a deeper redesign than cosmetic restyling
- demands discipline so the result does not become half marketing page and half admin panel

### 3. Native iOS-Style Utility App

Pros:

- very familiar and efficient
- straightforward to implement using common mobile UI patterns

Cons:

- weaker product identity
- underuses the design inspiration the user explicitly requested
- risks feeling generic rather than deliberate

## Chosen Approach

Use approach 2.

Phase 17A should produce an:

`Apple-inspired frontline workbench`

That means:

- restrained color and typography
- strong information hierarchy
- clear focus on one primary action at a time
- confirmation and exception handling that visually outrank passive content
- a mobile experience that feels calm, premium, and trustworthy without behaving like a product landing page

The Apple reference in `design-md/apple` should be treated as a design grammar, not a website to mimic literally.

## Design

### 1. Establish A Light-First Semantic Design System

The app should stop styling each screen ad hoc and instead define a semantic design layer for React Native.

Recommended token groups:

- colors
  - `bg.app`
  - `bg.surface`
  - `bg.elevated`
  - `bg.inverse`
  - `fg.primary`
  - `fg.secondary`
  - `fg.tertiary`
  - `accent.primary`
  - `status.warning`
  - `status.error`
  - `status.success`
- typography
  - `display.page`
  - `title.section`
  - `title.card`
  - `body.default`
  - `body.strong`
  - `caption`
  - `micro`
- spacing
  - `8, 12, 16, 20, 24, 32`
- radius
  - compact input/card radius
  - comfortable panel radius
  - pill radius for action chips
- elevation
  - flat
  - subtle lift
  - overlay
  - focus ring

The light palette should follow the Apple reference closely in spirit:

- app background around `#f5f5f7`
- surfaces around white
- primary text around `#1d1d1f`
- one interaction blue around `#0071e3`

Status colors should exist, but they should be tightly controlled. Blue remains the only color used to attract action. Warning, error, and success colors should communicate state rather than brand.

Phase 17A should reserve dark-mode tokens now, but the first pass should optimize the light theme rather than attempt full visual parity across both themes.

### 2. Use Apple-Inspired Rules Without Turning The App Into A Marketing Page

The Apple source material is valuable for its discipline:

- large, tight page headings
- generous whitespace
- one accent color
- restrained shadow
- clean pill actions
- dark translucent chrome when emphasis is needed

But the app is an operator tool, so the design should adapt those rules:

- body copy stays left aligned
- cards are task containers, not promotional tiles
- summary zones may use stronger contrast, but the rest of the app remains calm
- the top bar can use a glass-inspired surface, but should degrade gracefully to an opaque surface if blur is unavailable
- gradients, decorative illustrations, or heavy texture should not appear in Phase 17A

This creates a product that feels premium and composed while remaining fast to scan during real work.

### 3. Preserve The Existing Navigation Model, But Make It Feel Intentional

Phase 17A should keep the current bottom-tab information architecture because it already matches the product's mental model:

- dashboard or home
- chat or workbench
- ledger

The navigation does not need more destinations. It needs stronger hierarchy.

Recommended adjustments:

- use a cleaner tab bar with stronger active state and quieter inactive state
- give each tab a human label in Chinese rather than engineering shorthand
- reduce the amount of utility chrome competing with content
- treat the current tab as a scene with a clear top-level title and one dominant purpose

If environment or debug information must remain accessible, it should move into a secondary location rather than live at the top of frontline screens.

### 4. Redesign Login As A Trust-Building Entry Screen

The login screen should become a single-purpose entry experience.

Recommended structure:

- brand header
  - product name
  - one short value statement in Chinese
- centered surface card
  - email field
  - password field
  - primary sign-in button
- concise support text
  - connection or environment hint when relevant
  - human-readable error feedback

Interaction rules:

- only one primary action is visually dominant
- focus state uses the semantic blue ring
- loading state should be explicit in the button and optionally in a lightweight inline progress indicator
- connection failures should mention the API endpoint in human-readable wording when useful, but should not surface raw debugging noise by default

The goal is that even in development and pilot contexts, the first impression is stable and professional rather than experimental.

### 5. Turn Dashboard Into A Daily Store Overview, Not A Data Dump

The dashboard should answer:

`What should I pay attention to right now?`

Recommended structure:

- page title area
  - large title such as "Today" or its Chinese equivalent
  - small subtitle for shop context or last refresh
- summary hero card
  - today's stock-in count
  - completed tasks
  - pending confirmations
  - low-stock alerts
- quick action row
  - voice lookup
  - photo stock-in
  - receipt intake
  - pending confirmations
- exception sections
  - low-stock alerts
  - pending confirmations

Design rules:

- the summary card may use stronger contrast than surrounding cards to anchor the page
- exception cards should outrank routine counts
- developer actions such as demo reset should move into a lower-priority or explicitly labeled environment/debug area

The dashboard should feel like an operational launchpad rather than a report page.

### 6. Turn Chat Into A Guided Workbench

The chat screen is the app's most important screen and should stop behaving like a generic message list.

It should become a guided workbench with four clear layers:

- scene header
  - current work context
  - connection health
  - lightweight session status
- task conversation stream
  - user intent
  - system response
  - recognition results
- high-priority confirmation surfaces
  - pending stock-in confirmation
  - receipt confirmation
  - stock-out confirmation
- input dock
  - text entry
  - guided media actions

The visual distinction between passive messages and actionable confirmations should be strong. Confirmation cards should never disappear into the same hierarchy as ordinary text bubbles.

Recommended message classes:

- operator message
- system result message
- guidance or warning message
- confirmation card
- failure or retry card

Recommended state language:

- sending
- uploading
- analyzing
- awaiting confirmation
- completed
- failed, retry available
- degraded or safer mode active

This lets the workbench communicate process, not just transcript.

### 7. Replace Demo Buttons With Guided Multimodal Entry

The current `MockMediaEntryPanel` exposes development-era labels such as voice demo, photo demo, and receipt demo. Phase 17A should replace that interaction model with a user-facing entry dock.

Recommended first-pass input dock:

- primary text input
- compact pill actions for:
  - voice
  - photo
  - receipt

Each action should open a guided sub-flow rather than fire a hidden demo action immediately.

Recommended flow shape:

- voice
  - ready
  - capturing or preparing
  - uploading
  - analyzing
  - result or confirmation
- photo
  - choose source
  - preview
  - uploading
  - analyzing
  - result or confirmation
- receipt
  - choose source
  - preview
  - uploading
  - OCR analysis
  - line-item confirmation

The important Phase 17A boundary is:

- existing backend upload and send-message contracts remain the integration spine
- the mobile UI becomes guided and task-oriented
- development-only shortcuts, if still needed, move behind an explicit debug affordance and out of the frontline default path

### 8. Make Confirmation The Strongest Card In The System

The product's real differentiator is confirmation-first inventory action. The UI should make that obvious.

A confirmation card should contain:

- a clear task title
- a source label such as voice, photo, or receipt
- structured fields
  - item
  - quantity
  - unit
  - price when relevant
  - notes or confidence cues
- explicit warning or low-confidence highlighting when needed
- primary and secondary actions
  - confirm
  - edit
  - reject or defer

Design rules:

- stronger contrast or border treatment than a normal result card
- clearer spacing between label, value, and action groups
- no raw JSON-like metadata presentation
- field-level ambiguity should be visible and editable

If the chat stream is the narrative, confirmation cards are the decisive moments. They should look and feel that way.

### 9. Redesign Ledger As A Lightweight Inventory Workspace

The ledger screen should stop behaving like a test harness and instead provide one calm place to inspect stock and make corrective actions.

Recommended structure:

- header
  - title
  - optional subtitle or freshness indicator
- search and filtering area
  - search field
  - filter chips only when the underlying query supports a real filter, otherwise search stands alone in the first implementation
- inventory list
  - item name
  - current stock
  - unit
  - price state
  - compact actions
- recent activity timeline
  - audit events presented as a readable timeline rather than loose text rows

Mutation patterns:

- correction and stock-out actions should open a structured inline panel or lightweight sheet
- forms should foreground:
  - current quantity
  - desired quantity or stock-out quantity
  - reason
- submit state should be explicit and dismissible

The ledger should feel like a professional utility, not a raw admin form.

### 10. Standardize Shared States Across All Four Screens

Phase 17A should define shared rules for:

- loading
- empty
- success
- warning
- error
- offline or degraded
- protected or unavailable

Examples:

- empty dashboard sections should say what the user can do next
- login/network failures should use a consistent inline error treatment
- degraded runtime or cutover-related limitations should be surfaced as calm banners, not buried text
- long-running actions should avoid blocking the entire screen unless absolutely necessary

This is important because the current shell often renders state as raw text. The redesign should make state handling feel productized.

### 11. Keep Operational And Developer Tools Available, But Demote Them

The repo still needs developer and operator affordances during pilot work:

- demo reset
- runtime or environment hints
- debug endpoint or API hints
- temporary testing shortcuts that still remain necessary during pilot preparation

Phase 17A should not remove those tools. It should relocate them:

- a debug section
- an environment sheet
- a secondary utilities area

The frontline default path should stay clean. Store operators should not compete visually with engineering controls.

### 12. Data Flow And Integration Boundaries Stay Stable

Phase 17A is a UX redesign, not a contract rewrite.

The design should preserve the existing flow boundaries:

- login
  - submit auth mutation
  - store session
  - enter tab shell
- dashboard
  - read summary, alerts, and pending confirmations
  - refresh on stream changes
- chat
  - read messages and confirmations
  - use upload-backed media flow
  - submit messages and refresh from stream events
- ledger
  - read inventory and audit logs
  - submit correction and stock-out mutations

The main change is not what the app talks to. The main change is how the app guides the user through those interactions.

### 13. Accessibility And Copy Must Be Part Of The Design, Not A Later Patch

Phase 17A should include baseline accessibility and clarity rules:

- touch targets should stay comfortably tappable
- text contrast should remain high in light mode
- visual emphasis should not rely on color alone
- error and confirmation text should use natural Chinese wording
- page and button labels should reflect frontline mental models instead of internal engineering terms

The redesign should make the app easier to understand under stress, not just nicer to look at.

### 14. Keep Scope Tight

Phase 17A should focus on the frontline mobile shell and avoid turning into a broad product expansion.

It should avoid:

- broker-backed realtime redesign
- a large operator admin portal
- large data-visualization surfaces
- a full dark-mode implementation pass
- ornamental motion systems
- unrelated backend contract changes

If a later phase introduces richer replay surfaces or operator dashboards, they should inherit the design system created here rather than being part of this initial mobile UX milestone.

## Success Criteria

- login, dashboard, chat, and ledger share one coherent semantic design system
- the app feels like a frontline pilot product rather than a developer shell
- guided multimodal entry replaces demo-first controls in the default chat path
- confirmation cards become visually and structurally distinct from ordinary messages
- dashboard hierarchy makes today's priorities and next actions obvious
- ledger actions become structured, readable, and calm
- developer or environment controls remain available without competing with frontline tasks
- current business APIs, auth flow, and session-stream refresh model remain stable

## Out Of Scope

- backend contract redesign
- broker-based realtime architecture changes
- a large admin or analytics console
- complete dark-mode rollout
- advanced motion design
- large branding or illustration systems
- multi-shop enterprise navigation expansion

## Verification Strategy

Phase 17A should be verified in four layers:

1. component and screen tests for:
   - design-system primitives
   - login states
   - dashboard hierarchy and empty states
   - chat confirmation rendering and guided entry dock
   - ledger action panels
2. interaction tests for:
   - loading, success, error, and retry flows
   - confirmation card approve or reject affordances
   - developer controls being visually demoted but still reachable
3. manual Expo device checks for:
   - readability
   - touch comfort
   - navigation clarity
   - form focus and error states
4. pilot-style walkthroughs where a non-developer can:
   - sign in
   - understand the home summary
   - complete one chat-led task
   - understand one confirmation request
   - find and use the ledger

The final measure for this phase is not visual polish alone. It is whether the mobile app becomes understandable and trustworthy in a real frontline workflow.
