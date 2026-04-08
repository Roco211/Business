from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.devtools.live_pilot_preflight import (
    DEFAULT_LOGIN_EMAIL,
    DEFAULT_LOGIN_PASSWORD,
    LivePilotPreflightError,
    READY_STATUS,
    run_live_pilot_preflight,
)
from app.devtools.trial_readiness import TrialReadinessError


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run an operator-focused live-pilot preflight check against the API.",
    )
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
    parser.add_argument(
        "--artifact-path",
        default=None,
        help="Optional local path override for the approved calibration artifact JSON.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = run_live_pilot_preflight(
            api_base_url=args.api_base_url,
            auth_token=args.auth_token,
            login_email=args.login_email,
            login_password=args.login_password,
            artifact_path=args.artifact_path,
        )
    except (LivePilotPreflightError, TrialReadinessError) as exc:
        print(f"Live pilot preflight failed: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(result.to_dict(), sort_keys=True))
    return 0 if result.overall_status == READY_STATUS else 1


if __name__ == "__main__":
    raise SystemExit(main())
