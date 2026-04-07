# Pilot Execution Runbook

This runbook covers the operator loop after trial readiness is green and the approved calibration artifact has already been applied.

## Daily Pilot Review Flow

1. Confirm the API is up and the trial profile is still configured.
2. Run the readiness CLI.
3. Run the pilot summary CLI for the current review window.
4. Export one shift bundle JSON package for handoff or incident review.
5. Record the bundle manifest path in the pilot handoff log or incident ticket.
6. Continue pilot traffic only when readiness, summary, and shift bundle export are all successful.

Baseline commands:

```powershell
python backend/scripts/run_trial_readiness_check.py
python backend/scripts/run_pilot_summary_check.py
python backend/scripts/export_pilot_shift_bundle.py --hours 24 --output-dir C:\secure\pilot\shift-bundles
```

Useful overrides:

```powershell
python backend/scripts/run_pilot_summary_check.py --hours 24
python backend/scripts/run_pilot_summary_check.py --max-fallback-rate 0.05 --max-low-confidence-rate 0.20
python backend/scripts/export_pilot_shift_bundle.py --hours 8 --api-base-url http://127.0.0.1:8001
```

## Cutover Mode Meanings

- `closed`: guardrails block live cutover behavior and operators should treat pilot traffic as halted
- `shadow`: providers are observed under guardrails and state-changing actions are forced through confirmations
- `open`: cutover is live under the approved profile/artifact/preflight alignment

When in doubt, roll back from `open` to `shadow`. If the incident is severe or unresolved, roll back to `closed`.

## Pilot Summary CLI Contract

The CLI runs readiness first and the protected pilot summary route second. It prints one compact JSON object with:

- `overall_status`
- `readiness`
- `pilot_summary.time_window`
- `pilot_summary.task_totals`
- `pilot_summary.total_task_count`
- `pilot_summary.telemetry_task_count`
- `pilot_summary.confirmations`
- `pilot_summary.confirmation_rate`
- `pilot_summary.rejection_rate`
- `pilot_summary.fallback_count`
- `pilot_summary.fallback_rate`
- `pilot_summary.low_confidence_count`
- `pilot_summary.low_confidence_rate`
- `pilot_summary.provider_failures`
- `pilot_summary.trial_provider_profile`
- `pilot_summary.reasons`
- `thresholds`

Exit behavior:

- Exit `0`: readiness is green and the pilot summary verdict is green
- Exit `1`: readiness degraded, pilot summary degraded, missing trial profile metadata, provider failures present, threshold breach, auth failure, non-200 response, or malformed envelope

## How To Read A Degraded Result

Treat the pilot summary as degraded when any of the following appears in `pilot_summary.reasons`:

- `trial_provider_profile_missing`
- `provider_failures_present`
- `fallback_rate_exceeded`
- `low_confidence_rate_exceeded`

The CLI also degrades when readiness is not green, even if the pilot summary metrics are otherwise within threshold.

Rate denominator note:

- `confirmation_rate` continues to use `total_task_count`
- `fallback_rate` and `low_confidence_rate` use `telemetry_task_count`, which is the count of distinct in-window task runs with telemetry for the current `trial_provider_profile`

## Suggested Daily Review Cadence

- Start of day: run readiness and a 24-hour pilot summary before opening pilot traffic.
- Mid-shift: re-run the pilot summary after any provider incident or threshold alert.
- End of day: export and archive a final shift bundle with the calibration artifact id that was active during the shift.

## Required Shift Bundle Export Workflow

Run once per handoff and for every incident timeline:

```powershell
python backend/scripts/export_pilot_shift_bundle.py --hours 24 --output-dir C:\secure\pilot\shift-bundles
```

Bundle contents:

- readiness JSON (`run_trial_readiness_check` equivalent payload)
- preflight JSON (`run_live_pilot_preflight` equivalent payload)
- current `GET /api/v1/system/pilot-control` JSON
- pilot summary JSON (`run_pilot_summary_check` equivalent payload)
- compact manifest with file names, timestamps, shop id, mode, profile, and artifact id

Destination requirements:

- use a private location outside the repo (recommended), or
- use a repository path that is explicitly gitignored

If any upstream artifact is degraded, export still succeeds but marks bundle `overall_status=degraded` and includes `degraded_reasons`.

## Rollback Posture

If either operator CLI exits non-zero:

1. Stop opening new pilot traffic until the cause is understood.
2. Move cutover back to `shadow` first while investigation continues:

```powershell
python backend/scripts/set_pilot_cutover.py --mode shadow --note "rollback: investigating incident"
```

3. If the incident remains unresolved, close cutover completely:

```powershell
python backend/scripts/set_pilot_cutover.py --mode closed --note "rollback: cutover closed pending fix"
```

4. Preserve and attach a fresh shift bundle export to the incident ticket.
5. If the issue is calibration-rule related, re-apply the previous approved calibration report:

```powershell
python backend/scripts/apply_trial_calibration.py --report C:\secure\pilot\artifacts\last-known-good.json
```

6. Re-run `run_trial_readiness_check.py`, `run_live_pilot_preflight.py`, and `run_pilot_summary_check.py` before resuming.
7. Open cutover again only through the controlled path:

```powershell
python backend/scripts/set_pilot_cutover.py --mode open --artifact-path C:\secure\pilot\artifacts\last-known-good.json --note "resume after rollback"
```

Notes:

- Do not use `/api/v1/system/demo/bootstrap` as a recovery step for trial mode.
- Any non-empty `provider_failures` map should be treated as a pilot incident until the underlying provider issue is explained.
- Missing or empty `trial_provider_profile` means the run is not safe to treat as calibrated pilot traffic.
