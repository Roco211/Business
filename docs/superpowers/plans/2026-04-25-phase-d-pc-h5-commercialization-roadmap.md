# Phase D PC/H5 Frontend + Backend Commercialization Roadmap

> For agentic workers: REQUIRED SUB-SKILL when executing this roadmap: use subagent-driven-development for independent backend/frontend/testing slices, or executing-plans for inline checkpoint execution.

Goal: Bring Business from backend-ready MVP to a PC/H5 commercial pilot that can be used by real small-shop owners for dashboard, goods, inventory, AI assistant, confirmations, and basic operational decisions.

Architecture: Keep the backend as a modular FastAPI monolith with V2 tenant/shop isolation and confirmation-first AI actions. Add a PC/H5 React app under apps/h5, backed by BFF-style dashboard endpoints that aggregate existing inventory, ledger, confirmation, task, and analytics data. Use Docker/preflight/CI as the release gate.

Tech Stack: FastAPI, SQLAlchemy, SQLite for demo/pilot, PostgreSQL for commercial deployment, React + Vite + TypeScript for PC/H5, SSE for AI chat streaming, Docker, GitHub Actions.

---

## Current Baseline

Backend status:
- V2 auth/context/tenant/shop isolation: ready.
- Inventory item CRUD + soft delete: ready.
- Stock-in/stock-out formal APIs: ready.
- Inventory ledger/snapshot: ready.
- Dashboard summary: partially ready; supports revenue summary, sales ranking, low stock, daily revenue series, pending low-stock/recent transaction counts.
- Chat/Voice/Photo AI inventory writes: confirmation-first and approval commits ledger/snapshot.
- Single item audit trail: ready.
- Docker acceptance and backend preflight: ready.
- Provider trial preflight: ready, opt-in only.

Current PC/H5 status:
- No formal commercial PC/H5 frontend exists yet.
- Existing apps/mobile is Expo/React Native, not a PC management console.
- Existing AI_Store_Manager_UI.html and showcase_app are prototype/showcase material, not production PC frontend.
- dashboard.jpg is the high-fidelity target direction.

Commercialization principle:
- Do not fake unsupported domains as real data.
- First commercial pilot should expose only truthful backend-backed modules.
- Unsupported domains such as customers/orders/marketing/after-sales/finance can appear as disabled or "即将上线", but should not show fake operational numbers.

---

## Phase D0: Product Contract Lockdown

Objective: Freeze the first commercial PC/H5 scope so frontend and backend do not drift.

Scope:
- Use dashboard.jpg as visual direction, but adapt metrics to current backend reality.
- Keep AI-native concept: AI运营协调官 global input, today top priorities, AI employee role cards, suggestions with evidence, confirmation-first action flow.

MVP dashboard modules:
1. Top navigation / shop identity.
2. KPI cards:
   - 今日销售额
   - 今日销售笔数
   - 低库存商品
   - 待确认任务
3. AI employee cards:
   - AI运营协调官
   - 营业数据员
   - 库存守护员
   - 商品档案员
   - 经营策略顾问
4. AI运营协调官全局输入框.
5. 今日最重要的 3 件事.
6. AI 智能建议.
7. 今日工作动态.
8. 待办事项.
9. 商品管理入口.
10. 库存管理入口.
11. AI 助手入口.

Non-MVP modules:
- 客户管理: disabled/coming soon.
- 营销中心: disabled/coming soon.
- 财务对账: disabled/coming soon.
- 售后申请: disabled/coming soon until order/after-sale domain exists.
- 客服小助手: disabled/coming soon until customer-service conversation domain exists.

Deliverables:
- docs/superpowers/specs/pc-h5-dashboard-contract.md
- API contract examples for every PC dashboard field.
- Empty/error/loading state definitions.

Acceptance:
- Every visible number maps to a backend field or a clearly marked coming-soon state.
- No unsupported fake order/customer/consultation metric is displayed as real.

---

## Phase D1: Backend BFF Endpoints for PC Dashboard

Objective: Add frontend-friendly BFF endpoints so the PC dashboard does not need to orchestrate many low-level APIs.

Create or extend backend endpoints:

1. GET /api/v2/pc-dashboard/overview
Returns:
- store
- user
- kpis
- ai_employees
- top_priorities
- suggestions
- activities
- todos
- notifications

