# AI-Native SaaS Architecture Principles

Date: 2026-04-18
Status: Accepted
Scope: Backend rewrite foundation

## Decision

We will rebuild the backend using option C: a core architecture rewrite.

This is not a blind rewrite from zero. We will preserve useful product learning from the current MVP, especially inventory ledger thinking, confirmation workflows, task state transitions, multimodal provider abstractions, and audit requirements. We will discard the old foundational boundaries where they conflict with the target SaaS model.

The target product is an AI-native multi-tenant SaaS business operating system for small merchants. Multimodal AI is the primary interaction and orchestration layer. Deterministic backend tools remain the source of business truth.

## Highest-Level Principles

1. AI understands and orchestrates. The system constrains and commits.
2. Tenant is the first business boundary. Shop is a business unit under a tenant.
3. Every business operation must execute inside an explicit account, tenant, shop, permission, and session context.
4. AI may propose intents and tool calls, but AI must not directly mutate business truth.
5. Uncertainty is a normal workflow state, not an exception.
6. High-risk or uncertain actions require clarification, confirmation, rejection, or correction paths.
7. Critical business facts must be evented, auditable, and explainable.
8. Model providers are replaceable. AI capability, prompts, schemas, evaluations, cost, and latency must be observable.

## Product Positioning

This project is not a traditional inventory system with an AI assistant attached.

It is an AI-native SaaS application where users primarily interact through:

- voice
- images
- receipts and OCR
- text conversation
- confirmation cards
- concise operational surfaces

Forms, admin screens, APIs, and CLI tools are supporting surfaces. They are useful for setup, debugging, operations, and fallback, but they are not the main product differentiator.

## Multi-Tenant Model

The future SaaS hierarchy is:

```text
Platform
Account
Tenant
Shop
Membership
Role / Permission
Business Data
```

Definitions:

- Account: a human login identity. One account may belong to multiple tenants.
- Tenant: a merchant organization or commercial account.
- Shop: a store or operating unit under one tenant.
- Tenant membership: an account's role inside a tenant.
- Shop access: which shops a tenant member may operate or view.

Required implications:

- Do not use `shop_id` as the tenant boundary.
- Do not bind login sessions only to one shop.
- Do not rely on primary-key lookup followed by context inference for authorization.
- Business tables should carry `tenant_id` by default.
- Shop-scoped tables should also carry `shop_id`.
- Cross-tenant data leakage must be treated as a P0 class risk.

## Explicit Execution Context

Every business operation must receive an explicit execution context.

Minimum context:

```text
actor_id
tenant_id
shop_id
membership_id
role
permissions
session_id
input_channel
locale
timezone
trace_id
```

The system must establish context before running business logic. Services should not accept only object IDs and reconstruct authority from database relationships unless the query is explicitly scoped by the execution context.

## AI-Native Workflow

The canonical workflow is:

```text
Capture input
Interpret multimodal intent
Assess confidence and risk
Clarify missing or ambiguous fields
Create a structured draft
Request confirmation when needed
Execute deterministic tools
Commit ledger and audit facts
Publish task/session events
Allow correction without rewriting history
```

AI output is advisory until it crosses a deterministic tool boundary.

## Uncertainty Handling

AI input is probabilistic. The system must support uncertainty as first-class state.

Common states:

- captured: the user input has entered the system.
- interpreted: AI has produced a candidate intent or extraction.
- needs_clarification: required fields are missing or ambiguous.
- needs_confirmation: the proposed write action is ready but requires human approval.
- rejected: the user or policy rejected the proposed action.
- committed: deterministic tools wrote the business fact.
- corrected: a later correction event adjusted the business truth.

The system should not hide low confidence. It should surface the reason and guide the next safe action.

## Human-in-the-Loop Risk Policy

Risk policy controls whether the system answers, asks, confirms, or blocks.

Suggested levels:

- Low-risk read: answer directly when confidence is sufficient.
- Low-risk suggestion: provide recommendation without mutation.
- Medium-risk write: require confirmation before commit.
- High-risk write: require strong confirmation or elevated role.
- Uncertain action: ask a clarifying question before confirmation.
- Unauthorized action: block and explain the permission boundary.

The closer an action gets to business truth, the more deterministic control is required.

## Tool-Governed Execution

Tools must be structured, typed, permission-aware, idempotent, and auditable.

Each tool should define:

- input schema
- output schema
- required context
- required permissions
- risk level
- idempotency key
- possible failure reasons
- audit behavior
- whether it mutates business truth

