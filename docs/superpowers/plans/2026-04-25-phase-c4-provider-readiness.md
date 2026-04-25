# Phase C4: Real AI Provider Readiness

Date: 2026-04-25
Scope: LLM / ASR / OCR / Vision provider readiness
Repository: Business backend

## Goal

Prepare the backend for switching from repeatable mock-provider Docker validation to live provider validation, without leaking secrets and without weakening the existing local-demo path.

This document is a checklist and handoff guide. It does not include real API keys, tokens, passwords, or connection strings.

## Current provider posture

The backend supports a safe local-demo mode:

- `APP_RUNTIME_MODE=local-demo`
- `LLM_PROVIDER=mock`
- `ASR_PROVIDER=mock`
- `OCR_PROVIDER=mock`
- `VISION_PROVIDER=mock`

This mode is used by Docker acceptance and should remain the default for deterministic CI-like validation.

The backend configuration also exposes live-provider environment variables:

### LLM

- `LLM_PROVIDER`
- `LLM_PROVIDER_API_URL`
- `LLM_PROVIDER_API_KEY`
- `LLM_PROVIDER_MODEL`
- `LLM_TIMEOUT_SECONDS`
- `LLM_MAX_TOKENS`
- `LLM_TEMPERATURE`
- `LLM_ALLOW_MOCK_FALLBACK`

There is also a legacy OpenAI-compatible provider factory using:

- `LLM_API_URL`
- `LLM_API_KEY`
- `LLM_MODEL`
- `LLM_PROVIDER_NAME`
- `VOLCANO_API_URL`
- `VOLCANO_API_KEY`
- `VOLCANO_MODEL`

### ASR

- `ASR_PROVIDER`
- `ASR_PROVIDER_API_URL`
- `ASR_PROVIDER_API_KEY`
- `ASR_PROVIDER_MODEL`
- `ASR_TIMEOUT_SECONDS`
- `ASR_ALLOW_MOCK_FALLBACK`

### OCR

- `OCR_PROVIDER`
- `OCR_PROVIDER_API_URL`
- `OCR_PROVIDER_API_KEY`
- `OCR_PROVIDER_MODEL`
- `OCR_TIMEOUT_SECONDS`
- `OCR_ALLOW_MOCK_FALLBACK`

### Vision

- `VISION_PROVIDER`
- `VISION_PROVIDER_API_URL`
- `VISION_PROVIDER_API_KEY`
- `VISION_PROVIDER_MODEL`
- `VISION_TIMEOUT_SECONDS`
- `VISION_ALLOW_MOCK_FALLBACK`

### Trial readiness metadata

- `TRIAL_PROVIDER_PROFILE`
- `ASR_PROVIDER_LABEL`
- `OCR_PROVIDER_LABEL`
- `VISION_PROVIDER_LABEL`
- `TRIAL_CALIBRATION_DATASET_DIR`
- `TRIAL_CALIBRATION_ARTIFACTS_DIR`
- `LIVE_PILOT_ALLOWED_SHOP_IDS`

## Recommended live-provider environment profile

For a pilot/trial run, use environment variables or a local `.env` file like this. Replace all secret values with actual values locally only; never commit them.

```bash
APP_RUNTIME_MODE=trial
DATABASE_URL=sqlite:////app/aism-dev.db

LLM_PROVIDER=volcano
LLM_PROVIDER_API_URL=https://ark.cn-beijing.volces.com/api/v3/chat/completions
LLM_PROVIDER_MODEL=ep-xxxxxxxxxxxxxxxx
LLM_PROVIDER_API_KEY=[REDACTED]
LLM_TIMEOUT_SECONDS=30
LLM_MAX_TOKENS=500
LLM_TEMPERATURE=0.3
LLM_ALLOW_MOCK_FALLBACK=1

ASR_PROVIDER=volcano
ASR_PROVIDER_API_URL=[REDACTED]
ASR_PROVIDER_MODEL=[REDACTED]
ASR_PROVIDER_API_KEY=[REDACTED]
ASR_TIMEOUT_SECONDS=15
ASR_ALLOW_MOCK_FALLBACK=1

OCR_PROVIDER=volcano
OCR_PROVIDER_API_URL=[REDACTED]
OCR_PROVIDER_MODEL=[REDACTED]
OCR_PROVIDER_API_KEY=[REDACTED]
OCR_TIMEOUT_SECONDS=15
OCR_ALLOW_MOCK_FALLBACK=1

VISION_PROVIDER=volcano
VISION_PROVIDER_API_URL=[REDACTED]
VISION_PROVIDER_MODEL=[REDACTED]
VISION_PROVIDER_API_KEY=[REDACTED]
VISION_TIMEOUT_SECONDS=15
VISION_ALLOW_MOCK_FALLBACK=1

TRIAL_PROVIDER_PROFILE=volcano-trial-v1
ASR_PROVIDER_LABEL=volcano-asr-v1
OCR_PROVIDER_LABEL=volcano-ocr-v1
VISION_PROVIDER_LABEL=volcano-vision-v1
LIVE_PILOT_ALLOWED_SHOP_IDS=shop_default
```

