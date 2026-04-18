# Infra Docker

This directory defines the local infrastructure for the current MVP foundation:

- MySQL
- Redis
- MinIO
- API service
- Worker service
- Beat service

Phase 2 adds SQLAlchemy and Alembic-backed persistence. The backend now expects a migration-managed schema for DB-backed routes such as mock login bootstrap and session bootstrap. By default the application derives its database URL from `MYSQL_*` variables, and `DATABASE_URL` is only needed when you want to override that behavior explicitly.

Phase 3A extends that persistence layer with the message and task ledger foundation. The local stack still brings up MySQL, Redis, MinIO, API, and worker services, but this phase only exercises the DB-backed intake path and does not yet introduce runtime consumers, confirmations, or WebSocket session events.

The compose stack now includes a `migrator` service so the API and worker start behind an explicit schema upgrade step.

Phase 4A adds a dry-run runtime worker on top of that ledger. Fresh message intake now produces pollable task runs, the worker can consume them asynchronously, and runtime outcomes are written back into the session as read-only system messages. This phase still avoids confirmation flows, inventory mutation, audit trails, and WebSocket push.

Phase 4B adds durable confirmation persistence and owner-facing confirmation routes on top of the runtime worker. Stock-in tasks can now pause in `awaiting-confirmation`, pending confirmations can be listed and resolved through the API, and task-run polling can project the linked `confirmation_id`.

Phase 5A extends that approval path into real inventory truth. Approving a pending stock-in confirmation now writes `inventory_items`, `inventory_events`, and `audit_logs` in the backend database and only then completes the linked task.

Phase 6A adds the first read-side surface on top of that truth. The backend now exposes inventory item list/detail reads plus inventory-scoped audit log reads, and the Expo `LedgerScreen` consumes them through a lightweight fetch client.

Phase 6B extends that read-side with a durable `alerts` table, a dashboard summary route, and a low-stock alert route. The Expo `DashboardScreen` now reads:

- `GET /api/v1/dashboard/summary`
- `GET /api/v1/alerts?type=low-stock`
- `GET /api/v1/confirmations?status=pending`

Current alert truth is only refreshed by the approved stock-in commit path. Stock-out, correction, and realtime push remain future work.

Phase 7A adds the first ledger correction write path:

- `POST /api/v1/inventory-events/corrections`

The backend now refreshes low-stock alert truth after both:

- approved stock-in commits
- manual correction writes

Stock-out and realtime push still remain future work.

For local mobile development:

- set `EXPO_PUBLIC_API_BASE_URL` if you want to point Expo at a non-default backend
- otherwise the client defaults to `http://10.0.2.2:8001` on Android emulators
- and defaults to `http://127.0.0.1:8001` on non-Android Expo targets
- Expo Go now opens on the login screen first
- use the seeded owner credentials (default: `owner@example.com` / `dev-password`) unless you override `SEED_OWNER_EMAIL` / `SEED_OWNER_PASSWORD`
- after login, mobile API calls use the issued bearer access token

Phase 8A now adds:

- durable `session_stream_events`
- a websocket session endpoint at `WS /api/v1/ws/sessions/{session_id}?token=<access_token>`
- a mobile shared session bootstrap + websocket provider

Current realtime behavior is intentionally lightweight:

- the API process tails committed `session_stream_events` for connected websocket clients
- the mobile app re-fetches affected REST reads on incoming events instead of maintaining a local cache graph
- the websocket surface is login-token-authenticated and scoped to one session at a time

Replay endpoints, OCR-specific stream events, and stock-out realtime flows remain future work.

The V2 outbox due-scope fallback now also has a Celery beat-based scheduling path. The beat process periodically enqueues `app.workers.v2_outbox_due_tasks.drain_due_v2_outbox_scopes` so pending projection work can still be swept even when no business request triggers the best-effort runtime dispatch path.

## Local Demo Run Order

With the current MVP slices in place, the recommended local operator flow is now:

1. Start the local stack:

```powershell
docker compose -f infra/docker/docker-compose.yml --env-file .env.example up -d mysql redis minio api worker beat
```

2. Verify the running API and reset the demo state:

```powershell
python backend/scripts/run_local_demo_smoke.py
```

3. Start Expo if you want to exercise the mobile client:

```powershell
cd apps/mobile
npx expo start
```

