# AI-Native SaaS Backend Rewrite Design

## Context

The backend will move forward with option C: a core architecture rewrite.

This decision was confirmed on 2026-04-18 after reviewing the current backend architecture and its mismatch with the target product model. The accepted architecture principles are persisted in:

`docs/architecture/ai-native-saas-architecture-principles.md`

The current backend has valuable product learning, but its foundational boundary is wrong for the future product:

- `shop` currently acts like the tenant boundary.
- login binds directly to one `shop_id`.
- authorization context is `actor_id + shop_id + role`.
- default shop and default owner bootstrap logic remain part of the auth path.
- many services load records by primary key and infer context afterward.

The target product model is different:

- this is a multi-tenant SaaS platform
- `tenant` is the merchant organization
- one tenant may contain many shops
- one account may join multiple tenants
- users explicitly switch the current tenant and shop
- multimodal AI is the primary interaction and orchestration layer
- deterministic backend tools remain the source of business truth

## Goal

Design a clean backend architecture for an AI-native multi-tenant SaaS system before implementation begins.

This design should become the durable blueprint for the rewrite. It should correct the foundational model before any major backend code is written.

After this design is accepted:

- new backend work should target `/api/v2`
- identity, tenant, shop, context, session, task, AI runtime, ledger, audit, async, and realtime foundations should be rebuilt around the new model
- old `/api/v1` code may be used as reference material, but it should not constrain the new boundaries
- valuable old acceptance scenarios may be migrated into the new test suite

## Options Considered

### Option A: Patch the existing architecture in place

Deliver:

- add a `tenant` table
- retrofit existing `shop` and membership tables
- keep the current auth/session flow and gradually add context switching

Pros:

- lower immediate code churn
- preserves most existing service code
- may produce a quick short-term demo

Cons:

- keeps the wrong mental model alive
- forces compatibility layers around `shop = tenant`
- makes authorization harder to reason about
- makes future AI runtime and cross-tenant context handling fragile

Why not:

- the incorrect boundary is too deep in the current auth, session, and business data model
- patching would preserve naming and behavior that contradict the product model

### Option B: Refactor by domain while preserving most existing structures

Deliver:

- reorganize the current backend into clearer modules
- add explicit tenant context to new paths
- migrate one service at a time

Pros:

- safer than a full rewrite
- allows phased improvements
- keeps old endpoints working longer

Cons:

- still spends effort adapting an architecture built for single-shop assumptions
- delays the moment when the correct tenant and context model becomes mandatory
- risks ending with a half-new, half-old architecture

Why not:

- the business has not entered production scale yet
- the cost of preserving incorrect foundations is higher than rebuilding them now

### Option C: Rebuild the core architecture

Deliver:

- new domain model
- new `/api/v2` surface
- new auth and context selection flow
- new AI runtime pipeline
- new inventory ledger model
- new async and realtime foundations

Pros:

- aligns the architecture with the real product model
- avoids preserving incorrect semantics
- gives multimodal AI and human-in-the-loop workflows first-class support
- creates a clean base for future platform growth

Cons:

- higher immediate design and implementation effort
- requires disciplined migration planning
- requires careful test coverage before cutting over

Chosen approach:

Use option C.

This will be a core architecture rewrite, not a blind restart. We will preserve product learning from the current backend, especially inventory ledger semantics, confirmation workflow experience, task state transitions, multimodal provider abstractions, and audit requirements.

## Chosen Architecture

Use a modular monolith with strict domain boundaries, reliable outbox-based async processing, and event-driven projections.

This is intentionally not an early microservice design.

Reasons:

- the domain model is still being shaped
- one deployable backend keeps iteration fast
- strict module boundaries are enough for the current stage
- future service extraction can follow domain seams once the product stabilizes

The backend should be organized around these domains:

1. `identity_access`
2. `tenant_shop`
3. `workspace_context`
4. `conversation_runtime`
5. `inventory_ledger`
6. `media_ai_platform`
7. `audit_governance`
8. `async_realtime`

## Domain Boundaries

### identity_access

Responsibilities:

