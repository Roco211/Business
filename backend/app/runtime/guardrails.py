from dataclasses import dataclass

from app.core.config import Settings
from sqlalchemy.orm import Session

from app.services.pilot_control import (
    MODE_CLOSED,
    MODE_OPEN,
    MODE_SHADOW,
    pilot_alignment_mismatch_reasons,
    resolve_pilot_runtime_control_state,
)


TRIAL_RUNTIME_MODE = "trial"
LOCAL_DEMO_RUNTIME_MODE = "local-demo"
PILOT_CUTOVER_BLOCK_ERROR_CODE = "pilot_cutover_closed"
GUARDRAIL_STATUS_ALLOWED = "allowed"
GUARDRAIL_STATUS_BLOCKED = "blocked"
GUARDRAIL_STATUS_FORCED_CONFIRMATION = "forced-confirmation"
GUARDRAIL_STATUS_UNCLASSIFIED = "unclassified"
WRITE_INTENT_TASK_TYPES = {
    "voice-stock-in",
    "voice-stock-out",
    "photo-stock-in",
    "receipt-ocr",
}


@dataclass(frozen=True)
class PilotCutoverGuardrailDecision:
    cutover_mode: str
    guardrail_status: str
    guardrail_reason: str | None
    block_error_code: str | None
    shadow_forced_confirmation: bool
    guardrail_degraded: bool
    guardrail_degraded_reasons: tuple[str, ...]

    @property
    def should_block(self) -> bool:
        return self.guardrail_status == GUARDRAIL_STATUS_BLOCKED

    @property
    def should_force_confirmation(self) -> bool:
        return self.guardrail_status == GUARDRAIL_STATUS_FORCED_CONFIRMATION

    def telemetry_fields(self) -> dict[str, object]:
        return {
            "cutover_mode": self.cutover_mode,
            "guardrail_status": self.guardrail_status,
            "guardrail_reason": self.guardrail_reason,
            "shadow_forced_confirmation": self.shadow_forced_confirmation,
            "guardrail_degraded": self.guardrail_degraded,
            "guardrail_degraded_reasons": list(self.guardrail_degraded_reasons),
        }


def normalized_runtime_mode(value: str | None) -> str:
    normalized = (value or "").strip().lower()
    return normalized or LOCAL_DEMO_RUNTIME_MODE


def is_trial_mode(runtime_mode: str | None) -> bool:
    return normalized_runtime_mode(runtime_mode) == TRIAL_RUNTIME_MODE


def is_write_intent_task_type(task_type: str | None) -> bool:
    return (task_type or "").strip() in WRITE_INTENT_TASK_TYPES


def unclassified_route_failure_guardrail_telemetry(
    db_session: Session,
    *,
    settings: Settings,
    shop_id: str,
) -> dict[str, object]:
    if is_trial_mode(settings.normalized_runtime_mode()):
        control_state = resolve_pilot_runtime_control_state(
            db_session,
            shop_id=shop_id,
            trial_provider_profile=settings.trial_provider_profile.strip(),
        )
        cutover_mode = control_state.cutover_mode
    else:
        cutover_mode = LOCAL_DEMO_RUNTIME_MODE
    return {
        "cutover_mode": cutover_mode,
        "guardrail_status": GUARDRAIL_STATUS_UNCLASSIFIED,
        "guardrail_reason": "route_task_type_unclassified",
        "shadow_forced_confirmation": False,
        "guardrail_degraded": False,
        "guardrail_degraded_reasons": [],
    }