2. GET /api/v2/ai-employees/summary
Returns role cards backed by current metrics.

3. GET /api/v2/ai-suggestions
Initially rule-generated from existing data:
- low stock
- pending confirmations
- hot-selling item inventory risk
- stale/no recent sales warning if supported by ledger data

4. GET /api/v2/work-activities
Aggregates:
- V2TaskRun
- V2Confirmation
- V2InventoryLedgerEvent
- V2AuditLog if useful

5. GET /api/v2/todos/summary
Aggregates:
- pending inventory confirmations
- low-stock alerts
- inventory data issues

Test requirements:
- HTTP tests for tenant/shop isolation.
- Deleted/inactive items excluded from current dashboard views.
- Pending confirmations scoped to current account/tenant/shop.
- Suggestions include evidence and action metadata.
- High-risk suggestion actions do not mutate state directly.

Files likely touched:
- backend/app/api/v2/routes/pc_dashboard.py
- backend/app/services/v2_pc_dashboard.py
- backend/app/contracts/v2/pc_dashboard.py
- backend/app/api/v2/router registration file if present
- backend/tests/test_v2_pc_dashboard_overview_http_flow.py
- backend/tests/test_v2_pc_dashboard_isolation_http_flow.py

Validation:
- PYTHONPATH=backend pytest -q backend/tests/test_v2_pc_dashboard_overview_http_flow.py backend/tests/test_v2_pc_dashboard_isolation_http_flow.py
- RUN_DOCKER_ACCEPTANCE=0 RUN_PROVIDER_TRIAL_PREFLIGHT=0 bash backend/scripts/run_backend_preflight.sh

Commit:
- feat: add pc dashboard bff endpoints

---

## Phase D2: Create PC/H5 App Skeleton

Objective: Build the formal PC/H5 frontend app under apps/h5.

Create:
- apps/h5/package.json
- apps/h5/vite.config.ts
- apps/h5/tsconfig.json
- apps/h5/index.html
- apps/h5/src/main.tsx
- apps/h5/src/App.tsx
- apps/h5/src/routes.tsx
- apps/h5/src/styles/tokens.css
- apps/h5/src/styles/global.css

Core layout:
- Left sidebar matching dashboard.jpg direction.
- Top header with shop/user context.
- Responsive PC-first layout, minimum width optimized around 1280px.
- Coming-soon state for unsupported nav items.

Frontend rules:
- No emoji icons in final UI; use pure SVG/line icons or text symbols consistent with user preference.
- Clean white Doubao-like style, but PC SaaS layout.
- AI employee badges and role labels must match Business role naming.
- Loading/skeleton/error/empty states must exist from the start.

Validation:
- cd apps/h5 && npm install
- cd apps/h5 && npm run build

Commit:
- feat: scaffold pc h5 app

---

## Phase D3: Auth + Context Real API Integration

Objective: Make PC/H5 login and context selection work against current backend.

Frontend capabilities:
- Login by phone_code demo mode using 888888.
- Login by email/password if already supported.
- Store access token safely in frontend state/localStorage with clear logout behavior.
- Fetch tenants.
- Fetch shops.
- Select tenant/shop context.
- Attach both headers for protected APIs:
  - Authorization: Bearer <access_token>
  - X-Context-Token: <context_session_id>

Files likely created:
- apps/h5/src/api/client.ts
- apps/h5/src/api/auth.ts
- apps/h5/src/stores/authStore.ts
- apps/h5/src/pages/LoginPage.tsx
- apps/h5/src/pages/ContextSelectPage.tsx
- apps/h5/src/components/ProtectedRoute.tsx

Acceptance:
- User can login and reach dashboard.
- Refresh page keeps usable session if token/context still valid.
- 401 clears invalid local session and redirects to login.
- Wrong context header name is never used.

Validation:
- npm run build
- Browser manual test against Docker backend on 8001.
- Optional Playwright smoke: login -> context select -> dashboard visible.

Commit:
- feat: connect h5 auth and context

---

## Phase D4: PC Dashboard Real Data Integration

Objective: Implement dashboard.jpg-inspired PC dashboard with truthful backend-backed data.

Pages/components:
- DashboardPage
- Sidebar
- TopHeader
- KpiCardGrid
- OperationsCoordinatorCommandBar
- TodayPriorityPanel
- AiEmployeeGrid
- AiSuggestionPanel
- WorkActivityTimeline
- TodoSummaryPanel

