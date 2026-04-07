# Real Pilot Cutover Runbook

This runbook defines the controlled live cutover flow for real pilot shifts.

## Cutover Mode Meanings

- `closed`: live cutover is blocked; do not process live pilot traffic.
- `shadow`: live providers run for observation, but guardrails force confirmation before state-changing writes.
- `open`: live providers are allowed under the approved profile/artifact/preflight alignment.

## Required Transition Path

Use the protected pilot-control mutation flow and keep transitions explicit:

1. `closed -> shadow` when beginning observation for a shift.
2. Run live preflight and confirm `overall_status=ready`.
3. `shadow -> open` only after fresh preflight is ready.
4. `open -> shadow` for rapid safety rollback.
5. `shadow -> closed` when the pilot window is halted.

Never jump directly from `closed -> open`.

## Cutover Commands

Move to shadow:

```powershell
python backend/scripts/set_pilot_cutover.py --mode shadow --note "shift start: observation window"
```

Run preflight before open:

```powershell
python backend/scripts/run_live_pilot_preflight.py --artifact-path C:\secure\pilot\artifacts\pilot-v1_report_20260407T090000000000Z.json
```

Open cutover:

```powershell
python backend/scripts/set_pilot_cutover.py --mode open --artifact-path C:\secure\pilot\artifacts\pilot-v1_report_20260407T090000000000Z.json --note "shift start: controlled open"
```

Inspect current control state:

```powershell
$headers = @{ Authorization = "Bearer <access_token>" }
$response = Invoke-RestMethod -Method Get -Uri "http://127.0.0.1:8001/api/v1/system/pilot-control" -Headers $headers -TimeoutSec 10
$response.data | ConvertTo-Json -Compress
```

## Required Shift Bundle Export

At each handoff and every incident, export a shift bundle:

```powershell
python backend/scripts/export_pilot_shift_bundle.py --hours 24 --output-dir C:\secure\pilot\shift-bundles
```

For shorter incident windows:

```powershell
python backend/scripts/export_pilot_shift_bundle.py --hours 8 --api-base-url http://127.0.0.1:8001 --output-dir C:\secure\pilot\shift-bundles
```

Bundle contents:

- readiness JSON
- preflight JSON
- current pilot-control JSON
- pilot summary JSON
- manifest JSON with file names, timestamps, shop id, mode, profile, and artifact id

Destination rule:

- use a private external directory when possible, or
- use a repository path that is explicitly gitignored.

## Rollback Path

When any preflight/summary/bundle output is degraded:

1. Roll back from `open` to `shadow` immediately:

```powershell
python backend/scripts/set_pilot_cutover.py --mode shadow --note "rollback: investigating degraded signal"
```

2. If risk remains, roll back to `closed`:

```powershell
python backend/scripts/set_pilot_cutover.py --mode closed --note "rollback: pilot closed pending fix"
```

3. Export a fresh shift bundle and attach it to the incident record.
4. Re-run readiness, preflight, and pilot summary before re-opening.
5. Use `project_docs/pilot-incident-recovery-runbook.md` for the full diagnostics, replay, backfill, and reopen sequence.
