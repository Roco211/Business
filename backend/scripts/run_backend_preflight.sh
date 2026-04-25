#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

RUN_DOCKER_ACCEPTANCE="${RUN_DOCKER_ACCEPTANCE:-0}"
PYTHON_BIN="${PYTHON_BIN:-python3}"

export PYTHONPATH="${PYTHONPATH:-backend}"
export APP_RUNTIME_MODE="${APP_RUNTIME_MODE:-local-demo}"
export LLM_PROVIDER="${LLM_PROVIDER:-mock}"
export ASR_PROVIDER="${ASR_PROVIDER:-mock}"
export OCR_PROVIDER="${OCR_PROVIDER:-mock}"
export VISION_PROVIDER="${VISION_PROVIDER:-mock}"
export LLM_ALLOW_MOCK_FALLBACK="${LLM_ALLOW_MOCK_FALLBACK:-1}"

log() {
  printf '[backend-preflight] %s\n' "$*"
}

run() {
  log "$*"
  "$@"
}

CORE_PYTEST_FILES=(
  backend/tests/test_v2_inventory_item_audit_http_flow.py
  backend/tests/test_v2_inventory_item_crud_http_flow.py
  backend/tests/test_v2_inventory_query_isolation_http_flow.py
  backend/tests/test_v2_inventory_stock_in_http_flow.py
  backend/tests/test_v2_inventory_stock_out_http_flow.py
  backend/tests/test_v2_dashboard_analytics_isolation_http_flow.py
  backend/tests/test_v2_chat_http_confirmation_flow.py
  backend/tests/test_v2_voice_photo_http_confirmation_flow.py
  backend/tests/test_v2_chat_confirmation_first.py
)

log "repo root: $ROOT_DIR"
log "python: $($PYTHON_BIN --version 2>&1)"
log "runtime mode: $APP_RUNTIME_MODE"
log "providers: LLM=$LLM_PROVIDER ASR=$ASR_PROVIDER OCR=$OCR_PROVIDER VISION=$VISION_PROVIDER"

run "$PYTHON_BIN" -m compileall -q backend/app backend/tests backend/scripts
run "$PYTHON_BIN" -m pytest -vv "${CORE_PYTEST_FILES[@]}"

if [[ "$RUN_DOCKER_ACCEPTANCE" == "1" ]]; then
  run bash backend/scripts/run_docker_backend_acceptance.sh
else
  log "skipping Docker acceptance; set RUN_DOCKER_ACCEPTANCE=1 to enable"
fi

log "preflight passed"
