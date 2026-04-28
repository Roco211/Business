#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${PYTHON_BIN:-python3}"
export PYTHONPATH="${PYTHONPATH:-backend}"
export APP_ENV="${APP_ENV:-production}"
export APP_RUNTIME_MODE="${APP_RUNTIME_MODE:-production}"

log() {
  printf '[real-provider-preflight] %s\n' "$*"
}

run() {
  log "$*"
  "$@"
}

log "repo root: $ROOT_DIR"
log "profile: production real-provider preflight; mock providers are not accepted"
log "python: $($PYTHON_BIN --version 2>&1)"

run "$PYTHON_BIN" - <<'PY'
from app.core.config import get_settings

settings = get_settings()
violations = settings.production_mock_violations()
if violations:
    print({"status": "failed", "check": "production_mock_violations", "violations": violations})
    raise SystemExit(1)
print({"status": "passed", "check": "production_mock_violations"})
PY

run "$PYTHON_BIN" -m compileall -q backend/app backend/scripts
run "$PYTHON_BIN" -m pytest -q \
  backend/tests/test_production_mock_guardrails.py \
  backend/tests/test_production_readiness_config.py \
  backend/tests/test_provider_trial_preflight.py \
  backend/tests/test_ark_multimodal_provider.py

if [[ "${RUN_REAL_PROVIDER_TRIAL:-0}" == "1" ]]; then
  log "running live provider trial preflight"
  run "$PYTHON_BIN" backend/scripts/run_provider_trial_preflight.py
else
  log "skipping live provider trial; set RUN_REAL_PROVIDER_TRIAL=1 after injecting real credentials"
fi

log "real-provider preflight passed"
