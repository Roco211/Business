# Phase 18A Yuanbao Mobile UI Design

## Goal

Refresh the mobile frontline shell so it feels calmer, warmer, and more assistant-like while keeping the existing product structure intact:

- login remains a reliable credential entry point
- the home tab remains store-overview-first
- the workbench remains the place where message and confirmation handling happen

The design target is:

`blend Yuanbao's soft mobile visual language into our store-management workflow without losing the store overview as the primary homepage`

## Why This Phase Is Next

The current mobile app is functional and test-covered, but it still reads more like a lightweight admin panel than a frontline assistant product.

That shows up in three places:

1. the login screen feels like a developer-facing form instead of a trusted entry point
2. the dashboard hierarchy is correct, but the page still looks too rigid and operational
3. the workbench behavior is right, but the shell feels heavier and more mechanical than the assistant-like tone the user wants

The current information architecture is already the right one for the MVP:

- `首页` for store status and next actions
- `工作台` for message and confirmation handling
- `台账` for inventory review and correction

So this phase should be a visual and interaction-language upgrade, not an information-architecture rewrite.

## Scope

This phase changes only:

- `apps/mobile/src/features/auth/screens/LoginScreen.tsx`
- `apps/mobile/src/features/dashboard/screens/DashboardScreen.tsx` and dashboard presentation components
- `apps/mobile/src/features/chat/screens/ChatScreen.tsx` and shell-level chat components
- shared UI primitives and tab shell styling needed to make those screens coherent

This phase does not:

- change backend APIs
- change auth contracts
- change tab destinations
- redesign ledger workflows
- add new business actions
- add new assistant capabilities

## Constraints

Phase 18A should preserve:

- Expo managed mobile shell
- current auth/session/bootstrap flow
- current summary, alert, confirmation, and chat data sources
- current three-tab navigation
- current debug tooling, but visually demoted beneath the frontline path

The redesign can soften the UI tone, but it must not hide connection failures, bootstrap failures, or task failures behind vague "friendly" copy.

## Visual References Interpreted

The Yuanbao references point to a specific kind of mobile polish:

- large breathing room
- soft rounded cards and floating surfaces
- gentle shadows instead of hard panels
- capsule-like controls and input bars
- light top identity bars with small action icons
- guided action modules that feel welcoming instead of tool-heavy

The translation rule for this project is:

`borrow the softness, rhythm, and mobile posture - not Yuanbao's product structure`

The homepage must still prioritize store overview over open-ended conversation.

## Approaches Considered

### 1. Surface Reskin Only

Keep the current layout and mostly swap colors, radii, and shadows.

Pros:

- lowest implementation risk
- fastest to land

Cons:

- still feels like the same admin layout with a prettier coat
- does not deliver enough of the lighter assistant feeling the user asked for

### 2. Balanced Fusion

Keep the current information architecture and backend-driven page structure, but introduce a Yuanbao-inspired visual language across login, dashboard, and workbench shell.

Pros:

- preserves store-overview-first home behavior
- improves trust and warmth without sacrificing business clarity
- creates a coherent cross-screen mobile identity

Cons:

- touches several shared UI primitives
- requires careful hierarchy tuning so the app does not become too chat-like

### 3. Assistant-First Reframe

Push the dashboard and workbench much closer to Yuanbao's conversational framing.

Pros:

- strongest resemblance to the reference

Cons:

- risks weakening store overview as the primary homepage
- requires more behavior and copy restructuring than this phase should take on

## Chosen Approach

Use approach 2: `Balanced Fusion`.

This phase should preserve:

- store overview as the first thing a user sees on `首页`
- existing workbench and confirmation behavior
- current login mechanics

while changing:

- the visual warmth of the shell
- the softness of surfaces and controls
- the tone of page entry
- the clarity of primary versus secondary action hierarchy

## Design

### 1. Shared Visual System Refresh

The redesign should begin with the shared mobile UI layer so the three target screens feel related rather than individually restyled.

#### Palette

The current palette is too cold and system-like for the intended experience.

Phase 18A should move the shell toward:

- a warm off-white app background
- white and cream surface cards
- deep brown or graphite primary text
- muted warm-gray secondary text
- a soft green as the main optimistic and brand accent
- one light lavender or mist accent for recommendation-style surfaces
- softer border tones with less contrast than the current shell

Status mapping must remain truthful:

- success stays clearly readable
- warnings still stand out
- errors remain explicit

#### Radius And Shadow

Rounded shapes are a major part of the Yuanbao feel.

Phase 18A should increase the perceived softness of:

- panels
- input fields
- pills
- bottom navigation container
- hero modules
- confirmation shells

Shadows should shift from "panel with outline" to "light floating surface":

- softer blur
- lower opacity
- less visual dependence on sharp borders

#### Shared Primitive Updates

The main primitives that should be retuned are:

- `AppScreen`
- `SurfaceCard`
- `PrimaryButton`
- `PillActionButton`
- `AppTextField`
- `StatusBadge`

These updates should be enough to let the three target screens share one shell language without re-implementing bespoke styling everywhere.

#### Navigation Treatment

The bottom tab bar should retain the existing three destinations, but visually become lighter and more floating:

- more rounded outer container
- more breathing room above the safe area
- softer background treatment
- stronger active-tab containment
- less hard-toolbar feeling

### 2. Login Screen Refresh

The login screen should become a calm, trusted entry point.

The screen should read in this order:

1. product identity
2. emotional promise
3. credential entry
4. safe, obvious primary action
5. quiet support/trust copy

Recommended composition:

- a soft brand mark or monogram block near the upper half
- product name and a one-line promise below it
- a mid-lower card for credential fields
- one dominant full-width login button
- subtle trust or environment hint below the main action

The backend still requires email and password, so the redesign should not fake a third-party login flow.

