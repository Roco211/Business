# Pilot Incident Recovery Runbook

This runbook covers the operator flow after a live pilot incident has already been detected. It assumes the pilot is running in `shadow` or `open`, and it focuses on safe, auditable recovery steps.

## Recovery Goals

1. Preserve operator evidence before changing pilot state.
2. Correlate the incident across cutover state, provider telemetry, affected task runs, confirmations, and session stream events.
3. Use replay and backfill actions that are read-only, auditable, and idempotent.
4. Close or shadow cutover before recovery work changes the live pilot posture.
5. Re-open pilot traffic only through the controlled pilot-control flow.

## Required Evidence First

Export a fresh shift bundle as soon as the incident is confirmed:

```powershell
python backend/scripts/export_pilot_shift_bundle.py --hours 24 --output-dir C:\secure\pilot\shift-bundles
```

The export records a protected `pilot.shift_bundle_exported` audit entry that is surfaced later through operator diagnostics.

## Operator API Session

Acquire a bearer token once for the recovery window:

```powershell
$login = Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8001/api/v1/auth/login" -ContentType "application/json" -Body '{"email":"owner@example.com","password":"dev-password"}'
$token = $login.data.access_token
$headers = @{ Authorization = "Bearer $token" }
```

## Standard Recovery Flow

1. Read the thin operator diagnostics surface:

```powershell
Invoke-RestMethod -Method Get -Uri "http://127.0.0.1:8001/api/v1/system/operator-diagnostics?hours=24&limit=10" -Headers $headers
```

Expected focus fields:

- `current_cutover_mode`
- `operator_verdict`
- `recent_reasons`
- `affected_tasks`
- `latest_shift_bundle`
- `suggested_actions`

2. Read the full incident timeline for the current window:

```powershell
Invoke-RestMethod -Method Get -Uri "http://127.0.0.1:8001/api/v1/system/incident-timeline?hours=24&limit=20" -Headers $headers
```

Use the timeline to answer:

- which task runs were affected
- which provider or guardrail reasons were involved
- whether confirmations were created or forced
- which session stream events were attached to the failing task

3. Replay one affected task diagnostically. This action is read-only and writes one `pilot.task_diagnostic_replayed` audit log. Re-using the same `idempotency_key` will return the existing audit entry instead of writing a duplicate.

```powershell
$body = @{
  task_run_id = "task_..."
  idempotency_key = "incident-drill-task-1"
} | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8001/api/v1/system/incident-replays/task-diagnostic" -Headers $headers -ContentType "application/json" -Body $body
```

4. Backfill the operator view snapshot after replay. This action is also read-only and idempotent under the same `idempotency_key`.

```powershell
$body = @{
  view = "incident-timeline"
  hours = 24
  limit = 20
  idempotency_key = "incident-drill-backfill-1"
} | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8001/api/v1/system/operator-view-backfills" -Headers $headers -ContentType "application/json" -Body $body
```

5. Roll back cutover if the operator verdict is `rollback-recommended` or if the incident remains unexplained:

```powershell
python backend/scripts/set_pilot_cutover.py --mode closed --note "incident recovery: close cutover pending drill review"
```

6. When investigation is complete, re-open in the controlled order:

```powershell
python backend/scripts/set_pilot_cutover.py --mode shadow --note "incident recovery: reopen in shadow"
python backend/scripts/set_pilot_cutover.py --mode open --artifact-path C:\secure\pilot\artifacts\pilot-v1_report_20260407T090000000000Z.json --note "incident recovery: reopen after review"
```

## Idempotency Rules

- `POST /api/v1/system/incident-replays/task-diagnostic`
  Use the same `idempotency_key` for a single incident ticket and task run.
- `POST /api/v1/system/operator-view-backfills`
  Use the same `idempotency_key` for one snapshot refresh cycle.
- `POST /api/v1/system/shift-bundle-exports`
  The API reuses the existing audit entry when `bundle_id` and `manifest_path` match.

## When To Stop

Do not re-open live cutover if any of these remain true:

- the incident reason is still unknown
- operator diagnostics still recommends rollback
- the latest shift bundle remains degraded without an owner-assigned explanation
- the replayed task still points to unresolved provider or guardrail drift

## Automated Drill Coverage

`backend/tests/test_pilot_incident_recovery_drill.py` covers the recovery sequence:

1. detect incident via operator diagnostics
2. record shift bundle export
3. inspect incident timeline
4. replay one task diagnostically
5. backfill the operator view
6. close cutover
7. reopen via `closed -> shadow -> open`
