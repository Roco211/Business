from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable


BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent
DEFAULT_OUTPUT_DIR = BACKEND_ROOT / "devdata" / "pilot_shift_bundles"

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.devtools.live_pilot_preflight import (  # noqa: E402
    DEFAULT_LOGIN_EMAIL,
    DEFAULT_LOGIN_PASSWORD,
    READY_STATUS,
    run_live_pilot_preflight,
)
from app.devtools.trial_readiness import (  # noqa: E402
    TrialReadinessError,
    run_trial_readiness,
    _build_live_request,
    _expect_data_envelope,
    _expect_string,
)
from scripts.run_pilot_summary_check import run_pilot_summary_check  # noqa: E402

DEGRADED_STATUS = "degraded"
MODE_CLOSED = "closed"
MODE_SHADOW = "shadow"
MODE_OPEN = "open"
ALLOWED_CUTOVER_MODES = {MODE_CLOSED, MODE_SHADOW, MODE_OPEN}


class ShiftBundleExportError(RuntimeError):
    """Raised when pilot shift bundle export cannot complete."""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Export a compact pilot shift bundle for operator handoff or incident review.",
    )
    parser.add_argument(
        "--api-base-url",
        default="http://127.0.0.1:8001",
        help="Base URL for the running API service.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help="Destination directory for exported bundle JSON files.",
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
        help="Maximum acceptable fallback rate before summary degrades.",
    )
    parser.add_argument(
        "--max-low-confidence-rate",
        type=float,
        default=0.20,
        help="Maximum acceptable low-confidence rate before summary degrades.",
    )
    return parser