AI may choose and propose a tool invocation. The backend validates and executes it.

## Ledger and Audit Truth

Current state should not be the only source of truth.

For inventory and similar business domains:

```text
initial state + stock-in events - stock-out events + correction events = current state
```

Principles:

- Use ledger events for critical business changes.
- Use projections or snapshots for fast reads.
- Do not silently overwrite historical facts.
- Corrections should append new events.
- Audit logs must connect actor, input, AI interpretation, confirmation, tool execution, and resulting business facts.

## Session as Business Context

A session is not just a chat history.

A session is a business task context. It may contain:

- user messages
- uploaded media
- AI interpretations
- tool-call drafts
- clarifying questions
- confirmations
- task state changes
- result cards
- committed business events
- audit references

Session design must support multiple session types, such as shop workgroup, receipt processing, stocktaking, correction, and replenishment review.

## AI Capability Architecture

AI capabilities should be provider-agnostic and versioned.

Capability categories:

- ASR: speech to text
- Vision: product, shelf, and image recognition
- OCR: receipt and document extraction
- LLM reasoning: intent, planning, clarification, summarization
- Retrieval: product matching, aliases, historical context, tenant knowledge
- Evaluation: quality, confidence, regression, and cost tracking

For each capability, track:

- provider
- model
- prompt version
- schema version
- confidence
- latency
- cost
- fallback usage
- failure reason
- human correction outcome

The core architecture must not depend on a single AI provider.

## Memory Boundaries

AI memory must be scoped.

Memory types:

- short-term session memory
- shop business memory
- tenant organization memory
- long-term learning memory

Rules:

- Tenant memory must never leak across tenants.
- Shop-specific corrections should not automatically affect other shops unless promoted by policy.
- Cross-tenant accounts must switch context explicitly.
- Retrieval must always be scoped by tenant and, when needed, shop.

## Authorization Separation

AI does not grant permission.

The authorization system must decide:

- whether the actor belongs to the tenant
- whether the actor can access the shop
- whether the actor can perform the requested action
- whether the action needs confirmation
- whether the action requires an elevated role

AI can explain the action. The policy system decides whether it is allowed.

## Async and Event Reliability

Multimodal AI workflows are naturally asynchronous.

The architecture should separate:

- commands: requested actions
- tasks: asynchronous work
- events: committed facts
- outbox: reliable event dispatch
- workers: background processing
- projections: query-optimized read models

Do not rely on best-effort in-memory dispatch for important workflows.

## Real-Time Experience

Real-time delivery is a projection of committed facts.

The desired order is:

```text
commit business event
write outbox event
deliver over websocket / push / polling
client updates UI
```

Websocket delivery is not the business truth. Database events are the truth.

## Observability and Evaluation

Because AI is the competitive core, the system must measure AI quality.

Track at minimum:

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

AI quality that cannot be measured cannot be improved reliably.

## Cost and Latency Budgeting

Not every operation should use the most expensive model.

Rules:

- Simple inventory reads should not require LLM calls when deterministic data is enough.
- Product matching should prefer scoped search before expensive reasoning.
- OCR and Vision results should be cached and reused.
- Repeated processing of identical media should be avoided.
- Model selection should depend on risk, ambiguity, and expected business value.

## CLI Positioning

CLI tools are allowed and useful during backend-first development.

CLI should support:

- tenant/shop setup
- local smoke tests
- task replay
- provider evaluation
- data repair
- operational diagnostics

CLI is not the end-user product surface. The differentiating product surface remains multimodal AI interaction.

## Rewrite Rules

During the option C rewrite:

- Preserve product learning, not old boundaries.
- Rebuild identity, tenant, shop, membership, role, context, session, task, event, and ledger foundations.
- Reuse current code only when it fits the new boundaries.
- Treat the existing implementation as a reference, not as a constraint.
- Convert valuable old tests into new acceptance tests when possible.
- Avoid compatibility layers that preserve incorrect domain concepts.

## Non-Negotiables

These decisions should not be revisited casually:

- The product is AI-native.
- Multimodal AI is a core differentiator.
- Tenant is not shop.
- Account can belong to multiple tenants.
- Tenant can contain multiple shops.
- Context switching is explicit.
- AI cannot directly mutate business truth.
- Uncertainty requires workflow support.
- Confirmation, correction, and audit are foundational.
- Critical business facts must be explainable.