The smoke script talks to the running API at `http://127.0.0.1:8001` by default, calls the demo bootstrap API, and validates the expected owner-facing dashboard/chat/ledger state over HTTP.
When `--auth-token` is omitted, it first logs in at `POST /api/v1/auth/login` using the CLI login credentials and then uses that issued bearer token for protected calls.
In local-demo mock object-storage mode, `POST /api/v1/media-uploads` now returns an API-served writable `upload_url` under `/api/v1/media-uploads/mock/...` so mobile/demo clients can perform a real `PUT` before calling `complete`.

You can override the API target if needed:

```powershell
python backend/scripts/run_local_demo_smoke.py --api-base-url http://10.0.2.2:8001
```

You can also provide explicit login credentials or a pre-issued bearer token:

```powershell
python backend/scripts/run_local_demo_smoke.py --login-email owner@example.com --login-password dev-password
python backend/scripts/run_local_demo_smoke.py --auth-token <access_token>
```

## Trial Readiness Run Order

Use this flow for operator trial checks (not demo reset):

1. Start the local stack:

```powershell
docker compose -f infra/docker/docker-compose.yml --env-file .env.example up -d mysql redis minio api worker beat
```

2. Switch runtime/provider env vars to the trial profile:

- `APP_RUNTIME_MODE=trial`
- `OBJECT_STORAGE_PROVIDER=s3-compatible`
- `ASR_PROVIDER=real-provider`
- `OCR_PROVIDER=real-provider`
- `VISION_PROVIDER=real-provider`
- `ASR_ALLOW_MOCK_FALLBACK=0`
- `OCR_ALLOW_MOCK_FALLBACK=0`
- `VISION_ALLOW_MOCK_FALLBACK=0`

3. Run the trial readiness CLI:

```powershell
python backend/scripts/run_trial_readiness_check.py
```

Behavior notes:

- the CLI calls `GET /health` and authenticated `GET /api/v1/system/readiness`
- when `--auth-token` is omitted, it logs in with owner credentials first (same auth flow as local demo smoke)
- it prints compact JSON and exits `0` only when runtime mode is `trial` and readiness is `ready`
- `degraded`, `not-ready`, auth errors, health failures, and malformed responses all exit non-zero

Full operator checklist lives in `project_docs/trial-readiness-runbook.md`.

## Local ASR Config

The backend ASR gateway is controlled through environment variables:

- `ASR_PROVIDER=mock` keeps local development on the deterministic mock provider.
- `ASR_PROVIDER=real-provider` enables the configured remote ASR adapter.
- `ASR_PROVIDER_API_URL` points at the real ASR HTTP endpoint when `ASR_PROVIDER=real-provider`.
- `ASR_PROVIDER_API_KEY` provides the bearer token for the real ASR endpoint.
- `ASR_PROVIDER_MODEL` selects the upstream transcription model.
- `ASR_TIMEOUT_SECONDS` controls request timeout for the real provider.
- `ASR_ALLOW_MOCK_FALLBACK=1` allows retryable real-provider failures to fall back to mock transcripts.
- `ASR_ALLOW_MOCK_FALLBACK=0` disables that fallback so operators can see hard real-provider failures directly.

The eval CLI now reads the supplied local audio file, infers basic file metadata, and forwards that audio payload through the ASR helper. It also sends either the explicit `--media-id` value or the filename stem so mock mode and fallback-driven checks can still target fixture transcripts.

For a mock-friendly operator check, keep `ASR_PROVIDER=mock` and run the eval CLI against any local audio file plus a fixture media ID:

```powershell
python backend/scripts/evaluate_real_asr.py C:\path\to\voice-query.m4a --media-id voice_query_demo
```

That prints compact JSON with:

- `transcript`
- `confidence`
- `provider_name`
- `used_fallback`
- `latency_ms`

For a real-provider smoke check, export the real ASR settings first and then point the same CLI at a local audio file. Pass `--media-id` as well if your configured gateway expects a specific upstream identifier in addition to the uploaded audio payload:

```powershell
$env:ASR_PROVIDER='real-provider'
$env:ASR_PROVIDER_API_URL='https://asr.example.com/v1/transcriptions'
$env:ASR_PROVIDER_API_KEY='replace-me'
$env:ASR_PROVIDER_MODEL='replace-me'
python backend/scripts/evaluate_real_asr.py C:\path\to\sample.m4a
```

