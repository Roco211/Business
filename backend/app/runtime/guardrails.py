from app.core.config import Settings


TRIAL_RUNTIME_MODE = "trial"
LOCAL_DEMO_RUNTIME_MODE = "local-demo"


def normalized_runtime_mode(value: str | None) -> str:
    normalized = (value or "").strip().lower()
    return normalized or LOCAL_DEMO_RUNTIME_MODE


def is_trial_mode(runtime_mode: str | None) -> bool:
    return normalized_runtime_mode(runtime_mode) == TRIAL_RUNTIME_MODE


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
