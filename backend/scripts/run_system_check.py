from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from scripts.export_pilot_shift_bundle import (  # noqa: E402
    DEFAULT_OUTPUT_DIR,
    ShiftBundleExportError,
    export_pilot_shift_bundle,
)
from scripts.run_local_demo_smoke import (  # noqa: E402
    DEFAULT_LOGIN_EMAIL,
    DEFAULT_LOGIN_PASSWORD,
    LocalDemoSmokeError,
    run_local_demo_smoke,
)
from scripts.run_trial_readiness_check import (  # noqa: E402
    READY_STATUS,
    TrialReadinessError,
    run_trial_readiness,
)

MODE_LOCAL_DEMO = "local-demo"
MODE_TRIAL = "trial"
MODE_PILOT = "pilot"
MODE_CHOICES = (MODE_LOCAL_DEMO, MODE_TRIAL, MODE_PILOT)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run a unified system check across local-demo, trial, and pilot modes.",
    )
    parser.add_argument("--mode", required=True, choices=MODE_CHOICES, help="System check mode to run.")
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
        help="Rolling pilot-summary window in hours.",
    )
    parser.add_argument(
        "--max-fallback-rate",
        type=float,
        default=0.05,
        help="Maximum acceptable fallback rate before the pilot bundle degrades.",
    )
    parser.add_argument(
        "--max-low-confidence-rate",
        type=float,
        default=0.20,
        help="Maximum acceptable low-confidence rate before the pilot bundle degrades.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help="Destination directory for exported pilot shift bundle JSON files.",
    )
    return parser


def _build_verdict(
    *,
    mode: str,
    overall_status: str,
    checks: dict[str, object],
    reasons: list[str] | None = None,
) -> dict[str, object]:
    verdict = {
        "mode": mode,
        "overall_status": overall_status,
        "checks": checks,
    }
    if reasons is not None:
        verdict["reasons"] = reasons
    return verdict


