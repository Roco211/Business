#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

echo "== Business production trial rehearsal =="
echo "[1/5] Validate production compose file"
python3 - <<'PY'
from pathlib import Path
import yaml
path = Path('infra/docker/docker-compose.production.yml')
data = yaml.safe_load(path.read_text())
services = data.get('services') or {}
required = {'postgres', 'redis', 'migrator', 'api'}
missing = sorted(required - set(services))
if missing:
    raise SystemExit(f'missing services: {missing}')
ports = services['api'].get('ports') or []
if not any('0.0.0.0:${HOST_PORT:-8001}:8001' in str(port) for port in ports):
    raise SystemExit(f'api port binding is not production trial friendly: {ports}')
print('compose yaml ok')
PY

echo "[2/5] Validate backup/restore scripts syntax"
bash -n backend/scripts/backup_postgres.sh
bash -n backend/scripts/restore_postgres.sh

echo "[3/5] Validate production middleware/config regressions"
PYTHONPATH=backend pytest backend/tests/test_production_readiness_config.py -q

echo "[4/5] Validate backend readiness summary"
READINESS_JSON="$(PYTHONPATH=backend python3 backend/scripts/run_backend_readiness_summary.py)"
READINESS_JSON="$READINESS_JSON" python3 - <<'PY'
import json, os
payload = json.loads(os.environ['READINESS_JSON'])
print(json.dumps({
    'overall_status': payload.get('overall_status'),
    'ready_count': payload.get('ready_count'),
    'missing_count': payload.get('missing_count'),
}, ensure_ascii=False))
if payload.get('overall_status') != 'ready' or payload.get('missing_count') != 0:
    raise SystemExit('readiness summary is not ready')
PY

echo "[5/5] Optional Docker production image acceptance"
if [[ "${RUN_DOCKER_ACCEPTANCE:-0}" == "1" ]]; then
  RUN_PROVIDER_TRIAL_PREFLIGHT=0 RUN_DOCKER_ACCEPTANCE=1 bash backend/scripts/run_backend_preflight.sh
else
  echo "skip docker acceptance; set RUN_DOCKER_ACCEPTANCE=1 to include image build/runtime checks"
fi

echo "production trial rehearsal passed"
