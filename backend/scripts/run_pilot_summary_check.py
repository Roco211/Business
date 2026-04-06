from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.devtools.trial_readiness import (
    DEFAULT_LOGIN_EMAIL,
    DEFAULT_LOGIN_PASSWORD,
    READY_STATUS,
    TrialReadinessError,
    TrialReadinessSummary,
    _build_live_request,
    _expect_data_envelope,
    _expect_string,
    run_trial_readiness,
)

DEGRADED_STATUS = "degraded"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run an operator-facing pilot summary check against the API.",
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
        "--hours",
        type=int,
        default=24,
        help="Rolling pilot summary window in hours.",
    )
    parser.add_argument(
        "--max-fallback-rate",
        type=float,
        default=0.05,
        help="Maximum acceptable fallback rate before the operator verdict degrades.",
    )
    parser.add_argument(
        "--max-low-confidence-rate",
        type=float,
        default=0.20,
        help="Maximum acceptable low-confidence rate before the operator verdict degrades.",
    )
    return parser


def _expect_object(value: object, *, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise TrialReadinessError(f"{label} was not an object")
    return value


def _expect_int(value: object, *, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TrialReadinessError(f"{label} was missing or not an integer")
    return value


def _normalize_nested_int_map(value: object, *, label: str) -> dict[str, dict[str, int]]:
    payload = _expect_object(value, label=label)
    normalized: dict[str, dict[str, int]] = {}
    for outer_key, outer_value in payload.items():
        if not isinstance(outer_key, str) or not outer_key:
            raise TrialReadinessError(f"{label} contained a non-string key")
        nested_payload = _expect_object(outer_value, label=f"{label}.{outer_key}")
        normalized[outer_key] = {}
        for inner_key, inner_value in nested_payload.items():
            if not isinstance(inner_key, str) or not inner_key:
                raise TrialReadinessError(f"{label}.{outer_key} contained a non-string key")
            normalized[outer_key][inner_key] = _expect_int(
                inner_value,
                label=f"{label}.{outer_key}.{inner_key}",
            )
    return normalized


def _normalize_flat_int_map(value: object, *, label: str) -> dict[str, int]:
    payload = _expect_object(value, label=label)
    normalized: dict[str, int] = {}
    for key, item_value in payload.items():
        if not isinstance(key, str) or not key:
            raise TrialReadinessError(f"{label} contained a non-string key")
        normalized[key] = _expect_int(item_value, label=f"{label}.{key}")
    return normalized


def _resolve_auth_token(
    *,
    auth_token: str | None,
    login_email: str,
    login_password: str,
    request_json,
) -> str:
    if auth_token is not None:
        return auth_token

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


def _load_pilot_summary(
    *,
    request_json,
    auth_token: str,
    hours: int,
) -> dict[str, object]:
    status_code, body = request_json(
        "GET",
        f"/api/v1/system/pilot-summary?hours={hours}",
        token=auth_token,
        payload=None,
    )
    data = _expect_data_envelope(
        status_code=status_code,
        body=body,
        label="GET /api/v1/system/pilot-summary",
    )
    summary_payload = _expect_object(data, label="GET /api/v1/system/pilot-summary data")
    time_window = _expect_object(
        summary_payload.get("time_window"),
        label="GET /api/v1/system/pilot-summary time_window",
    )
    confirmations = _expect_object(
        summary_payload.get("confirmations"),
        label="GET /api/v1/system/pilot-summary confirmations",
    )
    return {
        "time_window": {
            "hours": _expect_int(time_window.get("hours"), label="Pilot summary time_window.hours"),
            "started_at": _expect_string(
                time_window.get("started_at"),
                label="Pilot summary time_window.started_at",
            ),
            "ended_at": _expect_string(
                time_window.get("ended_at"),
                label="Pilot summary time_window.ended_at",
            ),
        },
        "task_totals": _normalize_nested_int_map(
            summary_payload.get("task_totals"),
            label="GET /api/v1/system/pilot-summary task_totals",
        ),
        "confirmations": {
            "created": _expect_int(
                confirmations.get("created"),
                label="Pilot summary confirmations.created",
            ),
            "approved": _expect_int(
                confirmations.get("approved"),
                label="Pilot summary confirmations.approved",
            ),
            "rejected": _expect_int(
                confirmations.get("rejected"),
                label="Pilot summary confirmations.rejected",
            ),
        },
        "low_confidence_count": _expect_int(
            summary_payload.get("low_confidence_count"),
            label="Pilot summary low_confidence_count",
        ),
        "fallback_count": _expect_int(
            summary_payload.get("fallback_count"),
            label="Pilot summary fallback_count",
        ),
        "provider_failures": _normalize_flat_int_map(
            summary_payload.get("provider_failures"),
            label="GET /api/v1/system/pilot-summary provider_failures",
        ),
        "trial_provider_profile": str(summary_payload.get("trial_provider_profile") or ""),
    }


def _compute_rate(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return numerator / denominator


def _build_pilot_summary_verdict(
    *,
    pilot_summary: dict[str, object],
    max_fallback_rate: float,
    max_low_confidence_rate: float,
) -> dict[str, object]:
    task_totals = pilot_summary["task_totals"]
    confirmations = pilot_summary["confirmations"]
    fallback_count = pilot_summary["fallback_count"]
    low_confidence_count = pilot_summary["low_confidence_count"]
    provider_failures = pilot_summary["provider_failures"]
    trial_provider_profile = pilot_summary["trial_provider_profile"]

    total_task_count = sum(
        status_count
        for status_map in task_totals.values()
        for status_count in status_map.values()
    )
    confirmation_rate = _compute_rate(confirmations["created"], total_task_count)
    rejection_rate = _compute_rate(confirmations["rejected"], confirmations["created"])
    fallback_rate = _compute_rate(fallback_count, total_task_count)
    low_confidence_rate = _compute_rate(low_confidence_count, total_task_count)

    reasons: list[str] = []
    if not str(trial_provider_profile).strip():
        reasons.append("trial_provider_profile_missing")
    if provider_failures:
        reasons.append("provider_failures_present")
    if fallback_rate > max_fallback_rate:
        reasons.append("fallback_rate_exceeded")
    if low_confidence_rate > max_low_confidence_rate:
        reasons.append("low_confidence_rate_exceeded")

    return {
        "confirmations": confirmations,
        "confirmation_rate": confirmation_rate,
        "fallback_count": fallback_count,
        "fallback_rate": fallback_rate,
        "low_confidence_count": low_confidence_count,
        "low_confidence_rate": low_confidence_rate,
        "overall_status": READY_STATUS if not reasons else DEGRADED_STATUS,
        "provider_failures": provider_failures,
        "reasons": reasons,
        "rejection_rate": rejection_rate,
        "task_totals": task_totals,
        "time_window": pilot_summary["time_window"],
        "total_task_count": total_task_count,
        "trial_provider_profile": trial_provider_profile,
    }


def run_pilot_summary_check(
    *,
    api_base_url: str,
    auth_token: str | None = None,
    login_email: str | None = None,
    login_password: str | None = None,
    hours: int = 24,
    max_fallback_rate: float = 0.05,
    max_low_confidence_rate: float = 0.20,
) -> dict[str, object]:
    request_json = _build_live_request(api_base_url)
    resolved_login_email = login_email or os.getenv("SEED_OWNER_EMAIL", DEFAULT_LOGIN_EMAIL)
    resolved_login_password = login_password or os.getenv("SEED_OWNER_PASSWORD", DEFAULT_LOGIN_PASSWORD)
    active_auth_token = _resolve_auth_token(
        auth_token=auth_token,
        login_email=resolved_login_email,
        login_password=resolved_login_password,
        request_json=request_json,
    )
    readiness = run_trial_readiness(
        api_base_url=api_base_url,
        auth_token=active_auth_token,
        login_email=resolved_login_email,
        login_password=resolved_login_password,
        request_json=request_json,
    )
    pilot_summary = _load_pilot_summary(
        request_json=request_json,
        auth_token=active_auth_token,
        hours=hours,
    )
    pilot_summary_verdict = _build_pilot_summary_verdict(
        pilot_summary=pilot_summary,
        max_fallback_rate=max_fallback_rate,
        max_low_confidence_rate=max_low_confidence_rate,
    )
    overall_status = READY_STATUS
    if readiness.overall_status != READY_STATUS or pilot_summary_verdict["overall_status"] != READY_STATUS:
        overall_status = DEGRADED_STATUS

    return {
        "api_base_url": api_base_url,
        "hours": hours,
        "overall_status": overall_status,
        "pilot_summary": pilot_summary_verdict,
        "readiness": readiness.to_dict(),
        "thresholds": {
            "max_fallback_rate": max_fallback_rate,
            "max_low_confidence_rate": max_low_confidence_rate,
        },
    }


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = run_pilot_summary_check(
            api_base_url=args.api_base_url,
            auth_token=args.auth_token,
            login_email=args.login_email,
            login_password=args.login_password,
            hours=args.hours,
            max_fallback_rate=args.max_fallback_rate,
            max_low_confidence_rate=args.max_low_confidence_rate,
        )
    except TrialReadinessError as exc:
        print(f"Pilot summary check failed: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(result, sort_keys=True))
    return 0 if result["overall_status"] == READY_STATUS else 1


if __name__ == "__main__":
    raise SystemExit(main())
