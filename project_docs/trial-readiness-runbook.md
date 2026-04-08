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

## Trial Metadata Checklist

Before the first pilot shift, confirm that the readiness payload reports a populated `trial_profile` check with:

- `trial_provider_profile`
- `asr_provider_label`
- `ocr_provider_label`
- `vision_provider_label`
- `trial_calibration_dataset_dir`
- `trial_calibration_artifacts_dir`

If any of those values are missing in trial mode, treat the environment as degraded and fix configuration before running live traffic.

## Private Calibration Dataset Preparation

Keep the pilot calibration dataset outside the repo and point `TRIAL_CALIBRATION_DATASET_DIR` at that private directory.

- Store only operator-approved pilot samples. Do not commit raw trial media into source control.
- Prefer de-identified or least-privilege media exports when possible.
- Keep stable file paths so the manifest can reference them without manual renaming on every run.
- Restrict directory access to the pilot operator group because the manifest may point at sensitive receipts, photos, or recordings.

Recommended manifest shape:

```json
{
  "trial_id": "pilot-v1",
  "cases": [
    {
      "case_id": "asr-001",
      "capability": "asr",
      "media_path": "asr/order-001.wav",
      "text_hint": "owner asking for current cola stock",
      "expected": {
        "transcript_contains": ["cola"],
        "min_confidence": 0.9
      }
    },
    {
      "case_id": "ocr-001",
      "capability": "ocr",
      "media_path": "ocr/receipt-001.jpg",
      "expected": {
        "total_amount": 123.0,
        "amount_tolerance": 1.0
      }
    },
    {
      "case_id": "vision-001",
      "capability": "vision",
      "media_path": "vision/item-001.jpg",
      "expected": {
        "top_candidate_in": ["Red Bull 250ml"],
        "min_confidence": 0.9
      }
    }
  ]
}
```

## Calibration Run And Apply Flow

1. Load the trial environment profile and confirm the readiness CLI is using the intended `trial_provider_profile`.
2. Run the live calibration against the private manifest.
3. Review the generated JSON and Markdown artifacts under `TRIAL_CALIBRATION_ARTIFACTS_DIR`.
4. Apply the approved JSON report to shop rules.
5. Re-run readiness before opening the pilot day.

Commands:

```powershell
python backend/scripts/run_live_trial_calibration.py --manifest C:\secure\pilot\manifest.json
python backend/scripts/apply_trial_calibration.py --report C:\secure\pilot\artifacts\pilot-v1_report_20260407T090000000000Z.json
python backend/scripts/run_trial_readiness_check.py
```

Notes:

- `run_live_trial_calibration.py` writes a machine-readable JSON report plus a Markdown operator summary.
- `apply_trial_calibration.py` updates the target shop's `low_confidence_threshold`, `require_price_confirmation`, and `require_new_item_confirmation`.
- Calibration apply writes an audit log entry tied to the report `artifact_id` and `trial_provider_profile`.
- If the applied rules are not acceptable, re-apply the last known-good report before running the next readiness check.

## Live Pilot Preflight CLI Contract

Run preflight immediately before any `shadow -> open` transition:

```powershell
python backend/scripts/run_live_pilot_preflight.py --artifact-path C:\secure\pilot\artifacts\pilot-v1_report_20260407T090000000000Z.json
```

Optional flags:

```powershell
python backend/scripts/run_live_pilot_preflight.py --api-base-url http://10.0.2.2:8001
python backend/scripts/run_live_pilot_preflight.py --auth-token <access_token>
```

Output contract (compact JSON):

- `overall_status`: `ready` or `degraded`
- `runtime_mode`
- `trial_provider_profile`
- `cutover_mode`
- `approved_calibration_artifact_id`
- `reasons` (array of degraded reasons, empty when ready)

Exit behavior:

- Exit `0`: all preflight gates are green
- Exit `1`: readiness mismatch, profile/label drift, artifact mismatch, allowlist mismatch, path safety issue, auth failure, or malformed payload

Preflight contract notes:

- the CLI uses protected routes and validates alignment across:
  - `GET /api/v1/system/readiness`
  - `GET /api/v1/system/pilot-control`
  - approved artifact JSON content
- if `reasons` is non-empty, treat the environment as not safe for `open` cutover
- preflight status is not sticky; rerun it for each new cutover window

## Cutover Mode Meanings

- `closed`: live pilot traffic is blocked by cutover policy
- `shadow`: live providers run, but guardrails force confirmation before state-changing actions
- `open`: live providers and guardrails are aligned for controlled live cutover

Only move to `open` after a fresh preflight result is `ready`.

## Handoff To Daily Pilot Review

Once readiness is green and the approved calibration report has been applied, use the daily flow in `project_docs/pilot-execution-runbook.md` for ongoing operator checks. That runbook covers the pilot summary CLI, threshold overrides, and rollback posture.