If you still want retryable real-provider failures to fall back to the mock layer during local operator checks, leave `ASR_ALLOW_MOCK_FALLBACK=1` and pass a fixture media ID such as `voice_query_demo`, `voice_stock_in_demo`, or `voice_stock_out_demo`.

## Local OCR Config

The backend OCR gateway is controlled through environment variables:

- `OCR_PROVIDER=mock` keeps local development on the deterministic receipt OCR fixture.
- `OCR_PROVIDER=real-provider` enables the configured remote OCR adapter.
- `OCR_PROVIDER_API_URL` points at the real OCR HTTP endpoint when `OCR_PROVIDER=real-provider`.
- `OCR_PROVIDER_API_KEY` provides the bearer token for the real OCR endpoint.
- `OCR_PROVIDER_MODEL` selects the upstream OCR model.
- `OCR_TIMEOUT_SECONDS` controls request timeout for the real provider.
- `OCR_ALLOW_MOCK_FALLBACK=1` allows retryable real-provider failures to fall back to the mock receipt provider.
- `OCR_ALLOW_MOCK_FALLBACK=0` disables that fallback so operators can see hard real-provider failures directly.

The OCR eval CLI reads a local image file, infers the content type, and forwards inline image bytes through the OCR gateway. That means it works both for hosted-media environments and for local operator checks where the file is not uploaded anywhere yet.

For a mock-friendly operator check, keep `OCR_PROVIDER=mock` and run:

```powershell
python backend/scripts/evaluate_real_ocr.py C:\path\to\receipt.jpg
```

That prints compact JSON with:

- `provider_name`
- `used_fallback`
- `total_amount`
- `line_items`
- `low_confidence_fields`

For a real-provider smoke check, export the OCR settings first and then point the same CLI at a local receipt image:

```powershell
$env:OCR_PROVIDER='real-provider'
$env:OCR_PROVIDER_API_URL='https://ocr.example.com/v1/receipts'
$env:OCR_PROVIDER_API_KEY='replace-me'
$env:OCR_PROVIDER_MODEL='replace-me'
python backend/scripts/evaluate_real_ocr.py C:\path\to\receipt.jpg
```

If you still want retryable real-provider failures to fall back to the mock layer during local operator checks, leave `OCR_ALLOW_MOCK_FALLBACK=1`.

## Local Vision Config

The backend vision gateway is controlled through environment variables:

- `VISION_PROVIDER=mock` keeps local development on the deterministic photo recognition fixture.
- `VISION_PROVIDER=real-provider` enables the configured remote vision adapter.
- `VISION_PROVIDER_API_URL` points at the real vision HTTP endpoint when `VISION_PROVIDER=real-provider`.
- `VISION_PROVIDER_API_KEY` provides the bearer token for the real vision endpoint.
- `VISION_PROVIDER_MODEL` selects the upstream recognition model.
- `VISION_TIMEOUT_SECONDS` controls request timeout for the real provider.
- `VISION_ALLOW_MOCK_FALLBACK=1` allows retryable real-provider failures to fall back to the mock vision provider.
- `VISION_ALLOW_MOCK_FALLBACK=0` disables that fallback so operators can see hard real-provider failures directly.

The vision eval CLI reads a local image file, infers the content type, and forwards inline image bytes through the vision gateway so local checks do not depend on pre-hosted media.

For a mock-friendly operator check, keep `VISION_PROVIDER=mock` and run:

```powershell
python backend/scripts/evaluate_real_vision.py C:\path\to\product.jpg
```

That prints compact JSON with:

- `provider_name`
- `used_fallback`
- `candidates`

For a real-provider smoke check, export the vision settings first and then point the same CLI at a local product image:

```powershell
$env:VISION_PROVIDER='real-provider'
$env:VISION_PROVIDER_API_URL='https://vision.example.com/v1/recognize'
$env:VISION_PROVIDER_API_KEY='replace-me'
$env:VISION_PROVIDER_MODEL='replace-me'
python backend/scripts/evaluate_real_vision.py C:\path\to\product.jpg
```

If you still want retryable real-provider failures to fall back to the mock layer during local operator checks, leave `VISION_ALLOW_MOCK_FALLBACK=1`.