Instead, it should:

- keep email and password visible and stable
- visually subordinate the fields beneath the hero identity area
- make the submit button feel like the decisive entry action
- preserve clear failure messaging

Tone should shift from operational wording toward assistant-led reassurance without overpromising new capabilities.

### 3. Dashboard Refresh

The dashboard must remain store-overview-first.

The page should render in five layers:

1. lightweight top identity/status strip
2. main overview hero
3. next-step guidance card
4. quick action module
5. risk and exception sections

#### Top Identity Strip

The top strip should feel closer to a lightweight assistant header than a page title block.

It should contain:

- store-oriented identity copy
- one short current-state sentence
- one compact health/status pill

#### Main Overview Hero

This is the dashboard's visual center of gravity.

It should combine:

- a friendly store-status greeting
- a one-line explanation of today's focus
- four key metrics

The metric set remains:

- 今日入库
- 已完成任务
- 待确认
- 低库存提醒

The redesign goal is not new metrics. It is a clearer, warmer framing of the existing ones.

#### Next-Step Guidance

Below the hero, the dashboard should include one clear recommendation block that answers:

`what should I do next?`

This block should adapt from current data:

- if pending confirmations or low-stock alerts exist, guide the user toward the workbench
- if the store is stable, suggest one lightweight operational action such as voice stock inquiry or photo entry

#### Quick Actions

Quick actions should move from simple text pills toward a more intentional 2x2 module set.

Actions remain:

- 语音查货
- 拍照入库
- 票据识别
- 待确认

Each action should include:

- a short title
- a short descriptive subtitle
- a gentler container style

#### Exception And Risk Sections

Low-stock alerts and pending confirmations remain critical.

They should still render with honest priority, but with calmer presentation:

- lighter background treatment
- compact badges
- shorter summaries
- stronger distinction between section heading and item urgency

### 4. Workbench Shell Refresh

The workbench should become a lighter assistant workspace while preserving existing behavior and streaming semantics.

Phase 18A should not rewrite the workbench's business flow.

It should keep:

- connection status
- message timeline
- guided entry shortcuts
- confirmation cards
- manual text input
- existing debug disclosure structure

#### Header Treatment

`WorkbenchHeader` should move away from a large management-card style.

It should become a lighter identity/status bar with:

- assistant identity
- current workgroup or session title
- one short status sentence
- a compact connection pill

#### Guided Action Dock

The guided entry dock should visually align with the dashboard quick actions:

- soft tiles or capsules
- short subtitles
- calmer grouping

It should feel like "ways to ask for help" rather than developer demo buttons.

#### Message Presentation

The timeline should remain readable, but message cards should feel softer:

- system responses should read like assistant result cards
- owner messages should feel lighter and more conversational
- timestamp and role labels should stay present but visually weaker

#### Confirmation Surfaces

Pending confirmation cards should feel more like floating intervention sheets:

- more rounded outer container
- softer tonal layering
- clearer primary versus secondary actions
- editable field area that feels embedded, not bolted on

#### Composer

The bottom text input area should move toward a pill-like mobile input bar:

- softer outer shell
- stronger sense of one-line entry
- compact supporting actions

### 5. Copy And Tone

Tone goals:

- warmer
- calmer
- more assistant-like
- less engineering-shaped

Truthfulness rules:

- connection failures remain explicit
- bootstrap failures remain explicit
- task failures remain explicit
- degraded does not pretend to mean healthy
- debug affordances stay clearly secondary

### 6. Testing And Verification Strategy

Implementation should update and pass tests that verify:

- login still renders the credential flow with the new hierarchy
- dashboard still renders the core metrics, guidance, quick actions, and risk sections
- workbench still renders header, timeline shell, guided action entry, and confirmation shell
- navigation still preserves the three-tab shell
- shared UI primitive changes do not break existing consumers

Verification should include:

- targeted Jest runs for touched screen suites while iterating
- full `apps/mobile` Jest run before completion
- one visual sanity pass using the existing screenshot-based workflow when practical

## File-Level Design Intent

Expected implementation center of gravity:

- shared shell tokens and primitives in `apps/mobile/src/shared/ui`
- bottom-tab styling in `apps/mobile/src/app/navigation/RootNavigator.tsx`
- login hierarchy in `apps/mobile/src/features/auth/screens/LoginScreen.tsx`
- dashboard shell and dashboard module components in `apps/mobile/src/features/dashboard`
- workbench shell components in `apps/mobile/src/features/chat/components`
- workbench page orchestration in `apps/mobile/src/features/chat/screens/ChatScreen.tsx`

The ledger screen may inherit updated primitives passively, but it should not be redesigned as part of this phase.

## Risks And Mitigations

### Risk 1: The dashboard becomes too assistant-like and loses overview clarity

Mitigation:

- keep the four core metrics visually central
- keep recommendation content singular and operational
- keep risk sections visible below the hero

### Risk 2: The login redesign becomes decorative but less usable

Mitigation:

- preserve visible credential fields
- preserve stable keyboard behavior
- keep one strong full-width primary action

### Risk 3: Shared primitive changes unintentionally degrade other screens

Mitigation:

- keep primitive API shape unchanged where possible
- use focused test updates before broader runs
- avoid ledger-specific restyling during this phase

### Risk 4: The workbench becomes visually softer but operationally less clear

Mitigation:

- preserve clear action hierarchy on confirmation cards
- keep inline notices explicit
- keep connection state copy easy to scan

## Success Criteria

Phase 18A is successful when:

1. the mobile shell feels visibly closer to a polished assistant product
2. the dashboard still unmistakably centers store overview
3. the login, dashboard, and workbench feel like one product family
4. no workflow or status truth is lost in the redesign
5. all relevant mobile tests pass after the UI refresh
