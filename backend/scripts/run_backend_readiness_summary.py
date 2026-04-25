from __future__ import annotations

import json
import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.devtools.backend_readiness_summary import READY_STATUS, build_backend_readiness_summary


def main() -> int:
    summary = build_backend_readiness_summary(repo_root=REPO_ROOT)
    print(json.dumps(summary.to_dict(), ensure_ascii=False, sort_keys=True))
    return 0 if summary.overall_status == READY_STATUS else 1


if __name__ == "__main__":
    raise SystemExit(main())