- account identity
- login sessions
- password and auth token lifecycle
- tenant membership
- shop access
- role and permission evaluation

Owns:

- `account`
- `auth_session`
- `tenant_membership`
- `shop_access`
- role and permission definitions

Does not own:

- tenant commercial profile
- shop business configuration
- inventory data
- AI task execution

### tenant_shop

Responsibilities:

- tenant creation and lifecycle
- shop creation and lifecycle
- tenant-level settings
- shop-level settings

Owns:

- `tenant`
- `shop`
- tenant configuration
- shop configuration

Does not own:

- user authentication
- role evaluation
- conversation state
- inventory ledger events

### workspace_context

Responsibilities:

- explicit current tenant and shop selection
- context session creation
- permission snapshot creation
- context token validation

Owns:

- `context_session`
- context validation policies

Does not own:

- account credentials
- tenant membership persistence
- business writes

### conversation_runtime

Responsibilities:

- conversation sessions
- messages
- task runs
- clarification flow
- confirmation flow
- task state transitions
- runtime orchestration

Owns:

- `conversation_session`
- `message`
- `task_run`
- `confirmation`
- runtime state machine

Does not own:

- model provider clients directly
- inventory truth writes directly
- user authorization rules

### inventory_ledger

Responsibilities:

- tenant-level product catalog
- shop-level stock ledger
- stock projections
- stock-in, stock-out, and correction tools

Owns:

- `inventory_item`
- `inventory_stock_snapshot`
- `inventory_ledger_event`
- inventory tool implementations

Does not own:

- AI interpretation
- user sessions
- media files

### media_ai_platform

Responsibilities:

- media assets
- document extraction
- ASR, OCR, Vision, LLM, retrieval, and evaluation capabilities
- model call logging
- prompt and schema version tracking

Owns:

- `media_asset`
- `document`
- `model_call_log`
- provider abstractions
- prompt and schema registry

Does not own:

- business truth commits
- permission granting
- inventory ledger writes

### audit_governance

Responsibilities:

- audit log creation
- risk policy
- explainability records
- governance reporting

Owns:

- `audit_log`
- risk policy definitions
- governance events

Does not own:

- the underlying business operation itself
- websocket transport

### async_realtime

Responsibilities:

- reliable outbox
- worker dispatch
- projection processing
- realtime stream fanout
- replay and catch-up

Owns:

- `outbox_event`
- worker queues
- projection dispatch
- websocket fanout adapters

Does not own:

- business domain decisions
- AI prompt execution
- authorization rules

## Core Data Model

### account

Purpose:

Platform-level human login identity.

Key fields:

- `account_id`
- `email`
- `display_name`
- `password_hash`
- `status`
- `created_at`
- `updated_at`

Ownership:

- platform-level
- does not belong to a tenant

### tenant

Purpose:

Merchant organization and first business data boundary.

Key fields:

- `tenant_id`
- `name`
- `slug`
- `status`
- `plan_code`
- `owner_account_id`
- `created_at`
- `updated_at`

Ownership:

- first-class business boundary
- most business data must include `tenant_id`

### shop

Purpose:

Store or operating unit under a tenant.

Key fields:

- `shop_id`
- `tenant_id`
- `code`
- `name`
- `locale`
- `timezone`
- `status`
- `created_at`
- `updated_at`

Ownership:

- always belongs to one tenant
- never represents the tenant itself

### tenant_membership

Purpose:

Account membership inside a tenant.

Key fields:

- `membership_id`
- `tenant_id`
- `account_id`
- `role_key`
- `status`
- `joined_at`
- `updated_at`

Ownership:

- tenant-scoped
- expresses organization-level role

### shop_access

Purpose:

Which shops a tenant member can access.

Key fields:

- `shop_access_id`
- `tenant_id`
- `shop_id`
- `membership_id`
- `access_level`
- `status`
- `created_at`

Ownership:

- tenant-scoped and shop-scoped
- must enforce that `shop.tenant_id == shop_access.tenant_id`

### auth_session

Purpose:

Account login session.

Key fields:

- `auth_session_id`
- `account_id`
- `refresh_token_hash`
- `status`
- `expires_at`
- `revoked_at`
- `last_seen_at`
- `created_at`

