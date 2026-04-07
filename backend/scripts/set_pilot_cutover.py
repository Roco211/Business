from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
from typing import Any


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.devtools.live_pilot_preflight import (
    DEFAULT_LOGIN_EMAIL,
    DEFAULT_LOGIN_PASSWORD,
    READY_STATUS,
    run_live_pilot_preflight,
)
from app.devtools.trial_readiness import (
    TrialReadinessError,
    _build_live_request,
    _expect_data_envelope,
    _expect_string,
)

MODE_CLOSED = "closed"
MODE_SHADOW = "shadow"
MODE_OPEN = "open"


class PilotCutoverError(RuntimeError):
    """Raised when pilot cutover mutation cannot be completed."""


def _expect_object(value: object, *, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise PilotCutoverError(f"{label} was not an object")
    return value


def _resolve_auth_token(
    *,
    auth_token: str | None,
    login_email: str,
    login_password: str,
    api_base_url: str,
) -> str:
    if auth_token is not None:
        return auth_token

    request_json = _build_live_request(api_base_url)
    status_code, body = request_json(
        "POST",
        "/api/v1/auth/login",
        token=None,
        payload={"email": login_email, "password": login_password},
    )
    login_data = _expect_data_envelope(
        status_code=status_code,
        body=body,
        label="POST /api/v1/auth/login",
    )
    login_payload = _expect_object(login_data, label="POST /api/v1/auth/login data")
    return _expect_string(
        login_payload.get("access_token"),
        label="POST /api/v1/auth/login access_token",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Set pilot cutover mode via protected operator mutation flow.",
    )
    parser.add_argument(
        "--api-base-url",
        default="http://127.0.0.1:8001",
        help="Base URL for the running API service.",
    )
    parser.add_argument(
        "--mode",
        required=True,
        choices=[MODE_CLOSED, MODE_SHADOW, MODE_OPEN],
        help="Target cutover mode.",
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
        help="Optional calibration artifact JSON path; also used as report-path mutation value.",
    )
    parser.add_argument(
        "--note",
        default=None,
        help="Optional operator note stored with the mutation.",
    )
    parser.add_argument(
        "--skip-preflight",
        action="store_true",
        help="Skip live preflight check before opening cutover mode.",
    )
    return parser


def _build_mutation_payload(*, args: argparse.Namespace, preflight_ready: bool) -> dict[str, object]:
    return {
        "cutover_mode": args.mode,
        "approved_calibration_report_path": args.artifact_path,
        "last_preflight_status": READY_STATUS if (args.mode == MODE_OPEN and preflight_ready) else None,
        "notes": args.note,
    }


def _run_optional_open_preflight(args: argparse.Namespace) -> bool:
    if args.mode != MODE_OPEN or args.skip_preflight:
        return False

    summary = run_live_pilot_preflight(
        api_base_url=args.api_base_url,
        auth_token=args.auth_token,
        login_email=args.login_email,
        login_password=args.login_password,
        artifact_path=args.artifact_path,
    )
    if summary.overall_status != READY_STATUS:
        raise PilotCutoverError(f"Cutover preflight failed: {json.dumps(summary.to_dict(), sort_keys=True)}")
    return True


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        preflight_ready = _run_optional_open_preflight(args)
        active_auth_token = _resolve_auth_token(
            auth_token=args.auth_token,
            login_email=args.login_email,
            login_password=args.login_password,
            api_base_url=args.api_base_url,
        )
        request_json = _build_live_request(args.api_base_url)
        status_code, body = request_json(
            "POST",
            "/api/v1/system/pilot-control",
            token=active_auth_token,
            payload=_build_mutation_payload(args=args, preflight_ready=preflight_ready),
        )
        if status_code != 200:
            if isinstance(body, dict):
                error_code = body.get("error", {}).get("code")
                error_message = body.get("error", {}).get("message")
                raise PilotCutoverError(
                    f"Pilot cutover mutation failed: HTTP {status_code} "
                    f"code={error_code!r} message={error_message!r}"
                )
            raise PilotCutoverError(f"Pilot cutover mutation failed: HTTP {status_code}")

        data = _expect_data_envelope(
            status_code=status_code,
            body=body,
            label="POST /api/v1/system/pilot-control",
        )
        payload = _expect_object(data, label="POST /api/v1/system/pilot-control data")
    except (PilotCutoverError, TrialReadinessError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(
        json.dumps(
            {
                "shop_id": payload.get("shop_id"),
                "previous_cutover_mode": payload.get("previous_cutover_mode"),
                "cutover_mode": payload.get("cutover_mode"),
                "transition_audit_log_id": payload.get("transition_audit_log_id"),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
