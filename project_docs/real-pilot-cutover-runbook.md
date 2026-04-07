# Real Pilot Cutover Runbook

This runbook defines the controlled operator sequence for opening, monitoring, handing off, and rolling back real pilot cutover.

## Mode Semantics

- `closed`: block live cutover operations; treat pilot traffic as paused.
- `shadow`: observe live providers while forcing confirmation gates.
- `open`: controlled live cutover after successful preflight and approved artifact alignment.

## Preconditions Before Opening

1. Trial profile is active (`APP_RUNTIME_MODE=trial`).
2. Current readiness check is green.
3. Latest approved calibration artifact is available on a private path.
4. Operator has a rollback note prepared in case of incident.

## Controlled Open Sequence

1. Run readiness:

```powershell
python backend/scripts/run_trial_readiness_check.py
```

2. Run live preflight with the approved artifact:

```powershell
python backend/scripts/run_live_pilot_preflight.py --artifact-path C:\secure\pilot\artifacts\pilot-v1_report_20260407T090000000000Z.json
```

3. Move cutover to `shadow` (if not already there):

```powershell
python backend/scripts/set_pilot_cutover.py --mode shadow --note "pre-open observation window"
```

4. Open cutover with the same artifact path:

```powershell
python backend/scripts/set_pilot_cutover.py --mode open --artifact-path C:\secure\pilot\artifacts\pilot-v1_report_20260407T090000000000Z.json --note "morning shift open"
```

5. Validate live window health:

```powershell
python backend/scripts/run_pilot_summary_check.py --hours 24
```

## Required Shift Handoff Export

Export one bundle for each shift handoff and each incident timeline:

```powershell
python backend/scripts/export_pilot_shift_bundle.py --hours 24 --output-dir C:\secure\pilot\shift-bundles
```

Bundle includes:

- readiness JSON
- preflight JSON
- current pilot-control JSON
- pilot summary JSON
- manifest (`manifest.json`) containing file names, timestamps, shop id, mode, profile, and artifact id

Store bundle output in private storage and reference the manifest path in handoff/incident notes.

## Incident Rollback Path

If pilot checks degrade or provider incidents occur:

1. Roll back from `open` to `shadow`:

```powershell
python backend/scripts/set_pilot_cutover.py --mode shadow --note "rollback: provider incident investigation"
```

2. If needed, roll back from `shadow` to `closed`:

```powershell
python backend/scripts/set_pilot_cutover.py --mode closed --note "rollback: stop live cutover"
```

3. Export an incident shift bundle immediately:

```powershell
python backend/scripts/export_pilot_shift_bundle.py --hours 8 --output-dir C:\secure\pilot\shift-bundles
```

4. Re-run readiness, preflight, and pilot summary before considering reopen.

## Reopen After Rollback

Only reopen after:

1. root cause is understood and mitigated,
2. preflight returns `overall_status=ready`,
3. cutover transition is explicitly audited through `set_pilot_cutover.py --mode open`,
4. a new shift bundle is exported after reopen for traceability.