Ownership:

- account-scoped
- must not bind directly to a tenant or shop

### context_session

Purpose:

Explicit current tenant and shop working context.

Key fields:

- `context_session_id`
- `auth_session_id`
- `account_id`
- `tenant_id`
- `shop_id`
- `membership_id`
- `permission_snapshot`
- `expires_at`
- `created_at`

Ownership:

- account-scoped
- tenant-scoped
- usually shop-scoped

### conversation_session

Purpose:

Business task context, not just chat history.

Key fields:

- `session_id`
- `tenant_id`
- `shop_id`
- `session_type`
- `title`
- `status`
- `initiated_by_account_id`
- `created_at`
- `updated_at`

Ownership:

- tenant-scoped
- shop-scoped when tied to a store operation

### message

Purpose:

User, AI, system, or tool message inside a business session.

Key fields:

- `message_id`
- `tenant_id`
- `shop_id`
- `session_id`
- `actor_type`
- `actor_id`
- `message_kind`
- `payload_json`
- `client_request_id`
- `created_at`

Ownership:

- tenant-scoped
- shop-scoped when the session is shop-scoped

### task_run

Purpose:

Runtime workflow state for an interpreted business task.

Key fields:

- `task_run_id`
- `tenant_id`
- `shop_id`
- `session_id`
- `source_message_id`
- `intent_type`
- `status`
- `risk_level`
- `trace_id`
- `result_summary`
- `error_code`
- `created_at`
- `updated_at`
- `completed_at`

Ownership:

- tenant-scoped
- shop-scoped when task affects shop business data

### confirmation

Purpose:

Human approval boundary before risky or uncertain business action.

Key fields:

- `confirmation_id`
- `tenant_id`
- `shop_id`
- `task_run_id`
- `confirmation_type`
- `status`
- `draft_payload`
- `approved_by_account_id`
- `resolution_payload`
- `created_at`
- `resolved_at`

Ownership:

- tenant-scoped
- shop-scoped when confirming shop business action
- must not rely only on `task_run_id` for tenant boundary

### inventory_item

Purpose:

Tenant-level product catalog item.

Key fields:

- `inventory_item_id`
- `tenant_id`
- `sku`
- `name`
- `barcode`
- `default_unit`
- `status`
- `created_at`
- `updated_at`

Ownership:

- tenant-scoped
- not shop-scoped by default

Reason:

The same merchant should not create separate product identities for every shop unless there is a specific business reason.

### inventory_stock_snapshot

Purpose:

Shop-level current stock projection.

Key fields:

- `snapshot_id`
- `tenant_id`
- `shop_id`
- `inventory_item_id`
- `current_quantity`
- `current_price`
- `low_stock_threshold`
- `updated_at`

Ownership:

- tenant-scoped
- shop-scoped
- projection, not sole source of truth

### inventory_ledger_event

Purpose:

Immutable stock-changing business fact.

Key fields:

- `event_id`
- `tenant_id`
- `shop_id`
- `inventory_item_id`
- `event_type`
- `quantity_delta`
- `quantity_after`
- `unit`
- `price`
- `source_type`
- `source_id`
- `reason`
- `created_by_account_id`
- `occurred_at`

Ownership:

- tenant-scoped
- shop-scoped
- source of inventory truth

### media_asset

Purpose:

Tenant-owned uploaded media.

Key fields:

- `media_asset_id`
- `tenant_id`
- `shop_id`
- `uploaded_by_account_id`
- `media_type`
- `content_type`
- `storage_key`
- `sha256`
- `status`
- `created_at`

Ownership:

- tenant-scoped
- shop-scoped when uploaded inside shop context

### document

Purpose:

Structured extraction result from media.

Key fields:

- `document_id`
- `tenant_id`
- `shop_id`
- `media_asset_id`
- `document_type`
- `extraction_status`
- `extracted_fields`
- `confidence_summary`
- `created_at`
- `updated_at`

Ownership:

- tenant-scoped
- shop-scoped when related to shop operation

### model_call_log

Purpose:

