from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.devtools.local_demo_smoke import (
    DEFAULT_LOGIN_EMAIL,
    DEFAULT_LOGIN_PASSWORD,
    LocalDemoSmokeError,
    run_local_demo_smoke,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a live local-demo smoke check against the API.")
    parser.add_argument(
        "--api-base-url",
        default="http://127.0.0.1:8001",
        help="Base URL for the running API service.",
    )
    parser.add_argument(
        "--auth-token",
        default=None,
        help="Optional bearer token for protected calls. When omitted, the script logs in first.",
    )
    parser.add_argument(
        "--login-email",
        default=os.getenv("SEED_OWNER_EMAIL", DEFAULT_LOGIN_EMAIL),
        help="Login email used to fetch a bearer token when --auth-token is omitted.",
    )
    parser.add_argument(
        "--login-password",
        default=os.getenv("SEED_OWNER_PASSWORD", DEFAULT_LOGIN_PASSWORD),
        help="Login password used to fetch a bearer token when --auth-token is omitted.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        result = run_local_demo_smoke(
            api_base_url=args.api_base_url,
            auth_token=args.auth_token,
            login_email=args.login_email,
            login_password=args.login_password,
        )
    except LocalDemoSmokeError as exc:
        print(f"Local demo smoke failed: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(result.to_dict(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
