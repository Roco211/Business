import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy.orm import Session

from app.models import PilotControl

MODE_CLOSED = "closed"
MODE_SHADOW = "shadow"
MODE_OPEN = "open"
ALLOWED_CUTOVER_MODES = {MODE_CLOSED, MODE_SHADOW, MODE_OPEN}
ALLOWED_MODE_TRANSITIONS = {
    MODE_CLOSED: {MODE_SHADOW},
    MODE_SHADOW: {MODE_CLOSED, MODE_OPEN},
    MODE_OPEN: {MODE_CLOSED, MODE_SHADOW},
}
PREFLIGHT_READY_STATUS = "ready"


class PilotControlValidationError(ValueError):
    pass


class PilotControlTransitionError(ValueError):
    pass


@dataclass(frozen=True)
class PilotRuntimeControlState:
    cutover_mode: str
    trial_provider_profile: str
    approved_calibration_artifact_id: str | None
    approved_calibration_report_path: str | None
    last_preflight_status: str | None


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _normalize_mode(mode: str) -> str:
    normalized = mode.strip().lower()
    if normalized not in ALLOWED_CUTOVER_MODES:
        raise PilotControlValidationError("cutover_mode is invalid")
    return normalized


def _normalize_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def normalize_cutover_mode_or_closed(mode: str | None) -> str:
    normalized = (mode or "").strip().lower()
    if normalized not in ALLOWED_CUTOVER_MODES:
        return MODE_CLOSED
    return normalized


def _assert_valid_mode_transition(current_mode: str, next_mode: str) -> None:
    if next_mode == current_mode:
        return
    allowed_targets = ALLOWED_MODE_TRANSITIONS.get(current_mode, set())
    if next_mode not in allowed_targets:
        raise PilotControlTransitionError(
            f"cannot transition cutover_mode from '{current_mode}' to '{next_mode}'"
        )


def get_or_create_pilot_control(
    db_session: Session,
    *,
    shop_id: str,
    trial_provider_profile: str,
) -> tuple[PilotControl, bool]:
    normalized_profile = trial_provider_profile.strip()
    existing = db_session.get(PilotControl, shop_id)
    if existing is not None:
        return existing, False

    created = PilotControl(
        shop_id=shop_id,
        trial_provider_profile=normalized_profile,
        approved_calibration_artifact_id=None,
        approved_calibration_report_path=None,
        cutover_mode=MODE_CLOSED,
        opened_at=None,
        opened_by_actor_id=None,
        closed_at=None,
        closed_by_actor_id=None,
        last_preflight_at=None,
        last_preflight_status=None,
        notes=None,
    )
    db_session.add(created)
    return created, True


def resolve_pilot_runtime_control_state(
    db_session: Session,
    *,
    shop_id: str,
    trial_provider_profile: str,
) -> PilotRuntimeControlState:
    pilot_control = db_session.get(PilotControl, shop_id)
    if pilot_control is None:
        pilot_control, _ = get_or_create_pilot_control(
            db_session,
            shop_id=shop_id,
            trial_provider_profile=trial_provider_profile,
        )
    return PilotRuntimeControlState(
        cutover_mode=normalize_cutover_mode_or_closed(pilot_control.cutover_mode),
        trial_provider_profile=(pilot_control.trial_provider_profile or "").strip(),
        approved_calibration_artifact_id=_normalize_optional_text(
            pilot_control.approved_calibration_artifact_id
        ),
        approved_calibration_report_path=_normalize_optional_text(
            pilot_control.approved_calibration_report_path
        ),
        last_preflight_status=_normalize_optional_text(pilot_control.last_preflight_status),
    )


def _load_artifact_identity(*, report_path: str) -> tuple[str | None, str | None]:
    try:
        payload = json.loads(Path(report_path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None, None
    if not isinstance(payload, dict):
        return None, None
    artifact_id = _normalize_optional_text(
        payload.get("artifact_id") if isinstance(payload.get("artifact_id"), str) else None
    )
    artifact_profile = _normalize_optional_text(
        payload.get("trial_provider_profile")
        if isinstance(payload.get("trial_provider_profile"), str)
        else None
    )
    return artifact_id, artifact_profile


def pilot_alignment_mismatch_reasons(
    *,
    runtime_trial_provider_profile: str,
    control_state: PilotRuntimeControlState,
) -> tuple[str, ...]:
    reasons: list[str] = []
    runtime_profile = runtime_trial_provider_profile.strip()
    if not runtime_profile:
        reasons.append("trial_provider_profile_missing")
    elif control_state.trial_provider_profile != runtime_profile:
        reasons.append("trial_provider_profile_mismatch")

    if not control_state.approved_calibration_artifact_id:
        reasons.append("approved_calibration_artifact_missing")
    elif control_state.approved_calibration_report_path:
        artifact_id, artifact_profile = _load_artifact_identity(
            report_path=control_state.approved_calibration_report_path
        )
        if (
            artifact_profile is not None
            and runtime_profile
            and artifact_profile != runtime_profile
        ):
            reasons.append("artifact_profile_mismatch")
        if (
            artifact_id is not None
            and artifact_id != control_state.approved_calibration_artifact_id
        ):
            reasons.append("artifact_id_mismatch")

    normalized_preflight_status = (control_state.last_preflight_status or "").strip().lower()
    if normalized_preflight_status != PREFLIGHT_READY_STATUS:
        reasons.append("preflight_not_ready")

    return tuple(reasons)


def mutate_pilot_control(
    db_session: Session,
    *,
    shop_id: str,
    actor_id: str,
    trial_provider_profile: str,
    cutover_mode: str | None,
    approved_calibration_artifact_id: str | None,
    approved_calibration_report_path: str | None,
    notes: str | None,
) -> tuple[PilotControl, bool]:
    pilot_control, changed = get_or_create_pilot_control(
        db_session,
        shop_id=shop_id,
        trial_provider_profile=trial_provider_profile,
    )
    current_mode = _normalize_mode(pilot_control.cutover_mode)

    if cutover_mode is not None:
        next_mode = _normalize_mode(cutover_mode)
        _assert_valid_mode_transition(current_mode, next_mode)
        if next_mode != current_mode:
            changed_at = _now()
            pilot_control.cutover_mode = next_mode
            changed = True
            if next_mode == MODE_CLOSED:
                pilot_control.closed_at = changed_at
                pilot_control.closed_by_actor_id = actor_id
            else:
                pilot_control.opened_at = changed_at
                pilot_control.opened_by_actor_id = actor_id
                pilot_control.closed_at = None
                pilot_control.closed_by_actor_id = None

    if approved_calibration_artifact_id is not None:
        normalized_artifact_id = _normalize_optional_text(approved_calibration_artifact_id)
        if pilot_control.approved_calibration_artifact_id != normalized_artifact_id:
            pilot_control.approved_calibration_artifact_id = normalized_artifact_id
            changed = True
    if approved_calibration_report_path is not None:
        normalized_report_path = _normalize_optional_text(approved_calibration_report_path)
        if pilot_control.approved_calibration_report_path != normalized_report_path:
            pilot_control.approved_calibration_report_path = normalized_report_path
            changed = True
    if notes is not None:
        normalized_notes = _normalize_optional_text(notes)
        if pilot_control.notes != normalized_notes:
            pilot_control.notes = normalized_notes
            changed = True

    normalized_profile = trial_provider_profile.strip()
    if pilot_control.trial_provider_profile != normalized_profile:
        pilot_control.trial_provider_profile = normalized_profile
        changed = True

    if changed:
        db_session.flush()
    return pilot_control, changed