Observable record of AI capability usage.

Key fields:

- `model_call_id`
- `tenant_id`
- `shop_id`
- `task_run_id`
- `capability`
- `provider`
- `model`
- `prompt_version`
- `schema_version`
- `latency_ms`
- `cost`
- `confidence`
- `used_fallback`
- `error_code`
- `created_at`

Ownership:

- tenant-scoped
- shop-scoped when associated with shop operation

### audit_log

Purpose:

Explainable record of critical system and business actions.

Key fields:

- `audit_log_id`
- `tenant_id`
- `shop_id`
- `actor_id`
- `session_id`
- `task_run_id`
- `action`
- `target_type`
- `target_id`
- `metadata_json`
- `created_at`

Ownership:

- tenant-scoped
- shop-scoped when related to shop action

### outbox_event

Purpose:

Reliable async event dispatch record.

Key fields:

- `outbox_event_id`
- `tenant_id`
- `shop_id`
- `aggregate_type`
- `aggregate_id`
- `event_type`
- `payload_json`
- `status`
- `attempt_count`
- `available_at`
- `created_at`

Ownership:

- tenant-scoped when event belongs to tenant data
- shop-scoped when event belongs to shop data

## Authentication and Authorization

Authentication and context selection are separate.

### Login flow

1. `POST /api/v2/auth/login`
2. System validates account credentials.
3. System creates `auth_session`.
4. Response proves account identity only.
5. Response does not select tenant or shop.

### Tenant and shop selection flow

1. `GET /api/v2/me/tenants`
2. User chooses a tenant.
3. `GET /api/v2/tenants/{tenant_id}/shops`
4. User chooses a shop if the operation requires shop context.
5. `POST /api/v2/context/select`
6. System validates membership and shop access.
7. System creates `context_session`.
8. Business APIs use the context token or context session reference.

### Authorization model

Use:

- tenant membership
- shop access
- role-based permissions
- risk policy
- action-specific checks

The runtime must not allow AI-generated tool calls to bypass permission checks.

## Execution Context

Every business operation must receive an explicit context.

Minimum context:

```text
account_id
tenant_id
shop_id
membership_id
role_key
permissions
context_session_id
session_id
input_channel
locale
timezone
trace_id
```

Rules:

- service methods should accept context, not only object IDs
- database queries should be scoped by `tenant_id`
- shop-scoped actions should also scope by `shop_id`
- context must be established before runtime interpretation, tool execution, confirmation, and ledger commit

## AI Runtime Workflow

The runtime is a workflow engine for uncertain multimodal business input.

Canonical flow:

```text
capture
interpret
assess
clarify
draft
confirm
execute
commit
correct
```

### capture

Persist user input:

- text
- audio
- image
- receipt
- document

Outputs:

- `message`
- optional `media_asset`
- optional `document`
- initial `task_run`

### interpret

AI converts multimodal input into structured candidates:

- intent
- extracted fields
- confidence
- ambiguity
- missing fields
- possible tool call

Outputs:

- interpretation payload
- `model_call_log`

### assess

System evaluates:

- confidence
- missing fields
- risk level
- account permissions
- tenant policy
- shop policy

Possible outcomes:

- answer directly
- ask clarification
- create draft
- require confirmation
- reject
- fail

### clarify

If required information is missing, the system asks a targeted question.

Examples:

- which product variant?
- which shop?
- how many units?
- should the system record price?

Clarification is a first-class task state, not a generic failure.

### draft

Create a structured proposed business action.

Drafts may include:

- matched item candidate
- extracted receipt lines
- proposed stock delta
- required fields
- model confidence
- reason for confirmation

### confirm

Create `confirmation` for write operations, risky actions, and low-confidence actions.

Confirmation should show:

- proposed action
- extracted fields
- missing or uncertain fields
- confidence summary
- business impact
- approval and rejection options

### execute

Deterministic backend tools execute approved actions.

AI does not mutate business truth directly.

### commit

Commit:

- business ledger event
- projection update
- audit log
- outbox event
- system result message

This should be transactional where possible.

### correct

Errors are corrected by appending correction events.