Important for Volcano Engine LLM: `LLM_PROVIDER_MODEL` should be the Ark Endpoint ID, usually starting with `ep-`, not just a public model name.

## Safety rules

1. Do not commit `.env`.
2. Do not paste keys into docs, tests, scripts, commit messages, or chat output.
3. Use `[REDACTED]` for any key/token/password/connection string in written material.
4. Keep local-demo mock validation green before trying trial mode.
5. Keep mock fallback enabled during pilot preparation unless explicitly testing hard-fail behavior.
6. If turning fallback off, do it in a dedicated test window and verify error surfaces are user-safe.

## Suggested validation sequence

### 1. Baseline deterministic Docker acceptance

```bash
bash backend/scripts/run_docker_backend_acceptance.sh
```

Expected:

- `/health` returns 200.
- `/api/v2/health` returns 200.
- Alembic version is `20260419_05`.
- Phase 8 reports 8/8 passed.
- Phase 9 reports 5/5 passed.
- Phase 10 reports 6/6 passed.

### 2. Local trial readiness without exposing secrets

Start a backend with trial env vars supplied out-of-band, then run:

```bash
python3 backend/scripts/run_system_check.py --mode trial --api-base-url http://127.0.0.1:8001
python3 backend/scripts/run_trial_readiness_check.py --api-base-url http://127.0.0.1:8001
```

Expected:

- If provider profile labels are missing, the readiness output should name the missing labels.
- If credentials are missing, the output should report degraded/unready without printing the raw secret values.
- With all trial metadata and providers configured, readiness should move toward `ready`.

### 3. Provider calibration and preflight

```bash
python3 backend/scripts/apply_trial_calibration.py --asr-provider-label volcano-asr-v1 --ocr-provider-label volcano-ocr-v1
python3 backend/scripts/set_pilot_cutover.py --mode trial --allowed-shops shop_default
python3 backend/scripts/run_live_pilot_preflight.py --api-base-url http://127.0.0.1:8001
```

Expected:

- Trial provider profile matches readiness and pilot-control output.
- ASR/OCR/Vision labels are present and consistent.
- Pilot allowed shops are constrained.

## Known gaps before real pilot

- The current deterministic Docker script intentionally uses mock providers. A separate live-provider Docker script/profile should be added only after real credentials are available.
- Provider-specific ASR/OCR/Vision endpoint contracts need live sandbox validation with representative Chinese hardware-store audio/images.
- Secrets management should be formalized before production: environment variables are acceptable for local pilot, but production should use a secret manager or deployment platform secret store.
- LLM provider config currently has two naming families (`LLM_PROVIDER_*` and legacy `LLM_*` / `VOLCANO_*`). Before production, consolidate or document precedence explicitly in runtime checks.

## Exit criteria for live-provider readiness

- Mock Docker acceptance remains green.
- Trial runtime readiness check does not leak secrets.
- LLM can parse common intents with latency within target threshold.
- ASR can transcribe at least the core stock-query and stock-in phrases.
- OCR/Vision can extract at least one receipt/photo stock-in candidate with confidence metadata.
- Voice/Photo/Chat inventory writes still go through confirmation-first flow and approval-only ledger commit.