API:
- GET /api/v2/pc-dashboard/overview

Data mapping:
- 今日销售额 <- kpis.today_sales_amount
- 今日销售笔数 <- kpis.today_sales_transactions
- 低库存商品 <- kpis.low_stock_count
- 待确认任务 <- kpis.pending_confirmation_count
- AI employee cards <- ai_employees
- 今日最重要三件事 <- top_priorities
- AI suggestions <- suggestions
- activities <- activities
- todos <- todos

AI-native UI requirements:
- AI运营协调官 input is prominent, not hidden.
- Suggestions show evidence, risk/confidence, and next action.
- High-risk actions open confirmation/review flow, not direct mutation.
- Each AI employee card shows role, current status, key metrics, and recent activity.

Acceptance:
- Dashboard can be loaded with real backend data.
- Empty store shows friendly onboarding instead of broken charts.
- All unsupported modules are clearly coming-soon.
- No fake customer/order/consultation number appears.

Validation:
- npm run build
- backend preflight
- manual Docker end-to-end: login -> dashboard -> data visible

Commit:
- feat: connect pc dashboard to backend overview

---

## Phase D5: Inventory and Product Management Integration

Objective: Make core goods/inventory operations usable in PC/H5.

Pages:
- ProductListPage
- ProductCreateEditDrawer
- InventoryStockPage
- InventoryLedgerPage
- InventoryItemAuditPage
- StockInOutModal

Backend APIs used:
- GET /api/v2/inventory/items
- POST /api/v2/inventory/items
- GET /api/v2/inventory/items/{id}
- PATCH /api/v2/inventory/items/{id}
- DELETE /api/v2/inventory/items/{id}
- GET /api/v2/inventory/stock
- GET /api/v2/inventory/events
- POST /api/v2/inventory/stock-in
- POST /api/v2/inventory/stock-out
- GET /api/v2/inventory/items/{id}/audit

Acceptance:
- Create product.
- Edit product.
- Soft delete product.
- Stock in.
- Stock out.
- Low stock updates dashboard after refresh.
- Audit trail shows historical ledger events for item.
- Cross-tenant data is not visible.

Validation:
- npm run build
- manual E2E against Docker backend.
- backend preflight.

Commit:
- feat: connect h5 inventory management

---

## Phase D6: AI Assistant + Confirmation Flow Integration

Objective: Make the AI-native loop usable: ask AI运营协调官 -> AI proposes action -> user confirms -> backend commits.

Frontend capabilities:
- Chat page or dashboard command bar can send messages.
- SSE streaming response is parsed correctly.
- Pending confirmation cards render for stock_in/stock_out.
- User can approve/reject confirmation.
- Approve updates inventory ledger/snapshot.
- Voice/photo upload entry can be added if browser UX is acceptable.

Backend APIs used:
- POST /api/v2/chat or /api/v2/chat/stream
- confirmation list endpoint if present
- POST /api/v2/confirmations/{id}/approve
- POST /api/v2/confirmations/{id}/reject
- voice/photo endpoints if included in H5 MVP

Frontend components:
- OperationsCoordinatorChatPanel
- StreamingMessageBubble
- ConfirmationCard
- StockInConfirmationReview
- StockOutConfirmationReview
- PendingConfirmationsDrawer

Acceptance:
- User asks: “M6螺丝入库10个”.
- System creates pending confirmation, stock unchanged.
- User approves.
- Ledger/snapshot update.
- Dashboard pending task count decreases.
- User asks impossible stock-out; system shows库存不足 and creates no confirmation.

Validation:
- Manual E2E plus backend confirmation tests.
- npm run build.
- Docker backend preflight.

Commit:
- feat: connect h5 ai confirmation flow

---

## Phase D7: Commercial UX Hardening

Objective: Make the PC/H5 app feel commercial-grade rather than demo-grade.

Work items:
- Unified empty states.
- Unified error toasts.
- Loading skeletons.
- Form validation.
- Destructive action confirmation modals.
- Permission/coming-soon states.
- First-run onboarding.
- Friendly copywriting for non-technical shop owners.
- Responsive behavior for common laptop widths.
- Visual polish to match dashboard.jpg while respecting no-emoji preference.