The system should not silently overwrite historical facts.

## Task State Machine

Suggested `task_run.status` values:

- `captured`
- `interpreting`
- `needs_clarification`
- `drafted`
- `awaiting_confirmation`
- `executing`
- `committed`
- `rejected`
- `failed`
- `corrected`

Rules:

- write operations must not move to `committed` without deterministic tool execution
- user rejection must be explicit
- correction must link back to the original event or task when possible

## Tool Boundary

Tools must be structured and governed.

Each tool definition should include:

- tool name
- input schema
- output schema
- required context
- required permissions
- risk level
- idempotency key
- audit behavior
- mutation behavior
- error codes

Initial tool families:

- `inventory.query`
- `inventory.stock_in.create_draft`
- `inventory.stock_in.commit`
- `inventory.stock_out.create_draft`
- `inventory.stock_out.commit`
- `inventory.correction.commit`
- `catalog.item.match`
- `catalog.item.create`
- `document.receipt.extract`
- `session.message.append_system_result`

## API Surface

New backend work should target `/api/v2`.

### Public auth

Endpoints:

- `POST /api/v2/auth/login`
- `POST /api/v2/auth/logout`
- `POST /api/v2/auth/refresh`

### Identity and context

Endpoints:

- `GET /api/v2/me`
- `GET /api/v2/me/tenants`
- `GET /api/v2/tenants/{tenant_id}/shops`
- `POST /api/v2/context/select`
- `GET /api/v2/context/current`

### Conversation runtime

Endpoints:

- `POST /api/v2/sessions`
- `GET /api/v2/sessions`
- `POST /api/v2/sessions/{session_id}/messages`
- `GET /api/v2/sessions/{session_id}/messages`
- `GET /api/v2/task-runs/{task_run_id}`
- `GET /api/v2/confirmations`
- `POST /api/v2/confirmations/{confirmation_id}/approve`
- `POST /api/v2/confirmations/{confirmation_id}/reject`

### Media and documents

Endpoints:

- `POST /api/v2/media-assets`
- `POST /api/v2/media-assets/{media_asset_id}/complete`
- `POST /api/v2/documents`
- `GET /api/v2/documents/{document_id}`

### Operations

Endpoints:

- `GET /api/v2/inventory/items`
- `GET /api/v2/inventory/stock`
- `GET /api/v2/inventory/events`
- `POST /api/v2/inventory/corrections`
- `GET /api/v2/dashboard/summary`
- `GET /api/v2/alerts`

### Admin and internal

Endpoints:

- `GET /api/v2/internal/provider-health`
- `GET /api/v2/internal/worker-health`
- `POST /api/v2/internal/projections/replay`
- `GET /api/v2/internal/model-calls`

## Async and Realtime

Important async work should use an outbox-backed flow.

Write transaction:

1. persist business object or task state
2. persist `outbox_event`
3. commit transaction

Worker flow:

1. dispatcher picks pending outbox event
2. worker executes task
3. worker writes result, audit, projection, and follow-up outbox events
4. notification worker pushes realtime updates

Realtime principles:

- database events are truth
- websocket is delivery
- clients must support replay and catch-up
- multi-instance fanout should use Redis pub/sub or a message bus
- connection memory should not be the only delivery state

## Observability and AI Evaluation

AI is the competitive core, so AI performance must be measurable.

Track:

- intent accuracy
- extraction accuracy
- clarification rate
- confirmation approval rate
- confirmation rejection rate
- correction rate
- low-confidence rate
- provider latency
- provider cost
- fallback rate
- task failure rate
- prompt version performance
- schema version performance

Every model call should emit a `model_call_log` record with provider, model, prompt version, schema version, latency, cost, confidence, fallback status, and error state.

## Migration Strategy

### Phase 0: Principle freeze

Status:

- complete

Output:

- `docs/architecture/ai-native-saas-architecture-principles.md`

### Phase 1: New v2 skeleton

Build:

- new module layout
- `/api/v2` router
- shared response envelope
- execution context primitives
- base test fixtures

Do not:

- extend old `/api/v1` for new architecture work

