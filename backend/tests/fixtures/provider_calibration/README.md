# Provider Calibration Manifest Fixtures

This fixture set is intentionally redacted and mock-friendly.

- `manifest.schema.json` defines the tracked manifest contract for pilot calibration runs.
- `example_manifest.json` shows a safe example that uses local fixture paths and no private media.
- `python backend/scripts/run_live_trial_calibration.py --manifest backend/tests/fixtures/provider_calibration/example_manifest.json`
  writes artifacts by default to `backend/devdata/trial_calibration_artifacts/` (ignored in git).

## Source Control Boundary

Do not commit:

- private store media (audio/images/video)
- raw provider payload dumps from live trials
- customer or operator data

Keep live assets and generated artifacts in ignored paths:

- `backend/devdata/trial_calibration/`
- `backend/devdata/trial_calibration_artifacts/`
