#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${PYTHON_BIN:-python3}"
export PYTHONPATH="${PYTHONPATH:-backend}"
export APP_ENV="${APP_ENV:-production}"
export APP_RUNTIME_MODE="${APP_RUNTIME_MODE:-production}"
export SMS_REAL_PREFLIGHT="${SMS_REAL_PREFLIGHT:-0}"
export RUN_REAL_PROVIDER_TRIAL="${RUN_REAL_PROVIDER_TRIAL:-0}"

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
if [[ "$SMS_REAL_PREFLIGHT" == "1" ]]; then
  log "sms: real SMS preflight required"
else
  log "sms: real SMS preflight deferred; set SMS_REAL_PREFLIGHT=1 after SMS credentials are available"
fi

run "$PYTHON_BIN" - <<'PY'
import os
from app.core.config import get_settings

settings = get_settings()
violations = settings.production_mock_violations()
if os.getenv("SMS_REAL_PREFLIGHT", "0") != "1":
    violations = [v for v in violations if v.get("key") != "SMS_PROVIDER"]
if violations:
    print({
        "status": "failed",
        "check": "production_mock_violations",
        "violation_count": len(violations),
        "violations": violations,
    })
    raise SystemExit(1)
print({
    "status": "passed",
    "check": "production_mock_violations",
    "sms_real_preflight": os.getenv("SMS_REAL_PREFLIGHT", "0") == "1",
})
PY

run "$PYTHON_BIN" - <<'PY'
from app.core.config import get_settings
from app.services.object_storage import build_object_storage

settings = get_settings()
provider = build_object_storage(settings)
target = provider.create_upload_target(
    object_key="health-check/real-provider-preflight-object-storage.txt",
    content_type="text/plain",
)
print({
    "status": "passed",
    "check": "object_storage_presign",
    "provider": settings.normalized_object_storage_provider(),
    "upload_url_scheme": target.upload_url.split(":", 1)[0],
    "public_url_configured": bool(target.public_url),
})
PY

run "$PYTHON_BIN" - <<'PY'
from app.core.config import get_settings

settings = get_settings()
checks = {
    "llm_provider_configured": bool(settings.llm_provider and settings.llm_provider.strip().lower() != "mock"),
    "llm_key_configured": bool(settings.llm_provider_api_key),
    "ocr_provider_configured": bool(settings.ocr_provider and settings.ocr_provider.strip().lower() != "mock"),
    "ocr_key_configured": bool(settings.ocr_provider_api_key),
    "vision_provider_configured": bool(settings.vision_provider and settings.vision_provider.strip().lower() != "mock"),
    "vision_key_configured": bool(settings.vision_provider_api_key),
    "asr_client_mode": settings.asr_provider.strip().lower() in {"client", "client-asr", "disabled", "none", ""},
}
failed = [key for key, ok in checks.items() if not ok]
print({"status": "passed" if not failed else "failed", "check": "provider_config_summary", "failed": failed})
if failed:
    raise SystemExit(1)
PY

run "$PYTHON_BIN" -m compileall -q backend/app backend/scripts
run "$PYTHON_BIN" -m pytest -q \
  backend/tests/test_production_mock_guardrails.py \
  backend/tests/test_production_readiness_config.py \
  backend/tests/test_provider_trial_preflight.py \
  backend/tests/test_ark_multimodal_provider.py \
  backend/tests/test_object_storage_provider.py

if [[ "$RUN_REAL_PROVIDER_TRIAL" == "1" ]]; then
  log "running live provider trial preflight"
  run "$PYTHON_BIN" backend/scripts/run_provider_trial_preflight.py
else
  log "skipping live provider trial; set RUN_REAL_PROVIDER_TRIAL=1 after injecting real credentials"
fi

log "real-provider preflight passed"