### Phase 2: Identity, tenant, shop, and context

Build:

- `account`
- `tenant`
- `shop`
- `tenant_membership`
- `shop_access`
- `auth_session`
- `context_session`
- login
- tenant listing
- shop listing
- context selection

Success criteria:

- one account can belong to multiple tenants
- one tenant can have multiple shops
- business APIs require explicit context

### Phase 3: Conversation and runtime skeleton

Build:

- conversation sessions
- messages
- task runs
- initial runtime state machine
- clarification state
- confirmation state

Success criteria:

- a message creates a tenant-scoped, shop-scoped task
- the task can pause for clarification or confirmation

### Phase 4: Inventory ledger v2

Build:

- tenant-level catalog items
- shop-level stock snapshots
- inventory ledger events
- stock-in commit tool
- stock-out commit tool
- correction tool

Success criteria:

- current stock is projection
- ledger event is truth
- correction appends event instead of overwriting history

### Phase 5: Media and AI platform

Build:

- media assets
- documents
- ASR, OCR, Vision, and LLM capability interfaces
- model call logs
- prompt and schema versioning

Success criteria:

- multimodal input is captured and interpreted with measurable AI metadata

### Phase 6: Outbox, workers, projections, realtime

Build:

- outbox table
- dispatcher worker
- runtime worker
- projection worker
- notification worker
- websocket replay

Success criteria:

- runtime dispatch is reliable
- realtime updates are derived from committed events

### Phase 7: Scenario migration

Migrate:

- voice stock query
- voice stock in
- photo stock query
- photo stock in
- receipt OCR stock in
- manual correction
- audit browsing
- low-stock alerts

Success criteria:

- old valuable scenarios pass on `/api/v2`

### Phase 8: v1 deprecation

Remove or quarantine:

- default shop bootstrap from auth
- default owner bootstrap from auth
- old shop-as-tenant assumptions
- old session stream singleton assumptions

## Reuse, Rewrite, Discard

Reuse as reference:

- inventory ledger concept
- confirmation workflow concept
- task-run lifecycle learning
- provider gateway abstraction learning
- existing acceptance scenario coverage

Rewrite:

- identity and access
- tenant and shop model
- context selection
- conversation session model
- runtime pipeline
- inventory model
- outbox and async processing
- AI observability

Discard:

- `shop` as tenant boundary
- login binding directly to one shop
- default shop and default owner auth bootstrap
- primary-key lookup followed by context inference
- in-memory-only realtime delivery assumptions

## Testing Strategy

Test the new architecture through behavior, not old implementation shape.

Initial acceptance tests:

- account can belong to two tenants
- tenant can contain two shops
- context selection rejects inaccessible shop
- business API rejects requests without context
- AI task can enter `needs_clarification`
- AI task can enter `awaiting_confirmation`
- confirmed stock-in writes ledger event, stock projection, audit log, and outbox event
- rejected confirmation does not mutate inventory
- correction appends a correction event
- model call is logged with provider and schema metadata
- cross-tenant object access is rejected

## Non-Goals

This design does not implement:

- UI rewrite
- billing
- plugin marketplace
- multi-service deployment
- full financial accounting
- supplier ordering automation
- full data migration tooling

These may be added later after the core AI-native SaaS backend foundation is stable.

## Open Decisions

These decisions can be made during implementation planning:

- exact token format for context sessions
- exact permission key names
- exact role presets
- Redis versus database polling for first outbox dispatcher
- whether first v2 implementation uses MySQL only or keeps SQLite-friendly tests
- exact prompt registry storage model

These open decisions do not change the accepted architecture direction.

## Acceptance Criteria for This Design

The design is accepted if it satisfies these points:

- tenant is a first-class boundary
- shop is only a tenant-owned business unit
- account can belong to multiple tenants
- context selection is explicit
- AI is the primary interaction and orchestration layer
- AI cannot directly mutate business truth
- uncertainty, clarification, confirmation, correction, and audit are foundational
- inventory truth is event-ledger based
- async dispatch uses reliable outbox semantics
- realtime delivery is a projection of committed events
- the old backend is treated as reference, not constraint

