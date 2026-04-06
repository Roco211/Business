# Trial Readiness Runbook

This runbook is for operator-facing checks before trial usage.

## Scope

The trial readiness CLI verifies:

- `GET /health`
- `GET /api/v1/system/readiness` (authenticated)

It does not mutate demo state and does not call `/api/v1/system/demo/bootstrap`.

## Configuration Profiles

### Local Demo Profile

Use for development and local smoke resets.

- `APP_RUNTIME_MODE=local-demo`
- `OBJECT_STORAGE_PROVIDER=mock`
- `ASR_PROVIDER=mock`
- `OCR_PROVIDER=mock`
- `VISION_PROVIDER=mock`
- `ASR_ALLOW_MOCK_FALLBACK=1`
- `OCR_ALLOW_MOCK_FALLBACK=1`
- `VISION_ALLOW_MOCK_FALLBACK=1`

### Trial Profile

Use for trial readiness and operator preflight checks.

- `APP_RUNTIME_MODE=trial`
- `OBJECT_STORAGE_PROVIDER=s3-compatible`
- `ASR_PROVIDER=real-provider`
- `OCR_PROVIDER=real-provider`
- `VISION_PROVIDER=real-provider`
- `ASR_ALLOW_MOCK_FALLBACK=0`
- `OCR_ALLOW_MOCK_FALLBACK=0`
- `VISION_ALLOW_MOCK_FALLBACK=0`

The `*_ALLOW_MOCK_FALLBACK=0` settings are required in trial mode.

## Command

```powershell
python backend/scripts/run_trial_readiness_check.py
```

Optional flags:

```powershell
python backend/scripts/run_trial_readiness_check.py --api-base-url http://10.0.2.2:8001
python backend/scripts/run_trial_readiness_check.py --auth-token <access_token>
python backend/scripts/run_trial_readiness_check.py --login-email owner@example.com --login-password dev-password
```

When `--auth-token` is omitted, the CLI logs in via `POST /api/v1/auth/login` and uses the returned bearer token.

## Output Contract

The CLI prints compact JSON with:

- `api_base_url`
- `health_status`
- `runtime_mode`
- `readiness_status` (from `/api/v1/system/readiness` `overall_status`)
- `overall_status` (operator verdict; `ready` only when `runtime_mode=trial` and `readiness_status=ready`, otherwise `degraded`)
- `object_storage` (`status`, `mode`)
- `providers.asr|ocr|vision` (`status`, `mode`)

Example:

```json
{"api_base_url":"http://127.0.0.1:8001","health_status":"ok","runtime_mode":"trial","readiness_status":"ready","overall_status":"ready","object_storage":{"status":"ready","mode":"s3-compatible"},"providers":{"asr":{"status":"ready","mode":"real-provider"},"ocr":{"status":"ready","mode":"real-provider"},"vision":{"status":"ready","mode":"real-provider"}}}
```

## Exit Code

- Exit `0`: `runtime_mode == "trial"` and `readiness_status == "ready"` (`overall_status == "ready"`)
- Exit `1`: degraded/not-ready readiness, auth failures, health failures, non-200 responses, or malformed envelopes
