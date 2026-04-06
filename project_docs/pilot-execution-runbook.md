# Pilot Execution Runbook

This runbook covers the operator loop after trial readiness is green and the approved calibration artifact has already been applied.

## Daily Pilot Review Flow

1. Confirm the API is up and the trial profile is still configured.
2. Run the readiness CLI.
3. Run the pilot summary CLI for the current review window.
4. Record the compact JSON outputs in the pilot handoff log or incident ticket.
5. Continue pilot traffic only when both checks remain green.

Baseline commands:

```powershell
python backend/scripts/run_trial_readiness_check.py
python backend/scripts/run_pilot_summary_check.py
```

Useful overrides:

```powershell
python backend/scripts/run_pilot_summary_check.py --hours 24
python backend/scripts/run_pilot_summary_check.py --max-fallback-rate 0.05 --max-low-confidence-rate 0.20
```

## Pilot Summary CLI Contract

The CLI runs readiness first and the protected pilot summary route second. It prints one compact JSON object with:

- `overall_status`
- `readiness`
- `pilot_summary.time_window`
- `pilot_summary.task_totals`
- `pilot_summary.total_task_count`
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

## Suggested Daily Review Cadence

- Start of day: run readiness and a 24-hour pilot summary before opening pilot traffic.
- Mid-shift: re-run the pilot summary after any provider incident or threshold alert.
- End of day: archive the final summary JSON with the calibration artifact id that was active during the shift.

## Rollback Posture

If either operator CLI exits non-zero:

1. Stop opening new pilot traffic until the cause is understood.
2. Preserve the latest readiness JSON, pilot summary JSON, and calibration report path used for that shift.
3. If the issue is provider or infrastructure related, revert to the last known-good runtime profile or move the environment back to `APP_RUNTIME_MODE=local-demo` before restarting the API.
4. If the issue is calibration-rule related, re-apply the previous approved calibration report:

```powershell
python backend/scripts/apply_trial_calibration.py --report C:\secure\pilot\artifacts\last-known-good.json
```

5. Re-run `run_trial_readiness_check.py` and `run_pilot_summary_check.py` before resuming the pilot.

Notes:

- Do not use `/api/v1/system/demo/bootstrap` as a recovery step for trial mode.
- Any non-empty `provider_failures` map should be treated as a pilot incident until the underlying provider issue is explained.
- Missing or empty `trial_provider_profile` means the run is not safe to treat as calibrated pilot traffic.
