from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
UTC = timezone.utc
import json
from pathlib import Path
from typing import Any, Callable, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from app.core.config import get_settings
from app.devtools.asr_provider_eval import evaluate_asr_file
from app.devtools.ocr_provider_eval import evaluate_ocr_path
from app.devtools.vision_provider_eval import evaluate_vision_path
from app.services.asr_types import AsrProviderError
from app.services.ocr_types import OcrProviderError
from app.services.vision_types import VisionProviderError

Capability = Literal["asr", "ocr", "vision"]
BACKEND_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ARTIFACTS_DIR = BACKEND_ROOT / "devdata" / "trial_calibration_artifacts"
EVALUATION_EXCEPTIONS = (
    AsrProviderError,
    OcrProviderError,
    VisionProviderError,
    FileNotFoundError,
    OSError,
    RuntimeError,
    NotImplementedError,
)


class ManifestValidationError(ValueError):
    """Raised when the calibration manifest does not meet the required schema."""


class _ManifestCaseModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str = Field(min_length=1)
    capability: Capability
    media_path: str = Field(min_length=1)
    media_id: str | None = None
    text_hint: str | None = None
    expected: dict[str, Any]


class _ManifestModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    trial_id: str = Field(min_length=1)
    cases: list[_ManifestCaseModel] = Field(min_length=1)


@dataclass(frozen=True)
class PilotCalibrationCase:
    case_id: str
    capability: Capability
    media_path: Path
    media_id: str | None
    text_hint: str | None
    expected: dict[str, Any]


@dataclass(frozen=True)
class PilotCalibrationManifest:
    trial_id: str
    cases: list[PilotCalibrationCase]
    manifest_path: Path


class _AsrExpectedModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    transcript_contains: list[str] = Field(default_factory=list)
    min_confidence: float | None = Field(default=None, ge=0.0, le=1.0)

    @field_validator("transcript_contains", mode="before")
    @classmethod
    def _validate_transcript_contains(cls, value: Any) -> Any:
        if value is None:
            return []
        if not isinstance(value, list):
            raise TypeError("transcript_contains must be an array of strings")
        return value


class _OcrExpectedModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_amount: float | None = None
    amount_tolerance: float = Field(default=0.0, ge=0.0)


class _VisionExpectedModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    top_candidate_in: list[str] = Field(default_factory=list)
    min_confidence: float | None = Field(default=None, ge=0.0, le=1.0)

    @field_validator("top_candidate_in", mode="before")
    @classmethod
    def _validate_top_candidate_in(cls, value: Any) -> Any:
        if value is None:
            return []
        if not isinstance(value, list):
            raise TypeError("top_candidate_in must be an array of strings")
        return value


def _normalize_expected(*, capability: Capability, payload: dict[str, Any]) -> dict[str, Any]:
    if capability == "asr":
        return _AsrExpectedModel.model_validate(payload).model_dump(exclude_none=True)

    if capability == "ocr":
        return _OcrExpectedModel.model_validate(payload).model_dump(exclude_none=True)
    return _VisionExpectedModel.model_validate(payload).model_dump(exclude_none=True)


def load_manifest(manifest_path: str | Path) -> PilotCalibrationManifest:
    resolved_manifest_path = Path(manifest_path).resolve()
    try:
        raw_payload = json.loads(resolved_manifest_path.read_text(encoding="utf-8"))
        parsed = _ManifestModel.model_validate(raw_payload)
        cases: list[PilotCalibrationCase] = []
        for case in parsed.cases:
            resolved_media_path = (
                (resolved_manifest_path.parent / case.media_path).resolve()
                if not Path(case.media_path).is_absolute()
                else Path(case.media_path)
            )
            cases.append(
                PilotCalibrationCase(
                    case_id=case.case_id,
                    capability=case.capability,
                    media_path=resolved_media_path,
                    media_id=case.media_id,
                    text_hint=case.text_hint,
                    expected=_normalize_expected(capability=case.capability, payload=case.expected),
                )
            )
    except (ValidationError, json.JSONDecodeError, OSError, TypeError, ValueError) as exc:
        raise ManifestValidationError(f"Invalid manifest: {exc}") from exc

    return PilotCalibrationManifest(
        trial_id=parsed.trial_id,
        cases=cases,
        manifest_path=resolved_manifest_path,
    )


def _resolve_default_artifact_dir() -> Path:
    configured_path = get_settings().trial_calibration_artifacts_dir.strip()
    if configured_path:
        return Path(configured_path).resolve()
    return DEFAULT_ARTIFACTS_DIR


def _failed_case_from_exception(*, case: PilotCalibrationCase, error: Exception) -> dict[str, Any]:
    return {
        "case_id": case.case_id,
        "capability": case.capability,
        "provider_name": None,
        "used_fallback": False,
        "low_confidence_signal": False,
        "outcome": "fail",
        "reasons": ["evaluation_error"],
        "latency_ms": 0,
        "error": str(error),
    }


