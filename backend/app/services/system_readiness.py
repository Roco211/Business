from urllib.parse import urlsplit

from app.contracts.system import ReadinessCheckData, SystemReadinessData
from app.core.config import Settings
from app.runtime.guardrails import provider_trial_violation
from app.services.asr_gateway import SUPPORTED_REAL_PROVIDER_NAMES as SUPPORTED_ASR_PROVIDER_NAMES
from app.services.ocr_gateway import SUPPORTED_REAL_PROVIDER_NAMES as SUPPORTED_OCR_PROVIDER_NAMES
from app.services.vision_gateway import SUPPORTED_REAL_PROVIDER_NAMES as SUPPORTED_VISION_PROVIDER_NAMES

READY_STATUS = "ready"
DEGRADED_STATUS = "degraded"
LOCAL_DEMO_RUNTIME_MODE = "local-demo"
TRIAL_RUNTIME_MODE = "trial"
MOCK_MODE = "mock"
UNSET_MODE = "unset"
SUPPORTED_OBJECT_STORAGE_PROVIDER_NAMES = {"s3-compatible"}
SUPPORTED_PRODUCTION_DATABASE_DIALECTS = {"postgresql", "postgres"}


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




def _database_dialect(database_url: str) -> str:
    scheme = urlsplit(database_url).scheme.strip().lower()
    if not scheme:
        return UNSET_MODE
    return scheme.split("+")[0]


def _build_production_database_check(*, settings: Settings) -> ReadinessCheckData:
    app_env = settings.app_env.strip().lower()
    dialect = _database_dialect(settings.database_url)
    details = {
        "app_env": app_env or "development",
        "dialect": dialect,
        "database_url_configured": str(bool(settings.database_url.strip())).lower(),
        "requires_postgresql": str(app_env == "production").lower(),
    }
    if app_env != "production":
        return ReadinessCheckData(
            status=READY_STATUS,
            mode=dialect,
            message="Production database strictness is optional outside production APP_ENV.",
            details=details,
        )
    if dialect not in SUPPORTED_PRODUCTION_DATABASE_DIALECTS:
        return ReadinessCheckData(
            status=DEGRADED_STATUS,
            mode=dialect,
            message="Production APP_ENV requires PostgreSQL-compatible DATABASE_URL.",
            details={**details, "reason": "unsupported_production_database"},
        )
    return ReadinessCheckData(
        status=READY_STATUS,
        mode="postgresql",
        message="Production database configuration uses PostgreSQL-compatible dialect.",
        details=details,
    )


def _build_production_config_check(*, settings: Settings) -> ReadinessCheckData:
    app_env = settings.app_env.strip().lower()
    cors_origins = settings.cors_origins()
    reasons: list[str] = []
    if app_env == "production":
        if not cors_origins:
            reasons.append("missing_cors_origins")
        if any(origin == "*" for origin in cors_origins):
            reasons.append("wildcard_cors_origin")
        if not settings.security_headers_enabled:
            reasons.append("security_headers_disabled")
        if settings.rate_limit_per_minute <= 0:
            reasons.append("rate_limit_disabled")
    details = {
        "app_env": app_env or "development",
        "cors_origin_count": str(len(cors_origins)),
        "cors_wildcard_enabled": str(any(origin == "*" for origin in cors_origins)).lower(),
        "security_headers_enabled": str(settings.security_headers_enabled).lower(),
        "rate_limit_per_minute": str(settings.rate_limit_per_minute),
    }
    if reasons:
        return ReadinessCheckData(
            status=DEGRADED_STATUS,
            mode=app_env or "development",
            message="Production APP_ENV is missing one or more safety configuration requirements.",
            details={**details, "reason": ",".join(reasons)},
        )
    return ReadinessCheckData(
        status=READY_STATUS,
        mode=app_env or "development",
        message="Production safety configuration is ready." if app_env == "production" else "Production safety strictness is optional outside production APP_ENV.",
        details=details,
    )


