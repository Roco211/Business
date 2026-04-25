from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient

from app.main import create_app


REQUIRED_EXPORT_PATHS = {
    "/api/v2/exports/sales-orders",
    "/api/v2/exports/purchase-orders",
    "/api/v2/exports/finance-transactions",
    "/api/v2/exports/inventory-ledger",
}


def main() -> int:
    os.environ.setdefault("APP_RUNTIME_MODE", "local-demo")
    os.environ.setdefault("LLM_PROVIDER", "mock")
    os.environ.setdefault("ASR_PROVIDER", "mock")
    os.environ.setdefault("OCR_PROVIDER", "mock")
    os.environ.setdefault("VISION_PROVIDER", "mock")
    os.environ.setdefault("APP_RATE_LIMIT_PER_MINUTE", "0")

    client = TestClient(create_app(), raise_server_exceptions=False)
    statuses = []
    for _ in range(25):
        response = client.get("/api/v2/health")
        statuses.append(response.status_code)
        if response.status_code != 200:
            print(json.dumps({"status": "failed", "reason": "health_check_failed", "statuses": statuses}, ensure_ascii=False))
            return 1

    openapi = client.get("/openapi.json")
    if openapi.status_code != 200:
        print(json.dumps({"status": "failed", "reason": "openapi_failed", "status_code": openapi.status_code}, ensure_ascii=False))
        return 1
    paths = set((openapi.json().get("paths") or {}).keys())
    missing_paths = sorted(REQUIRED_EXPORT_PATHS - paths)
    if missing_paths:
        print(json.dumps({"status": "failed", "reason": "missing_export_paths", "missing_paths": missing_paths}, ensure_ascii=False))
        return 1

    print(json.dumps({"status": "passed", "health_checks": len(statuses), "export_paths": sorted(REQUIRED_EXPORT_PATHS)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
