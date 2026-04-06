from app.contracts.system import ReadinessCheckData, SystemReadinessData
from app.core.config import Settings
from app.runtime.guardrails import provider_trial_violation
from app.services.asr_gateway import SUPPORTED_REAL_PROVIDER_NAMES as SUPPORTED_ASR_PROVIDER_NAMES
from app.services.ocr_gateway import SUPPORTED_REAL_PROVIDER_NAMES as SUPPORTED_OCR_PROVIDER_NAMES
from app.services.vision_gateway import SUPPORTED_REAL_PROVIDER_NAMES as SUPPORTED_VISION_PROVIDER_NAMES

READY_STATUS = "ready"
DEGRADED_STATUS = "degraded"
LOCAL_DEMO_RUNTIME_MODE = "local-demo"
MOCK_MODE = "mock"
UNSET_MODE = "unset"
SUPPORTED_OBJECT_STORAGE_PROVIDER_NAMES = {"s3-compatible"}


def _normalize_runtime_mode(mode: str) -> str:
    normalized_mode = mode.strip().lower()
    return normalized_mode or LOCAL_DEMO_RUNTIME_MODE


def _normalize_provider_mode(provider: str) -> str:
    normalized_provider = provider.strip().lower()
    return normalized_provider or UNSET_MODE


def _missing_required_fields(required_live_fields: dict[str, str]) -> list[str]:
    return [
        field_name
        for field_name, field_value in required_live_fields.items()
        if not field_value.strip()
    ]


def _build_dependency_check(
    *,
    check_name: str,
    mode: str,
    runtime_mode: str,
    supported_live_modes: set[str],
    required_live_fields: dict[str, str],
    details: dict[str, str],
    trial_violation_message: str | None = None,
) -> ReadinessCheckData:
    if mode == UNSET_MODE:
        status = READY_STATUS if runtime_mode == LOCAL_DEMO_RUNTIME_MODE else DEGRADED_STATUS
        message = (
            f"{check_name} is unset and acceptable for local demo runtime."
            if status == READY_STATUS
            else f"{check_name} is not configured for trial readiness."
        )
        return ReadinessCheckData(status=status, mode=mode, message=message, details=details)

    if mode == MOCK_MODE:
        status = READY_STATUS if runtime_mode == LOCAL_DEMO_RUNTIME_MODE else DEGRADED_STATUS
        message = (
            f"{check_name} is in mock mode and acceptable for local demo runtime."
            if status == READY_STATUS
            else f"{check_name} is using a mock provider and is not trial-ready."
        )
        return ReadinessCheckData(status=status, mode=mode, message=message, details=details)

    if mode not in supported_live_modes:
        return ReadinessCheckData(
            status=DEGRADED_STATUS,
            mode=mode,
            message=f"{check_name} provider '{mode}' is unsupported.",
            details={
                **details,
                "reason": "unsupported_provider",
                "supported_modes": ",".join(sorted(supported_live_modes)),
            },
        )

    missing_fields = _missing_required_fields(required_live_fields)
    if missing_fields:
        return ReadinessCheckData(
            status=DEGRADED_STATUS,
            mode=mode,
            message=f"{check_name} is missing required live provider configuration.",
            details={
                **details,
                "reason": "missing_config",
                "missing_fields": ",".join(missing_fields),
            },
        )

    if trial_violation_message is not None:
        return ReadinessCheckData(
            status=DEGRADED_STATUS,
            mode=mode,
            message=trial_violation_message,
            details={
                **details,
                "reason": "trial_guardrail",
            },
        )

    return ReadinessCheckData(
        status=READY_STATUS,
        mode=mode,
        message=f"{check_name} is configured with a live provider.",
        details=details,
    )


def build_system_readiness(settings: Settings) -> SystemReadinessData:
    runtime_mode = _normalize_runtime_mode(settings.app_runtime_mode)

    object_storage_mode = _normalize_provider_mode(settings.object_storage_provider)
    asr_mode = _normalize_provider_mode(settings.asr_provider)
    ocr_mode = _normalize_provider_mode(settings.ocr_provider)
    vision_mode = _normalize_provider_mode(settings.vision_provider)

    checks = {
        "object_storage": _build_dependency_check(
            check_name="object storage",
            mode=object_storage_mode,
            runtime_mode=runtime_mode,
            supported_live_modes=SUPPORTED_OBJECT_STORAGE_PROVIDER_NAMES,
            required_live_fields={
                "bucket": settings.object_storage_bucket or "",
                "region": settings.object_storage_region or "",
                "endpoint_url": settings.object_storage_endpoint_url or "",
                "access_key": settings.object_storage_access_key or "",
                "secret_key": settings.object_storage_secret_key or "",
            },
            details={
                "provider": object_storage_mode,
                "bucket": settings.object_storage_bucket or "",
                "region": settings.object_storage_region or "",
                "endpoint_url": settings.object_storage_endpoint_url or "",
                "access_key_configured": str(bool(settings.object_storage_access_key)).lower(),
                "secret_key_configured": str(bool(settings.object_storage_secret_key)).lower(),
            },
        ),
        "asr": _build_dependency_check(
            check_name="asr",
            mode=asr_mode,
            runtime_mode=runtime_mode,
            supported_live_modes=set(SUPPORTED_ASR_PROVIDER_NAMES),
            required_live_fields={
                "api_url": settings.asr_provider_api_url or "",
                "api_key": settings.asr_provider_api_key or "",
                "model": settings.asr_provider_model or "",
            },
            details={
                "provider": asr_mode,
                "allow_mock_fallback": str(settings.asr_allow_mock_fallback).lower(),
            },
            trial_violation_message=provider_trial_violation(
                settings=settings,
                provider_name=settings.asr_provider,
                allow_mock_fallback=settings.asr_allow_mock_fallback,
                capability_label="ASR",
            ),
        ),
        "ocr": _build_dependency_check(
            check_name="ocr",
            mode=ocr_mode,
            runtime_mode=runtime_mode,
            supported_live_modes=set(SUPPORTED_OCR_PROVIDER_NAMES),
            required_live_fields={
                "api_url": settings.ocr_provider_api_url or "",
                "api_key": settings.ocr_provider_api_key or "",
                "model": settings.ocr_provider_model or "",
            },
            details={
                "provider": ocr_mode,
                "allow_mock_fallback": str(settings.ocr_allow_mock_fallback).lower(),
            },
            trial_violation_message=provider_trial_violation(
                settings=settings,
                provider_name=settings.ocr_provider,
                allow_mock_fallback=settings.ocr_allow_mock_fallback,
                capability_label="OCR",
            ),
        ),
        "vision": _build_dependency_check(
            check_name="vision",
            mode=vision_mode,
            runtime_mode=runtime_mode,
            supported_live_modes=set(SUPPORTED_VISION_PROVIDER_NAMES),
            required_live_fields={
                "api_url": settings.vision_provider_api_url or "",
                "api_key": settings.vision_provider_api_key or "",
                "model": settings.vision_provider_model or "",
            },
            details={
                "provider": vision_mode,
                "allow_mock_fallback": str(settings.vision_allow_mock_fallback).lower(),
            },
            trial_violation_message=provider_trial_violation(
                settings=settings,
                provider_name=settings.vision_provider,
                allow_mock_fallback=settings.vision_allow_mock_fallback,
                capability_label="Vision",
            ),
        ),
    }

    overall_status = READY_STATUS
    if any(check.status == DEGRADED_STATUS for check in checks.values()):
        overall_status = DEGRADED_STATUS

    return SystemReadinessData(
        overall_status=overall_status,
        runtime_mode=runtime_mode,
        checks=checks,
    )
