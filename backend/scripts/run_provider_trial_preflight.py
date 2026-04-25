from __future__ import annotations

import json
import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.devtools.provider_trial_preflight import READY_STATUS, run_provider_trial_preflight


def main() -> int:
    result = run_provider_trial_preflight()
    print(json.dumps(result.to_dict(), ensure_ascii=False, sort_keys=True))
    return 0 if result.overall_status == READY_STATUS else 1


if __name__ == "__main__":
    raise SystemExit(main())
