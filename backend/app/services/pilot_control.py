from datetime import UTC, datetime

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


class PilotControlValidationError(ValueError):
    pass


class PilotControlTransitionError(ValueError):
    pass


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
        changed = False
        if existing.trial_provider_profile != normalized_profile:
            existing.trial_provider_profile = normalized_profile
            changed = True
        return existing, changed

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