def _evaluate_case(
    *,
    case: PilotCalibrationCase,
    evaluate_asr: Callable[..., dict[str, Any]],
    evaluate_ocr: Callable[..., dict[str, Any]],
    evaluate_vision: Callable[..., dict[str, Any]],
) -> dict[str, Any]:
    if case.capability == "asr":
        return evaluate_asr(
            audio_path=case.media_path,
            media_id=case.media_id,
            text_hint=case.text_hint,
        )
    if case.capability == "ocr":
        return evaluate_ocr(file_path=case.media_path)
    return evaluate_vision(file_path=case.media_path)


def _score_case(*, capability: Capability, actual: dict[str, Any], expected: dict[str, Any]) -> tuple[str, list[str], bool]:
    used_fallback = bool(actual.get("used_fallback", False))
    low_confidence_signal = False
    fail_reasons: list[str] = []
    warn_reasons: list[str] = []

    if capability == "asr":
        transcript = str(actual.get("transcript", "")).lower()
        expected_fragments = [fragment.lower() for fragment in expected.get("transcript_contains", [])]
        if expected_fragments and any(fragment not in transcript for fragment in expected_fragments):
            fail_reasons.append("transcript_mismatch")
        min_confidence = expected.get("min_confidence")
        confidence = actual.get("confidence")
        if min_confidence is not None and (confidence is None or float(confidence) < float(min_confidence)):
            low_confidence_signal = True
    elif capability == "ocr":
        expected_amount = expected.get("total_amount")
        actual_amount = actual.get("total_amount")
        tolerance = float(expected.get("amount_tolerance", 0.0))
        if expected_amount is not None:
            if actual_amount is None or abs(float(actual_amount) - float(expected_amount)) > tolerance:
                fail_reasons.append("total_amount_mismatch")
        low_confidence_signal = bool(actual.get("low_confidence_fields"))
    else:
        candidates = list(actual.get("candidates") or [])
        if not candidates:
            fail_reasons.append("no_candidates")
        else:
            top_candidate = candidates[0]
            allowed_candidates = expected.get("top_candidate_in", [])
            if allowed_candidates and top_candidate.get("item_name") not in allowed_candidates:
                fail_reasons.append("top_candidate_mismatch")
            min_confidence = expected.get("min_confidence")
            top_confidence = top_candidate.get("confidence")
            if (
                min_confidence is not None
                and top_confidence is not None
                and float(top_confidence) < float(min_confidence)
            ):
                low_confidence_signal = True

    if fail_reasons:
        return "fail", fail_reasons, low_confidence_signal
    if used_fallback:
        warn_reasons.append("used_fallback")
    if low_confidence_signal:
        warn_reasons.append("low_confidence_signal")
    if warn_reasons:
        return "warn", warn_reasons, low_confidence_signal
    return "pass", [], low_confidence_signal


