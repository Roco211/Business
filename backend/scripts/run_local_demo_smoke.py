from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.devtools.local_demo_smoke import LocalDemoSmokeError, run_local_demo_smoke


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a live local-demo smoke check against the API.")
    parser.add_argument(
        "--api-base-url",
        default="http://127.0.0.1:8001",
        help="Base URL for the running API service.",
    )
    parser.add_argument(
        "--auth-token",
        default="mock_owner_token",
        help="Owner auth token used for the current MVP smoke flow.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        result = run_local_demo_smoke(
            api_base_url=args.api_base_url,
            auth_token=args.auth_token,
        )
    except LocalDemoSmokeError as exc:
        print(f"Local demo smoke failed: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(result.to_dict(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