def _build_trial_profile_check(*, settings: Settings, runtime_mode: str) -> ReadinessCheckData:
    trial_provider_profile = settings.trial_provider_profile.strip()
    asr_provider_label = settings.asr_provider_label.strip()
    ocr_provider_label = settings.ocr_provider_label.strip()
    vision_provider_label = settings.vision_provider_label.strip()
    trial_calibration_dataset_dir = settings.trial_calibration_dataset_dir.strip()
    trial_calibration_artifacts_dir = settings.trial_calibration_artifacts_dir.strip()
    allowed_live_pilot_shop_ids = settings.live_pilot_allowed_shop_ids()

    details = {
        "trial_provider_profile": trial_provider_profile,
        "asr_provider_label": asr_provider_label,
        "ocr_provider_label": ocr_provider_label,
        "vision_provider_label": vision_provider_label,
        "trial_calibration_dataset_dir": trial_calibration_dataset_dir,
        "trial_calibration_artifacts_dir": trial_calibration_artifacts_dir,
        "allowed_live_pilot_shop_ids": ",".join(allowed_live_pilot_shop_ids),
        "calibration_dataset_dir_configured": str(bool(trial_calibration_dataset_dir)).lower(),
        "calibration_artifacts_dir_configured": str(bool(trial_calibration_artifacts_dir)).lower(),
        "allowed_live_pilot_shops_configured": str(bool(allowed_live_pilot_shop_ids)).lower(),
        "missing_profile_metadata": "false",
    }

    if runtime_mode != TRIAL_RUNTIME_MODE:
        return ReadinessCheckData(
            status=READY_STATUS,
            mode=runtime_mode,
            message="Trial profile metadata is optional outside trial runtime mode.",
            details=details,
        )

    missing_fields = _missing_required_fields(
        {
            "trial_provider_profile": trial_provider_profile,
            "asr_provider_label": asr_provider_label,
            "ocr_provider_label": ocr_provider_label,
            "vision_provider_label": vision_provider_label,
            "trial_calibration_dataset_dir": trial_calibration_dataset_dir,
            "trial_calibration_artifacts_dir": trial_calibration_artifacts_dir,
            "allowed_live_pilot_shop_ids": ",".join(allowed_live_pilot_shop_ids),
        }
    )
    if missing_fields:
        return ReadinessCheckData(
            status=DEGRADED_STATUS,
            mode=runtime_mode,
            message="Trial profile metadata is missing required configuration.",
            details={
                **details,
                "reason": "missing_config",
                "missing_fields": ",".join(missing_fields),
                "missing_profile_metadata": "true",
            },
        )

    return ReadinessCheckData(
        status=READY_STATUS,
        mode=runtime_mode,
        message="Trial profile metadata is configured.",
        details=details,
    )


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
    trial_provider_profile = settings.trial_provider_profile.strip()

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
                "provider_label": settings.asr_provider_label.strip(),
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
                "provider_label": settings.ocr_provider_label.strip(),
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
                "provider_label": settings.vision_provider_label.strip(),
                "allow_mock_fallback": str(settings.vision_allow_mock_fallback).lower(),
            },
            trial_violation_message=provider_trial_violation(
                settings=settings,
                provider_name=settings.vision_provider,
                allow_mock_fallback=settings.vision_allow_mock_fallback,
                capability_label="Vision",
            ),
        ),
        "trial_profile": _build_trial_profile_check(settings=settings, runtime_mode=runtime_mode),
        "production_database": _build_production_database_check(settings=settings),
        "production_config": _build_production_config_check(settings=settings),
    }

    overall_status = READY_STATUS
    if any(check.status == DEGRADED_STATUS for check in checks.values()):
        overall_status = DEGRADED_STATUS

    return SystemReadinessData(
        overall_status=overall_status,
        runtime_mode=runtime_mode,
        trial_provider_profile=trial_provider_profile,
        checks=checks,
    )