def _calculate_latency_stats(latencies_ms: list[int]) -> dict[str, int]:
    if not latencies_ms:
        return {"min": 0, "max": 0, "avg": 0, "p95": 0}
    sorted_latencies = sorted(latencies_ms)
    p95_index = max(0, ((len(sorted_latencies) * 95 + 99) // 100) - 1)
    return {
        "min": sorted_latencies[0],
        "max": sorted_latencies[-1],
        "avg": round(sum(sorted_latencies) / len(sorted_latencies)),
        "p95": sorted_latencies[p95_index],
    }


def _resolve_trial_provider_profile(*, trial_id: str) -> str:
    configured_profile = get_settings().trial_provider_profile.strip()
    return configured_profile or trial_id


def _build_recommended_shop_rules() -> dict[str, Any]:
    return {
        "low_confidence_threshold": 0.9,
        "require_price_confirmation": True,
        "require_new_item_confirmation": True,
    }


def _build_artifact_identity(*, trial_id: str, generated_at: datetime) -> tuple[str, str]:
    run_token = generated_at.strftime("%Y%m%dT%H%M%S%fZ")
    artifact_id = f"{trial_id}-report-{run_token}"
    return artifact_id, run_token


def _render_markdown_report(*, report: dict[str, Any]) -> str:
    summary = report["summary"]
    latency = report["latency_ms"]
    lines = [
        "# Pilot Calibration Report",
        "",
        f"- Trial ID: `{report['trial_id']}`",
        f"- Generated At: `{report['generated_at']}`",
        "",
        "| pass | warn | fail |",
        "| --- | --- | --- |",
        f"| {summary['pass']} | {summary['warn']} | {summary['fail']} |",
        "",
        f"- Total Cases: {summary['total_cases']}",
        f"- Fallback Count: {summary['fallback_count']}",
        f"- Low Confidence Count: {summary['low_confidence_count']}",
        "",
        "| latency_min_ms | latency_avg_ms | latency_p95_ms | latency_max_ms |",
        "| --- | --- | --- | --- |",
        f"| {latency['min']} | {latency['avg']} | {latency['p95']} | {latency['max']} |",
        "",
        "## Case Outcomes",
        "",
        "| case_id | capability | provider | outcome | reasons |",
        "| --- | --- | --- | --- | --- |",
    ]

    for case in report["cases"]:
        reasons = ", ".join(case["reasons"]) if case["reasons"] else "-"
        lines.append(
            f"| {case['case_id']} | {case['capability']} | {case['provider_name']} | {case['outcome']} | {reasons} |"
        )
    return "\n".join(lines) + "\n"


def run_pilot_calibration(
    *,
    manifest_path: str | Path,
    output_dir: str | Path | None = None,
    evaluate_asr: Callable[..., dict[str, Any]] = evaluate_asr_file,
    evaluate_ocr: Callable[..., dict[str, Any]] = evaluate_ocr_path,
    evaluate_vision: Callable[..., dict[str, Any]] = evaluate_vision_path,
) -> dict[str, Any]:
    manifest = load_manifest(manifest_path)
    artifact_dir = Path(output_dir) if output_dir is not None else _resolve_default_artifact_dir()
    artifact_dir.mkdir(parents=True, exist_ok=True)

    case_outcomes: list[dict[str, Any]] = []
    failure_buckets: Counter[str] = Counter()
    latencies_ms: list[int] = []
    fallback_count = 0
    low_confidence_count = 0
    pass_count = 0
    warn_count = 0
    fail_count = 0

    for case in manifest.cases:
        try:
            actual = _evaluate_case(
                case=case,
                evaluate_asr=evaluate_asr,
                evaluate_ocr=evaluate_ocr,
                evaluate_vision=evaluate_vision,
            )
        except EVALUATION_EXCEPTIONS as exc:
            fail_count += 1
            failure_buckets.update(["evaluation_error"])
            latencies_ms.append(0)
            case_outcomes.append(_failed_case_from_exception(case=case, error=exc))
            continue

        latency_ms = max(0, int(actual.get("latency_ms", 0)))
        latencies_ms.append(latency_ms)
        used_fallback = bool(actual.get("used_fallback", False))
        if used_fallback:
            fallback_count += 1

        outcome, reasons, low_confidence_signal = _score_case(
            capability=case.capability,
            actual=actual,
            expected=case.expected,
        )
        if low_confidence_signal:
            low_confidence_count += 1

        if outcome == "pass":
            pass_count += 1
        elif outcome == "warn":
            warn_count += 1
            failure_buckets.update(reasons)
        else:
            fail_count += 1
            failure_buckets.update(reasons)

        case_outcomes.append(
            {
                "case_id": case.case_id,
                "capability": case.capability,
                "provider_name": actual.get("provider_name"),
                "used_fallback": used_fallback,
                "low_confidence_signal": low_confidence_signal,
                "outcome": outcome,
                "reasons": reasons,
                "latency_ms": latency_ms,
            }
        )

    generated_at = datetime.now(tz=UTC)
    generated_at_iso = generated_at.isoformat()
    artifact_id, run_token = _build_artifact_identity(
        trial_id=manifest.trial_id,
        generated_at=generated_at,
    )

    report = {
        "artifact_id": artifact_id,
        "trial_id": manifest.trial_id,
        "trial_provider_profile": _resolve_trial_provider_profile(trial_id=manifest.trial_id),
        "manifest_path": str(manifest.manifest_path),
        "generated_at": generated_at_iso,
        "recommended_shop_rules": _build_recommended_shop_rules(),
        "summary": {
            "total_cases": len(manifest.cases),
            "pass": pass_count,
            "warn": warn_count,
            "fail": fail_count,
            "fallback_count": fallback_count,
            "low_confidence_count": low_confidence_count,
        },
        "latency_ms": _calculate_latency_stats(latencies_ms),
        "failure_buckets": dict(failure_buckets),
        "cases": case_outcomes,
    }

    json_report_path = artifact_dir / f"{manifest.trial_id}_report_{run_token}.json"
    markdown_report_path = artifact_dir / f"{manifest.trial_id}_report_{run_token}.md"
    json_report_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    markdown_report_path.write_text(_render_markdown_report(report=report), encoding="utf-8")

    return {
        "artifact_id": report["artifact_id"],
        "trial_id": manifest.trial_id,
        "trial_provider_profile": report["trial_provider_profile"],
        "recommended_shop_rules": report["recommended_shop_rules"],
        "summary": report["summary"],
        "latency_ms": report["latency_ms"],
        "failure_buckets": report["failure_buckets"],
        "cases": report["cases"],
        "json_report_path": str(json_report_path),
        "markdown_report_path": str(markdown_report_path),
    }