def _load_json_object(*, path: Path, label: str) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ShiftBundleExportError(f"Unable to read {label} '{path}': {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ShiftBundleExportError(f"Unable to decode {label} '{path}': {exc}") from exc

    if not isinstance(payload, dict):
        raise ShiftBundleExportError(f"{label} '{path}' did not contain a JSON object")

    return payload


def _load_manifest_artifact_path(
    *,
    manifest_path: Path,
    artifacts: dict[str, object],
    manifest_key: str,
) -> Path:
    artifact_entry = artifacts.get(manifest_key)
    if not isinstance(artifact_entry, dict):
        raise ShiftBundleExportError(f"Shift bundle manifest missing artifacts.{manifest_key}")

    artifact_file = artifact_entry.get("file")
    if not isinstance(artifact_file, str) or not artifact_file.strip():
        raise ShiftBundleExportError(f"Shift bundle manifest missing artifacts.{manifest_key}.file")

    artifact_path = (manifest_path.parent / artifact_file).resolve()
    try:
        artifact_path.relative_to(manifest_path.parent.resolve())
    except ValueError as exc:
        raise ShiftBundleExportError(
            f"Shift bundle artifact '{artifact_file}' escaped the bundle directory",
        ) from exc
    return artifact_path


def _load_shift_bundle_checks(manifest_path_value: object) -> dict[str, dict[str, object]]:
    if not isinstance(manifest_path_value, str) or not manifest_path_value.strip():
        raise ShiftBundleExportError("Shift bundle result missing manifest_path")

    manifest_path = Path(manifest_path_value).expanduser().resolve()
    manifest_payload = _load_json_object(path=manifest_path, label="shift bundle manifest")
    artifacts = manifest_payload.get("artifacts")
    if not isinstance(artifacts, dict):
        raise ShiftBundleExportError("Shift bundle manifest missing artifacts")

    artifact_mapping = {
        "trial_readiness": "readiness",
        "live_pilot_preflight": "preflight",
        "pilot_summary": "pilot_summary",
    }
    checks: dict[str, dict[str, object]] = {}
    for check_name, manifest_key in artifact_mapping.items():
        artifact_path = _load_manifest_artifact_path(
            manifest_path=manifest_path,
            artifacts=artifacts,
            manifest_key=manifest_key,
        )
        checks[check_name] = _load_json_object(
            path=artifact_path,
            label=f"shift bundle artifact '{manifest_key}'",
        )
    return checks


def _normalize_reason_list(raw_reasons: object, *, fallback_reason: str | None = None) -> list[str]:
    reasons: list[str] = []
    if isinstance(raw_reasons, list):
        for reason in raw_reasons:
            if not isinstance(reason, str):
                continue
            cleaned_reason = reason.strip()
            if cleaned_reason and cleaned_reason not in reasons:
                reasons.append(cleaned_reason)
    if not reasons and fallback_reason is not None:
        reasons.append(fallback_reason)
    return reasons


def run_system_check(
    *,
    mode: str,
    api_base_url: str,
    auth_token: str | None = None,
    login_email: str | None = None,
    login_password: str | None = None,
    hours: int = 24,
    max_fallback_rate: float = 0.05,
    max_low_confidence_rate: float = 0.20,
    output_dir: str = str(DEFAULT_OUTPUT_DIR),
) -> dict[str, object]:
    resolved_login_email = login_email or os.getenv("SEED_OWNER_EMAIL", DEFAULT_LOGIN_EMAIL)
    resolved_login_password = login_password or os.getenv("SEED_OWNER_PASSWORD", DEFAULT_LOGIN_PASSWORD)

    if mode == MODE_LOCAL_DEMO:
        result = run_local_demo_smoke(
            api_base_url=api_base_url,
            auth_token=auth_token,
            login_email=resolved_login_email,
            login_password=resolved_login_password,
        )
        return _build_verdict(
            mode=mode,
            overall_status=READY_STATUS,
            checks={"local_demo": result.to_dict()},
        )

    if mode == MODE_TRIAL:
        result = run_trial_readiness(
            api_base_url=api_base_url,
            auth_token=auth_token,
            login_email=resolved_login_email,
            login_password=resolved_login_password,
        )
        return _build_verdict(
            mode=mode,
            overall_status=result.overall_status,
            checks={"trial_readiness": result.to_dict()},
        )

    if mode == MODE_PILOT:
        result = export_pilot_shift_bundle(
            api_base_url=api_base_url,
            output_dir=output_dir,
            auth_token=auth_token,
            login_email=resolved_login_email,
            login_password=resolved_login_password,
            hours=hours,
            max_fallback_rate=max_fallback_rate,
            max_low_confidence_rate=max_low_confidence_rate,
        )
        pilot_checks = _load_shift_bundle_checks(result.get("manifest_path"))
        reasons = _normalize_reason_list(
            result.get("degraded_reasons"),
            fallback_reason="shift_bundle_not_ready" if str(result["overall_status"]) != READY_STATUS else None,
        )
        return _build_verdict(
            mode=mode,
            overall_status=str(result["overall_status"]),
            checks={
                **pilot_checks,
                "shift_bundle": result,
            },
            reasons=reasons,
        )

    raise ValueError(f"Unsupported mode: {mode}")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        verdict = run_system_check(
            mode=args.mode,
            api_base_url=args.api_base_url,
            auth_token=args.auth_token,
            login_email=args.login_email,
            login_password=args.login_password,
            hours=args.hours,
            max_fallback_rate=args.max_fallback_rate,
            max_low_confidence_rate=args.max_low_confidence_rate,
            output_dir=args.output_dir,
        )
    except Exception as exc:  # noqa: BLE001 - operator-facing CLI should fail closed with a single verdict line
        print(f"System check failed: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(verdict, sort_keys=True))
    return 0 if verdict["overall_status"] == READY_STATUS else 1


if __name__ == "__main__":
    raise SystemExit(main())
