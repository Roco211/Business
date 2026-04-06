from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
from typing import Any

from app.devtools.trial_readiness import (
    DEFAULT_LOGIN_EMAIL,
    DEFAULT_LOGIN_PASSWORD,
    DEGRADED_STATUS,
    READY_STATUS,
    RequestJson,
    _build_live_request,
    _expect_data_envelope,
    _expect_status_ok,
    _expect_string,
)

TRIAL_RUNTIME_MODE = "trial"


class LivePilotPreflightError(RuntimeError):
    """Raised when live-pilot preflight checks cannot be completed."""


@dataclass(frozen=True)
class LivePilotPreflightSummary:
    overall_status: str
    runtime_mode: str
    trial_provider_profile: str
    cutover_mode: str
    approved_calibration_artifact_id: str
    reasons: list[str]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _expect_object(value: object, *, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise LivePilotPreflightError(f"{label} was not an object")
    return value


def _expect_optional_string(value: object, *, label: str) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        raise LivePilotPreflightError(f"{label} was not a string")
    return value.strip()


def _coerce_optional_string_with_reason(
    value: object,
    *,
    invalid_type_reason: str,
    reasons: list[str],
) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        reasons.append(invalid_type_reason)
        return ""
    return value.strip()


def _append_mismatch_reason(
    *,
    left_value: str,
    right_value: str,
    mismatch_reason: str,
    reasons: list[str],
) -> None:
    if left_value and right_value and left_value != right_value:
        reasons.append(mismatch_reason)


def _resolve_auth_token(
    *,
    auth_token: str | None,
    login_email: str | None,
    login_password: str | None,
    request_json: RequestJson,
) -> str:
    if auth_token is not None:
        return auth_token

    resolved_login_email = login_email or os.getenv("SEED_OWNER_EMAIL", DEFAULT_LOGIN_EMAIL)
    resolved_login_password = login_password or os.getenv("SEED_OWNER_PASSWORD", DEFAULT_LOGIN_PASSWORD)
    status_code, body = request_json(
        "POST",
        "/api/v1/auth/login",
        token=None,
        payload={"email": resolved_login_email, "password": resolved_login_password},
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


def _is_absolute_like(path_value: str) -> bool:
    normalized = path_value.strip()
    return bool(normalized) and (Path(normalized).is_absolute() or normalized.startswith("/") or normalized.startswith("\\"))


def _normalize_shop_allowlist(raw_allowlist: str) -> list[str]:
    return [shop_id.strip() for shop_id in raw_allowlist.split(",") if shop_id.strip()]


def _is_path_within_directory(*, target_path: Path, parent_dir: Path) -> bool:
    try:
        target_path.relative_to(parent_dir)
        return True
    except ValueError:
        return False


def run_live_pilot_preflight(
    *,
    api_base_url: str,
    auth_token: str | None = None,
    login_email: str | None = None,
    login_password: str | None = None,
    artifact_path: str | None = None,
    request_json: RequestJson | None = None,
) -> LivePilotPreflightSummary:
    request = request_json or _build_live_request(api_base_url)
    active_auth_token = _resolve_auth_token(
        auth_token=auth_token,
        login_email=login_email,
        login_password=login_password,
        request_json=request,
    )

    health_status_code, health_body = request("GET", "/health", token=None, payload=None)
    health_payload = _expect_status_ok(status_code=health_status_code, body=health_body, label="GET /health")
    health_status = _expect_string(health_payload.get("status"), label="GET /health status")
    if health_status != "ok":
        raise LivePilotPreflightError("Health status was not ok")

    readiness_status_code, readiness_body = request(
        "GET",
        "/api/v1/system/readiness",
        token=active_auth_token,
        payload=None,
    )
    readiness_data = _expect_data_envelope(
        status_code=readiness_status_code,
        body=readiness_body,
        label="GET /api/v1/system/readiness",
    )
    readiness_payload = _expect_object(readiness_data, label="GET /api/v1/system/readiness data")
    readiness_overall_status = _expect_string(
        readiness_payload.get("overall_status"),
        label="GET /api/v1/system/readiness overall_status",
    )
    runtime_mode = _expect_string(
        readiness_payload.get("runtime_mode"),
        label="GET /api/v1/system/readiness runtime_mode",
    )
    trial_provider_profile = _expect_optional_string(
        readiness_payload.get("trial_provider_profile"),
        label="GET /api/v1/system/readiness trial_provider_profile",
    )

    checks = _expect_object(
        readiness_payload.get("checks"),
        label="GET /api/v1/system/readiness checks",
    )
    trial_profile_check = _expect_object(checks.get("trial_profile"), label="Readiness checks.trial_profile")
    trial_profile_details = _expect_object(
        trial_profile_check.get("details"),
        label="Readiness checks.trial_profile.details",
    )
    asr_check = _expect_object(checks.get("asr"), label="Readiness checks.asr")
    ocr_check = _expect_object(checks.get("ocr"), label="Readiness checks.ocr")
    vision_check = _expect_object(checks.get("vision"), label="Readiness checks.vision")
    asr_details = _expect_object(asr_check.get("details"), label="Readiness checks.asr.details")
    ocr_details = _expect_object(ocr_check.get("details"), label="Readiness checks.ocr.details")
    vision_details = _expect_object(vision_check.get("details"), label="Readiness checks.vision.details")

    pilot_control_status_code, pilot_control_body = request(
        "GET",
        "/api/v1/system/pilot-control",
        token=active_auth_token,
        payload=None,
    )
    pilot_control_data = _expect_data_envelope(
        status_code=pilot_control_status_code,
        body=pilot_control_body,
        label="GET /api/v1/system/pilot-control",
    )
    pilot_control_payload = _expect_object(
        pilot_control_data,
        label="GET /api/v1/system/pilot-control data",
    )
    shop_id = _expect_string(
        pilot_control_payload.get("shop_id"),
        label="GET /api/v1/system/pilot-control shop_id",
    )
    cutover_mode = _expect_string(
        pilot_control_payload.get("cutover_mode"),
        label="GET /api/v1/system/pilot-control cutover_mode",
    )
    approved_calibration_artifact_id = _expect_optional_string(
        pilot_control_payload.get("approved_calibration_artifact_id"),
        label="GET /api/v1/system/pilot-control approved_calibration_artifact_id",
    )
    pilot_control_trial_provider_profile = _expect_optional_string(
        pilot_control_payload.get("trial_provider_profile"),
        label="GET /api/v1/system/pilot-control trial_provider_profile",
    )
    approved_calibration_report_path = _expect_optional_string(
        pilot_control_payload.get("approved_calibration_report_path"),
        label="GET /api/v1/system/pilot-control approved_calibration_report_path",
    )

    reasons: list[str] = []
    if readiness_overall_status != READY_STATUS:
        reasons.append("readiness_not_ready")
    if runtime_mode.strip().lower() != TRIAL_RUNTIME_MODE:
        reasons.append("runtime_mode_not_trial")
    if not trial_provider_profile:
        reasons.append("trial_provider_profile_missing")

    for field_name in (
        "trial_provider_profile",
        "asr_provider_label",
        "ocr_provider_label",
        "vision_provider_label",
        "trial_calibration_dataset_dir",
        "trial_calibration_artifacts_dir",
        "allowed_live_pilot_shop_ids",
    ):
        metadata_value = trial_profile_details.get(field_name)
        if not isinstance(metadata_value, str) or not metadata_value.strip():
            reasons.append(f"trial_profile_details_{field_name}_missing")

    trial_profile_details_profile = _coerce_optional_string_with_reason(
        trial_profile_details.get("trial_provider_profile"),
        invalid_type_reason="trial_profile_details_trial_provider_profile_invalid_type",
        reasons=reasons,
    )
    _append_mismatch_reason(
        left_value=trial_provider_profile,
        right_value=trial_profile_details_profile,
        mismatch_reason="trial_provider_profile_mismatch_readiness_vs_trial_profile_details",
        reasons=reasons,
    )
    _append_mismatch_reason(
        left_value=trial_provider_profile,
        right_value=pilot_control_trial_provider_profile,
        mismatch_reason="trial_provider_profile_mismatch_readiness_vs_pilot_control",
        reasons=reasons,
    )
    _append_mismatch_reason(
        left_value=trial_profile_details_profile,
        right_value=pilot_control_trial_provider_profile,
        mismatch_reason="trial_provider_profile_mismatch_trial_profile_details_vs_pilot_control",
        reasons=reasons,
    )

    asr_trial_profile_label = _coerce_optional_string_with_reason(
        trial_profile_details.get("asr_provider_label"),
        invalid_type_reason="trial_profile_details_asr_provider_label_invalid_type",
        reasons=reasons,
    )
    ocr_trial_profile_label = _coerce_optional_string_with_reason(
        trial_profile_details.get("ocr_provider_label"),
        invalid_type_reason="trial_profile_details_ocr_provider_label_invalid_type",
        reasons=reasons,
    )
    vision_trial_profile_label = _coerce_optional_string_with_reason(
        trial_profile_details.get("vision_provider_label"),
        invalid_type_reason="trial_profile_details_vision_provider_label_invalid_type",
        reasons=reasons,
    )

    for field_name, value in (
        ("asr_provider_label", asr_details.get("provider_label")),
        ("ocr_provider_label", ocr_details.get("provider_label")),
        ("vision_provider_label", vision_details.get("provider_label")),
    ):
        if not isinstance(value, str) or not value.strip():
            reasons.append(f"{field_name}_missing")

    asr_readiness_label = _coerce_optional_string_with_reason(
        asr_details.get("provider_label"),
        invalid_type_reason="asr_provider_label_invalid_type",
        reasons=reasons,
    )
    ocr_readiness_label = _coerce_optional_string_with_reason(
        ocr_details.get("provider_label"),
        invalid_type_reason="ocr_provider_label_invalid_type",
        reasons=reasons,
    )
    vision_readiness_label = _coerce_optional_string_with_reason(
        vision_details.get("provider_label"),
        invalid_type_reason="vision_provider_label_invalid_type",
        reasons=reasons,
    )
    _append_mismatch_reason(
        left_value=asr_readiness_label,
        right_value=asr_trial_profile_label,
        mismatch_reason="asr_provider_label_mismatch_readiness_vs_trial_profile_details",
        reasons=reasons,
    )
    _append_mismatch_reason(
        left_value=ocr_readiness_label,
        right_value=ocr_trial_profile_label,
        mismatch_reason="ocr_provider_label_mismatch_readiness_vs_trial_profile_details",
        reasons=reasons,
    )
    _append_mismatch_reason(
        left_value=vision_readiness_label,
        right_value=vision_trial_profile_label,
        mismatch_reason="vision_provider_label_mismatch_readiness_vs_trial_profile_details",
        reasons=reasons,
    )

    dataset_dir = _coerce_optional_string_with_reason(
        trial_profile_details.get("trial_calibration_dataset_dir"),
        invalid_type_reason="trial_profile_details_trial_calibration_dataset_dir_invalid_type",
        reasons=reasons,
    )
    artifacts_dir = _coerce_optional_string_with_reason(
        trial_profile_details.get("trial_calibration_artifacts_dir"),
        invalid_type_reason="trial_profile_details_trial_calibration_artifacts_dir_invalid_type",
        reasons=reasons,
    )
    if not _is_absolute_like(dataset_dir):
        reasons.append("calibration_dataset_dir_not_absolute")
    if not _is_absolute_like(artifacts_dir):
        reasons.append("calibration_artifacts_dir_not_absolute")
    for path_label, path_value in (
        ("calibration_dataset_dir", dataset_dir),
        ("calibration_artifacts_dir", artifacts_dir),
    ):
        lowered = path_value.lower()
        if "\\tmp\\" in lowered or "/tmp/" in lowered or "devdata" in lowered:
            reasons.append(f"{path_label}_not_private")

    raw_allowed_shops = _coerce_optional_string_with_reason(
        trial_profile_details.get("allowed_live_pilot_shop_ids"),
        invalid_type_reason="trial_profile_details_allowed_live_pilot_shop_ids_invalid_type",
        reasons=reasons,
    )
    allowed_shops = _normalize_shop_allowlist(raw_allowed_shops)
    if not allowed_shops:
        reasons.append("allowed_live_pilot_shop_ids_missing")
    elif shop_id not in allowed_shops:
        reasons.append("shop_not_allowed")

    selected_artifact_path = (artifact_path or "").strip() or approved_calibration_report_path
    if not selected_artifact_path:
        reasons.append("artifact_path_missing")
    else:
        artifact_file = Path(selected_artifact_path).resolve()
        if not artifact_file.exists():
            reasons.append("artifact_file_missing")
        else:
            if artifacts_dir:
                artifacts_dir_path = Path(artifacts_dir).resolve()
                if not _is_path_within_directory(target_path=artifact_file, parent_dir=artifacts_dir_path):
                    reasons.append("artifact_path_outside_artifacts_dir")

            try:
                raw_payload = json.loads(artifact_file.read_text(encoding="utf-8"))
            except OSError:
                reasons.append("artifact_file_unreadable")
                raw_payload = None
            except json.JSONDecodeError:
                reasons.append("artifact_json_invalid")
                raw_payload = None

            if raw_payload is None:
                artifact_payload = None
            elif not isinstance(raw_payload, dict):
                reasons.append("artifact_payload_not_object")
                artifact_payload = None
            else:
                artifact_payload = raw_payload

            if artifact_payload is None:
                return LivePilotPreflightSummary(
                    overall_status=DEGRADED_STATUS,
                    runtime_mode=runtime_mode,
                    trial_provider_profile=trial_provider_profile,
                    cutover_mode=cutover_mode,
                    approved_calibration_artifact_id=approved_calibration_artifact_id,
                    reasons=reasons,
                )

            artifact_id = _coerce_optional_string_with_reason(
                artifact_payload.get("artifact_id"),
                invalid_type_reason="artifact_id_invalid_type",
                reasons=reasons,
            )
            artifact_profile = _coerce_optional_string_with_reason(
                artifact_payload.get("trial_provider_profile"),
                invalid_type_reason="artifact_profile_invalid_type",
                reasons=reasons,
            )
            if not isinstance(artifact_payload.get("recommended_shop_rules"), dict):
                reasons.append("artifact_recommended_shop_rules_invalid")
            if not artifact_id:
                reasons.append("artifact_id_missing")
            if not artifact_profile:
                reasons.append("artifact_profile_missing")

            _append_mismatch_reason(
                left_value=artifact_profile,
                right_value=trial_provider_profile,
                mismatch_reason="artifact_profile_mismatch",
                reasons=reasons,
            )
            _append_mismatch_reason(
                left_value=artifact_profile,
                right_value=trial_profile_details_profile,
                mismatch_reason="artifact_profile_mismatch_trial_profile_details",
                reasons=reasons,
            )
            _append_mismatch_reason(
                left_value=artifact_profile,
                right_value=pilot_control_trial_provider_profile,
                mismatch_reason="artifact_profile_mismatch_pilot_control",
                reasons=reasons,
            )
            if artifact_id and approved_calibration_artifact_id and artifact_id != approved_calibration_artifact_id:
                reasons.append("artifact_id_mismatch")

    return LivePilotPreflightSummary(
        overall_status=READY_STATUS if not reasons else DEGRADED_STATUS,
        runtime_mode=runtime_mode,
        trial_provider_profile=trial_provider_profile,
        cutover_mode=cutover_mode,
        approved_calibration_artifact_id=approved_calibration_artifact_id,
        reasons=reasons,
    )