def _expect_object(value: object, *, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ShiftBundleExportError(f"{label} was not an object")
    return value


def _is_path_within_directory(*, target_path: Path, parent_dir: Path) -> bool:
    try:
        target_path.relative_to(parent_dir)
        return True
    except ValueError:
        return False


def _load_gitignored_directories() -> list[Path]:
    gitignore_path = REPO_ROOT / ".gitignore"
    if not gitignore_path.exists():
        return []

    ignored_directories: list[Path] = []
    for raw_line in gitignore_path.read_text(encoding="utf-8").splitlines():
        candidate = raw_line.strip()
        if not candidate or candidate.startswith("#") or candidate.startswith("!"):
            continue
        if any(token in candidate for token in ("*", "?", "[", "]")):
            continue
        normalized = candidate.rstrip("/").lstrip("/")
        if not normalized:
            continue
        ignored_directories.append((REPO_ROOT / normalized).resolve())
    return ignored_directories


def _run_git_check_ignore(path: Path) -> bool | None:
    if not _is_path_within_directory(target_path=path, parent_dir=REPO_ROOT):
        return None

    try:
        relative_path = path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return None

    try:
        candidate_paths = [relative_path]
        directory_candidate = relative_path.rstrip("/") + "/"
        if directory_candidate not in candidate_paths:
            candidate_paths.append(directory_candidate)
        for candidate_path in candidate_paths:
            result = subprocess.run(
                [
                    "git",
                    "-C",
                    str(REPO_ROOT),
                    "check-ignore",
                    "-q",
                    "--",
                    candidate_path,
                ],
                check=False,
            )
            if result.returncode == 0:
                return True
            if result.returncode not in (0, 1):
                return None
    except OSError:
        return None

    return False


def _is_gitignored_destination(path: Path) -> bool:
    git_result = _run_git_check_ignore(path)
    if git_result is not None:
        return git_result

    for ignored_directory in _load_gitignored_directories():
        if path == ignored_directory or _is_path_within_directory(target_path=path, parent_dir=ignored_directory):
            return True
    return False


def _validate_output_dir(output_dir: str) -> Path:
    destination = Path(output_dir).expanduser().resolve()
    if _is_path_within_directory(target_path=destination, parent_dir=REPO_ROOT):
        if not _is_gitignored_destination(destination):
            raise ShiftBundleExportError(
                "Output directory must be gitignored when writing inside the repository",
            )
    return destination


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


def _load_pilot_control(*, request_json, auth_token: str) -> dict[str, object]:
    status_code, body = request_json(
        "GET",
        "/api/v1/system/pilot-control",
        token=auth_token,
        payload=None,
    )
    data = _expect_data_envelope(
        status_code=status_code,
        body=body,
        label="GET /api/v1/system/pilot-control",
    )
    payload = _expect_object(data, label="GET /api/v1/system/pilot-control data")
    _expect_string(payload.get("shop_id"), label="GET /api/v1/system/pilot-control shop_id")
    _expect_string(payload.get("cutover_mode"), label="GET /api/v1/system/pilot-control cutover_mode")
    return payload


def _normalize_timestamp(now: datetime) -> datetime:
    if now.tzinfo is None:
        return now.replace(tzinfo=UTC)
    return now.astimezone(UTC)


def _compact_utc_timestamp(now: datetime) -> str:
    return now.strftime("%Y%m%dT%H%M%S%fZ")


def _iso_utc_timestamp(now: datetime) -> str:
    return now.strftime("%Y-%m-%dT%H:%M:%SZ")


def _append_reason(reasons: list[str], reason: object) -> None:
    if not isinstance(reason, str):
        return
    cleaned = reason.strip()
    if cleaned and cleaned not in reasons:
        reasons.append(cleaned)


def _append_reasons_with_fallback(
    *,
    reasons: list[str],
    raw_reasons: object,
    fallback_reason: str,
) -> None:
    reason_count_before = len(reasons)
    if isinstance(raw_reasons, list):
        for reason in raw_reasons:
            _append_reason(reasons, reason)
    if len(reasons) == reason_count_before:
        _append_reason(reasons, fallback_reason)


def _collect_degraded_reasons(
    *,
    readiness_payload: dict[str, object],
    preflight_payload: dict[str, object],
    pilot_control_payload: dict[str, object],
    pilot_summary_payload: dict[str, object],
) -> list[str]:
    reasons: list[str] = []

    if readiness_payload.get("overall_status") != READY_STATUS:
        _append_reason(reasons, "readiness_not_ready")

    if preflight_payload.get("overall_status") != READY_STATUS:
        _append_reasons_with_fallback(
            reasons=reasons,
            raw_reasons=preflight_payload.get("reasons"),
            fallback_reason="preflight_not_ready",
        )

    if pilot_summary_payload.get("overall_status") != READY_STATUS:
        pilot_summary_block = pilot_summary_payload.get("pilot_summary")
        if isinstance(pilot_summary_block, dict):
            _append_reasons_with_fallback(
                reasons=reasons,
                raw_reasons=pilot_summary_block.get("reasons"),
                fallback_reason="pilot_summary_not_ready",
            )
        else:
            _append_reason(reasons, "pilot_summary_not_ready")

    cutover_mode = pilot_control_payload.get("cutover_mode")
    if not isinstance(cutover_mode, str) or cutover_mode not in ALLOWED_CUTOVER_MODES:
        _append_reason(reasons, "pilot_control_cutover_mode_invalid")

    trial_provider_profile = pilot_control_payload.get("trial_provider_profile")
    if not isinstance(trial_provider_profile, str) or not trial_provider_profile.strip():
        _append_reason(reasons, "pilot_control_trial_provider_profile_missing")

    return reasons


def _write_json(path: Path, payload: object) -> None:
    path.write_text(
        json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )


def _ensure_directory(path: Path, *, label: str, exist_ok: bool) -> None:
    try:
        path.mkdir(parents=True, exist_ok=exist_ok)
    except FileExistsError as exc:
        raise ShiftBundleExportError(f"{label} already exists: {path}") from exc
    except OSError as exc:
        raise ShiftBundleExportError(f"Unable to create {label} '{path}': {exc}") from exc


def _write_json_artifact(path: Path, payload: object) -> None:
    try:
        _write_json(path, payload)
    except OSError as exc:
        raise ShiftBundleExportError(f"Unable to write bundle artifact '{path}': {exc}") from exc


def _cleanup_partial_bundle(bundle_dir: Path) -> None:
    if not bundle_dir.exists():
        return
    try:
        shutil.rmtree(bundle_dir)
    except OSError:
        return


def export_pilot_shift_bundle(
    *,
    api_base_url: str,
    output_dir: str,
    auth_token: str | None = None,
    login_email: str | None = None,
    login_password: str | None = None,
    hours: int = 24,
    max_fallback_rate: float = 0.05,
    max_low_confidence_rate: float = 0.20,
    now_fn: Callable[[], datetime] | None = None,
) -> dict[str, object]:
    if hours < 1:
        raise ShiftBundleExportError("--hours must be >= 1")

    destination_root = _validate_output_dir(output_dir)
    _ensure_directory(destination_root, label="output directory", exist_ok=True)

    request_json = _build_live_request(api_base_url)
    resolved_login_email = login_email or os.getenv("SEED_OWNER_EMAIL", DEFAULT_LOGIN_EMAIL)
    resolved_login_password = login_password or os.getenv("SEED_OWNER_PASSWORD", DEFAULT_LOGIN_PASSWORD)
    active_auth_token = _resolve_auth_token(
        auth_token=auth_token,
        login_email=resolved_login_email,
        login_password=resolved_login_password,
        request_json=request_json,
    )

    readiness_payload = run_trial_readiness(
        api_base_url=api_base_url,
        auth_token=active_auth_token,
        login_email=resolved_login_email,
        login_password=resolved_login_password,
        request_json=request_json,
    ).to_dict()
    preflight_payload = run_live_pilot_preflight(
        api_base_url=api_base_url,
        auth_token=active_auth_token,
        login_email=resolved_login_email,
        login_password=resolved_login_password,
        request_json=request_json,
    ).to_dict()
    pilot_control_payload = _load_pilot_control(
        request_json=request_json,
        auth_token=active_auth_token,
    )
    pilot_summary_payload = run_pilot_summary_check(
        api_base_url=api_base_url,
        auth_token=active_auth_token,
        login_email=resolved_login_email,
        login_password=resolved_login_password,
        hours=hours,
        max_fallback_rate=max_fallback_rate,
        max_low_confidence_rate=max_low_confidence_rate,
    )

    now = _normalize_timestamp((now_fn or (lambda: datetime.now(UTC)))())
    generated_at = _iso_utc_timestamp(now)
    bundle_id = f"shift_bundle_{_compact_utc_timestamp(now)}"
    bundle_dir = destination_root / bundle_id
    _ensure_directory(bundle_dir, label="bundle directory", exist_ok=False)

    try:
        artifacts: dict[str, dict[str, str]] = {}
        for artifact_name, payload in (
            ("readiness", readiness_payload),
            ("preflight", preflight_payload),
            ("pilot_control", pilot_control_payload),
            ("pilot_summary", pilot_summary_payload),
        ):
            file_name = f"{artifact_name}.json"
            _write_json_artifact(bundle_dir / file_name, payload)
            artifacts[artifact_name] = {
                "file": file_name,
                "captured_at": generated_at,
            }

        degraded_reasons = _collect_degraded_reasons(
            readiness_payload=readiness_payload,
            preflight_payload=preflight_payload,
            pilot_control_payload=pilot_control_payload,
            pilot_summary_payload=pilot_summary_payload,
        )
        overall_status = READY_STATUS if not degraded_reasons else DEGRADED_STATUS

        manifest_payload = {
            "bundle_id": bundle_id,
            "generated_at": generated_at,
            "api_base_url": api_base_url,
            "hours": hours,
            "shop_id": pilot_control_payload.get("shop_id"),
            "cutover_mode": pilot_control_payload.get("cutover_mode"),
            "trial_provider_profile": pilot_control_payload.get("trial_provider_profile"),
            "approved_calibration_artifact_id": pilot_control_payload.get("approved_calibration_artifact_id"),
            "overall_status": overall_status,
            "degraded_reasons": degraded_reasons,
            "artifacts": artifacts,
        }
        manifest_path = bundle_dir / "manifest.json"
        _write_json_artifact(manifest_path, manifest_payload)
    except ShiftBundleExportError:
        _cleanup_partial_bundle(bundle_dir)
        raise

    return {
        "bundle_id": bundle_id,
        "manifest_path": str(manifest_path),
        "overall_status": overall_status,
        "degraded_reasons": degraded_reasons,
    }


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        summary = export_pilot_shift_bundle(
            api_base_url=args.api_base_url,
            output_dir=args.output_dir,
            auth_token=args.auth_token,
            login_email=args.login_email,
            login_password=args.login_password,
            hours=args.hours,
            max_fallback_rate=args.max_fallback_rate,
            max_low_confidence_rate=args.max_low_confidence_rate,
        )
    except (ShiftBundleExportError, TrialReadinessError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(json.dumps(summary, sort_keys=True))
    return 0 if summary["overall_status"] == READY_STATUS else 1


if __name__ == "__main__":
    raise SystemExit(main())
