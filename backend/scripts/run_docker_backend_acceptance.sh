#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
IMAGE_NAME="${IMAGE_NAME:-business-backend-test}"
CONTAINER_NAME="${CONTAINER_NAME:-business-backend}"
HOST_PORT="${HOST_PORT:-8001}"
API_BASE_URL="${API_BASE_URL:-http://127.0.0.1:${HOST_PORT}}"

log() {
  printf '[docker-acceptance] %s\n' "$*"
}

wait_for_health() {
  local attempts="${1:-30}"
  local delay="${2:-1}"
  python3 - "$API_BASE_URL" "$attempts" "$delay" <<'PY'
import json
import sys
import time
import urllib.error
import urllib.request

base_url = sys.argv[1].rstrip('/')
attempts = int(sys.argv[2])
delay = float(sys.argv[3])
last_error = None
for _ in range(attempts):
    try:
        for path in ('/health', '/api/v2/health'):
            with urllib.request.urlopen(base_url + path, timeout=5) as response:
                body = response.read().decode('utf-8')
                if response.status != 200:
                    raise RuntimeError(f'{path} returned {response.status}: {body}')
                json.loads(body)
        print('HEALTH_OK')
        raise SystemExit(0)
    except Exception as exc:  # noqa: BLE001 - health retry script
        last_error = exc
        time.sleep(delay)
print(f'HEALTH_FAILED: {last_error}', file=sys.stderr)
raise SystemExit(1)
PY
}

log "repo root: $ROOT_DIR"
log "image: $IMAGE_NAME"
log "container: $CONTAINER_NAME"
log "api: $API_BASE_URL"

cd "$ROOT_DIR"

log "removing old container if present"
docker rm -f "$CONTAINER_NAME" >/dev/null 2>&1 || true

log "building backend image"
docker build -t "$IMAGE_NAME" -f "$BACKEND_DIR/Dockerfile" "$ROOT_DIR"

log "starting backend container with mock providers"
docker run -d \
  --name "$CONTAINER_NAME" \
  -p "${HOST_PORT}:8001" \
  -e APP_RUNTIME_MODE=local-demo \
  -e DATABASE_URL=sqlite:////app/aism-dev.db \
  -e LLM_PROVIDER=mock \
  -e ASR_PROVIDER=mock \
  -e OCR_PROVIDER=mock \
  -e VISION_PROVIDER=mock \
  "$IMAGE_NAME" >/dev/null

log "initializing clean container database"
docker exec "$CONTAINER_NAME" sh -lc "python3 - <<'PY'
from pathlib import Path
source = Path('/app/alembic.ini')
target = Path('/tmp/alembic.ini')
text = source.read_text()
text = text.replace('script_location = /root/business-clone/backend/alembic', 'script_location = /app/alembic')
text = text.replace('script_location = backend/alembic', 'script_location = /app/alembic')
text = text.replace('script_location = ./alembic', 'script_location = /app/alembic')
text = text.replace('sqlalchemy.url = sqlite:///./aism-dev.db', 'sqlalchemy.url = sqlite:////app/aism-dev.db')
target.write_text(text)
PY
rm -f /app/aism-dev.db /app/aism-dev.db-shm /app/aism-dev.db-wal
PYTHONPATH=/app alembic -c /tmp/alembic.ini upgrade head
PYTHONPATH=/app python3 scripts/bootstrap_v2_trial_data.py"

log "waiting for health"
wait_for_health 30 1

log "verifying container database state"
docker exec "$CONTAINER_NAME" sh -lc "python3 - <<'PY'
import sqlite3
con = sqlite3.connect('/app/aism-dev.db')
version = con.execute('select version_num from alembic_version').fetchone()[0]
table_count = con.execute(\"select count(*) from sqlite_master where type='table'\").fetchone()[0]
print(f'ALEMBIC_VERSION {version}')
print(f'TABLE_COUNT {table_count}')
if version != '20260425_01':
    raise SystemExit(f'unexpected alembic version: {version}')
if table_count < 42:
    raise SystemExit(f'unexpected table count: {table_count}')
PY"

log "running Phase 8/9/10 acceptance against Docker backend"
python3 "$BACKEND_DIR/scripts/test_phase8_acceptance.py"
python3 "$BACKEND_DIR/scripts/test_phase9_scenarios.py"
python3 "$BACKEND_DIR/test_e2e_phase10.py"

log "Docker backend acceptance passed"
log "container remains running: $CONTAINER_NAME on $API_BASE_URL"