def evaluate_pilot_cutover_guardrail(
    db_session: Session,
    *,
    settings: Settings,
    shop_id: str,
    task_type: str,
) -> PilotCutoverGuardrailDecision:
    if not is_trial_mode(settings.normalized_runtime_mode()):
        return PilotCutoverGuardrailDecision(
            cutover_mode=LOCAL_DEMO_RUNTIME_MODE,
            guardrail_status=GUARDRAIL_STATUS_ALLOWED,
            guardrail_reason=None,
            block_error_code=None,
            shadow_forced_confirmation=False,
            guardrail_degraded=False,
            guardrail_degraded_reasons=(),
        )

    control_state = resolve_pilot_runtime_control_state(
        db_session,
        shop_id=shop_id,
        trial_provider_profile=settings.trial_provider_profile.strip(),
    )
    cutover_mode = control_state.cutover_mode
    if not is_write_intent_task_type(task_type):
        return PilotCutoverGuardrailDecision(
            cutover_mode=cutover_mode,
            guardrail_status=GUARDRAIL_STATUS_ALLOWED,
            guardrail_reason=None,
            block_error_code=None,
            shadow_forced_confirmation=False,
            guardrail_degraded=False,
            guardrail_degraded_reasons=(),
        )

    alignment_reasons = pilot_alignment_mismatch_reasons(
        runtime_trial_provider_profile=settings.trial_provider_profile.strip(),
        control_state=control_state,
    )
    if cutover_mode == MODE_CLOSED:
        return PilotCutoverGuardrailDecision(
            cutover_mode=cutover_mode,
            guardrail_status=GUARDRAIL_STATUS_BLOCKED,
            guardrail_reason="cutover_mode_closed",
            block_error_code=PILOT_CUTOVER_BLOCK_ERROR_CODE,
            shadow_forced_confirmation=False,
            guardrail_degraded=False,
            guardrail_degraded_reasons=(),
        )
    if cutover_mode == MODE_SHADOW:
        return PilotCutoverGuardrailDecision(
            cutover_mode=cutover_mode,
            guardrail_status=GUARDRAIL_STATUS_FORCED_CONFIRMATION,
            guardrail_reason="cutover_mode_shadow",
            block_error_code=None,
            shadow_forced_confirmation=True,
            guardrail_degraded=bool(alignment_reasons),
            guardrail_degraded_reasons=alignment_reasons,
        )
    if cutover_mode == MODE_OPEN and alignment_reasons:
        return PilotCutoverGuardrailDecision(
            cutover_mode=cutover_mode,
            guardrail_status=GUARDRAIL_STATUS_FORCED_CONFIRMATION,
            guardrail_reason="cutover_alignment_invalid",
            block_error_code=None,
            shadow_forced_confirmation=False,
            guardrail_degraded=True,
            guardrail_degraded_reasons=alignment_reasons,
        )
    return PilotCutoverGuardrailDecision(
        cutover_mode=cutover_mode,
        guardrail_status=GUARDRAIL_STATUS_ALLOWED,
        guardrail_reason=None,
        block_error_code=None,
        shadow_forced_confirmation=False,
        guardrail_degraded=False,
        guardrail_degraded_reasons=(),
    )


def provider_trial_violation(
    *,
    settings: Settings,
    provider_name: str | None,
    allow_mock_fallback: bool,
    capability_label: str,
) -> str | None:
    if not is_trial_mode(settings.normalized_runtime_mode()):
        return None

    normalized_provider = (provider_name or "").strip().lower()
    if not normalized_provider or normalized_provider == "mock":
        return f"trial mode requires {capability_label} to use a configured real provider"

    if allow_mock_fallback:
        return f"trial mode does not allow {capability_label} mock fallback"

    return None


def image_route_trial_violation(
    *,
    settings: Settings,
    used_fallback: bool,
    confidence: float | None,
    low_confidence_threshold: object,
) -> str | None:
    if not is_trial_mode(settings.normalized_runtime_mode()):
        return None

    if used_fallback:
        return "trial mode blocks image recognition results that used provider fallback"

    if (
        confidence is not None
        and isinstance(low_confidence_threshold, (int, float))
        and confidence < float(low_confidence_threshold)
    ):
        return (
            "trial mode requires manual review when image confidence "
            f"{confidence:.2f} is below threshold {float(low_confidence_threshold):.2f}"
        )

    return None