Acceptance:
- A first-time shop owner can understand what to do within 1 minute.
- Main business flows need no developer explanation.
- No raw JSON/error stack appears in UI.
- All destructive actions require confirmation.

Validation:
- Browser exploratory QA.
- npm run build.
- API failure simulation by stopping backend or forcing 401/500.

Commit:
- feat: harden h5 commercial ux

---

## Phase D8: Full-Stack Docker Deployment

Objective: Serve the H5 app through FastAPI/Docker for one-command pilot startup.

Approach:
- Build apps/h5 with Vite.
- Copy dist into backend static location or Docker image static path.
- FastAPI serves SPA index and assets.
- API routes remain under /api.
- SPA routes fallback to index.html.

Files likely touched:
- backend/app/main.py or static serving module
- backend/Dockerfile
- backend/scripts/run_docker_backend_acceptance.sh
- backend/scripts/run_backend_preflight.sh
- apps/h5 build config

Acceptance:
- Docker container exposes API and PC/H5 frontend on the same port.
- http://127.0.0.1:8001 loads PC/H5 app.
- http://127.0.0.1:8001/api/v2/health returns API health.
- Refreshing /dashboard or /inventory does not 404.
- Static assets load correctly.

Validation:
- cd apps/h5 && npm run build
- RUN_DOCKER_ACCEPTANCE=1 RUN_PROVIDER_TRIAL_PREFLIGHT=0 bash backend/scripts/run_backend_preflight.sh
- Browser manual test against Docker container.

Commit:
- feat: serve h5 app from backend docker

---

## Phase D9: Pilot Readiness and Production Gap Closure

Objective: Prepare for real commercial pilot, not just local demo.

Required before real user pilot:
1. Environment profiles:
   - local-demo
   - trial
   - production
2. Database decision:
   - SQLite acceptable for local demo only.
   - PostgreSQL required for commercial multi-user deployment.
3. Security:
   - CORS allowlist.
   - Rate limiting.
   - Secure token storage policy.
   - Password/code brute-force protection.
   - Audit logs for destructive actions.
4. Observability:
   - structured logs.
   - error tracking.
   - request latency metrics.
   - AI provider latency/cost logs.
5. Backup/recovery:
   - DB backup script.
   - restore drill.
6. Real provider trial:
   - Use provider trial preflight with process env vars only.
   - Never commit credentials.
7. Business onboarding:
   - create demo tenant/shop script.
   - create first real tenant/shop script.
   - import initial products CSV.
8. Legal/compliance placeholder:
   - privacy policy.
   - terms.
   - data deletion process.

Acceptance:
- A new shop can be onboarded without code changes.
- Production config is separated from local demo config.
- No secret appears in repository or logs.
- Backup and restore process documented.

Commit:
- chore: add commercial pilot readiness tooling

---

## Recommended Execution Order

1. D0 product contract.
2. D1 backend BFF endpoints.
3. D2 H5 skeleton.
4. D3 auth/context integration.
5. D4 dashboard integration.
6. D5 product/inventory integration.
7. D6 AI assistant/confirmation integration.
8. D7 UX hardening.
9. D8 Docker full-stack deployment.
10. D9 pilot readiness.

This order avoids building beautiful screens on unsupported data, while still getting a visible PC product quickly.

---

## Commercial Definition of Done

The PC/H5 + backend system is commercial-pilot ready when:

- User can login and select shop.
- User can see truthful dashboard metrics.
- User can manage goods.
- User can perform stock-in/stock-out.
- User can inspect ledger and item audit history.
- User can ask AI运营协调官 inventory/business questions.
- AI-generated inventory mutations require confirmation.
- User can approve/reject pending AI tasks.
- Docker can start the whole system.
- Backend preflight passes.
- Frontend build passes.
- GitHub Actions backend gate passes.
- No credentials are committed or logged.
- Unsupported modules are not presented as real working modules.

---

## Suggested First Sprint

Sprint D0-D1-D2 should be the immediate next sprint.

Why:
- D0 prevents scope drift.
- D1 gives the PC app a stable backend contract.
- D2 creates the formal PC/H5 app foundation.

Sprint success criteria:
- One new PC dashboard contract doc.
- One backend overview endpoint with tests.
- One Vite React H5 app scaffold that builds.
- Commit and push after verification.
