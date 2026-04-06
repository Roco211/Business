from app.contracts.system import ReadinessCheckData, SystemReadinessData
from app.core.config import Settings

READY_STATUS = "ready"
DEGRADED_STATUS = "degraded"
LOCAL_DEMO_RUNTIME_MODE = "local-demo"
MOCK_MODE = "mock"
UNSET_MODE = "unset"


def _normalize_runtime_mode(mode: str) -> str:
    normalized_mode = mode.strip().lower()
    return normalized_mode or LOCAL_DEMO_RUNTIME_MODE


def _normalize_provider_mode(provider: str) -> str:
    normalized_provider = provider.strip().lower()
    return normalized_provider or UNSET_MODE


def _build_dependency_check(
    *,
    check_name: str,
    mode: str,
    runtime_mode: str,
    details: dict[str, str],
) -> ReadinessCheckData:
    if runtime_mode == LOCAL_DEMO_RUNTIME_MODE:
        if mode in {MOCK_MODE, UNSET_MODE}:
            return ReadinessCheckData(
                status=READY_STATUS,
                mode=mode,
                message=f"{check_name} is in {mode} mode and acceptable for local demo runtime.",
                details=details,
            )
        return ReadinessCheckData(
            status=READY_STATUS,
            mode=mode,
            message=f"{check_name} is configured with a live provider.",
            details=details,
        )

    if mode == UNSET_MODE:
        return ReadinessCheckData(
            status=DEGRADED_STATUS,
            mode=mode,
            message=f"{check_name} is not configured for trial readiness.",
            details=details,
        )
    if mode == MOCK_MODE:
        return ReadinessCheckData(
            status=DEGRADED_STATUS,
            mode=mode,
            message=f"{check_name} is using a mock provider and is not trial-ready.",
            details=details,
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
            details={
                "provider": object_storage_mode,
                "bucket": settings.object_storage_bucket or "",
                "region": settings.object_storage_region or "",
                "endpoint_url": settings.object_storage_endpoint_url or "",
            },
        ),
        "asr": _build_dependency_check(
            check_name="asr",
            mode=asr_mode,
            runtime_mode=runtime_mode,
            details={
                "provider": asr_mode,
                "allow_mock_fallback": str(settings.asr_allow_mock_fallback).lower(),
            },
        ),
        "ocr": _build_dependency_check(
            check_name="ocr",
            mode=ocr_mode,
            runtime_mode=runtime_mode,
            details={
                "provider": ocr_mode,
                "allow_mock_fallback": str(settings.ocr_allow_mock_fallback).lower(),
            },
        ),
        "vision": _build_dependency_check(
            check_name="vision",
            mode=vision_mode,
            runtime_mode=runtime_mode,
            details={
                "provider": vision_mode,
                "allow_mock_fallback": str(settings.vision_allow_mock_fallback).lower(),
            },
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
