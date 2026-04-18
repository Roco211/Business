from dataclasses import dataclass
import os


@dataclass(frozen=True)
class Settings:
    app_env: str
    app_host: str
    app_port: int
    redis_url: str
    database_url: str
    session_stream_keepalive_seconds: float
    session_stream_pending_poll_seconds: float = float(os.getenv("SESSION_STREAM_PENDING_POLL_SECONDS", "1"))
    v2_outbox_due_sweep_interval_seconds: int = int(os.getenv("V2_OUTBOX_DUE_SWEEP_INTERVAL_SECONDS", "30"))
    v2_outbox_due_sweep_scope_limit: int = int(os.getenv("V2_OUTBOX_DUE_SWEEP_SCOPE_LIMIT", "20"))
    v2_outbox_due_sweep_batch_limit_per_scope: int = int(
        os.getenv("V2_OUTBOX_DUE_SWEEP_BATCH_LIMIT_PER_SCOPE", "50")
    )
    v2_outbox_due_sweep_max_batches_per_scope: int = int(
        os.getenv("V2_OUTBOX_DUE_SWEEP_MAX_BATCHES_PER_SCOPE", "10")
    )
    v2_outbox_due_sweep_retry_after_seconds: int = int(
        os.getenv("V2_OUTBOX_DUE_SWEEP_RETRY_AFTER_SECONDS", "60")
    )
    app_runtime_mode: str = os.getenv("APP_RUNTIME_MODE", "local-demo")
    object_storage_provider: str = os.getenv("OBJECT_STORAGE_PROVIDER", "mock")
    object_storage_bucket: str | None = os.getenv("OBJECT_STORAGE_BUCKET")
    object_storage_region: str | None = os.getenv("OBJECT_STORAGE_REGION")
    object_storage_endpoint_url: str | None = os.getenv("OBJECT_STORAGE_ENDPOINT_URL")
    object_storage_access_key: str | None = os.getenv("OBJECT_STORAGE_ACCESS_KEY")
    object_storage_secret_key: str | None = os.getenv("OBJECT_STORAGE_SECRET_KEY")
    object_storage_public_base_url: str | None = os.getenv("OBJECT_STORAGE_PUBLIC_BASE_URL")
    object_storage_presign_ttl_seconds: int = int(os.getenv("OBJECT_STORAGE_PRESIGN_TTL_SECONDS", "900"))
    default_shop_id: str = os.getenv("DEFAULT_SHOP_ID", "shop_default")
    default_owner_actor_id: str = os.getenv("DEFAULT_OWNER_ACTOR_ID", "owner_default")
    default_session_id: str = os.getenv("DEFAULT_SESSION_ID", "sess_default")
    seed_owner_email: str | None = os.getenv("SEED_OWNER_EMAIL")
    seed_owner_password: str | None = os.getenv("SEED_OWNER_PASSWORD")
    seed_owner_display_name: str = os.getenv("SEED_OWNER_DISPLAY_NAME", "Default Owner")
    auth_session_ttl_minutes: int = int(os.getenv("AUTH_SESSION_TTL_MINUTES", "120"))
    asr_provider: str = os.getenv("ASR_PROVIDER", "mock")
    asr_provider_api_url: str | None = os.getenv("ASR_PROVIDER_API_URL")
    asr_provider_api_key: str | None = os.getenv("ASR_PROVIDER_API_KEY")
    asr_provider_model: str | None = os.getenv("ASR_PROVIDER_MODEL")
    asr_timeout_seconds: float = float(os.getenv("ASR_TIMEOUT_SECONDS", "15"))
    asr_allow_mock_fallback: bool = os.getenv("ASR_ALLOW_MOCK_FALLBACK", "1") not in ("0", "false", "False")
    ocr_provider: str = os.getenv("OCR_PROVIDER", "")
    ocr_provider_api_url: str | None = os.getenv("OCR_PROVIDER_API_URL")
    ocr_provider_api_key: str | None = os.getenv("OCR_PROVIDER_API_KEY")
    ocr_provider_model: str | None = os.getenv("OCR_PROVIDER_MODEL")
    ocr_timeout_seconds: float = float(os.getenv("OCR_TIMEOUT_SECONDS", "15"))
    ocr_allow_mock_fallback: bool = True
    vision_provider: str = os.getenv("VISION_PROVIDER", "")
    vision_provider_api_url: str | None = os.getenv("VISION_PROVIDER_API_URL")
    vision_provider_api_key: str | None = os.getenv("VISION_PROVIDER_API_KEY")
    vision_provider_model: str | None = os.getenv("VISION_PROVIDER_MODEL")
    vision_timeout_seconds: float = float(os.getenv("VISION_TIMEOUT_SECONDS", "15"))
    vision_allow_mock_fallback: bool = True
    trial_provider_profile: str = os.getenv("TRIAL_PROVIDER_PROFILE", "")
    asr_provider_label: str = os.getenv("ASR_PROVIDER_LABEL", "")
    ocr_provider_label: str = os.getenv("OCR_PROVIDER_LABEL", "")
    vision_provider_label: str = os.getenv("VISION_PROVIDER_LABEL", "")
    trial_calibration_dataset_dir: str = os.getenv("TRIAL_CALIBRATION_DATASET_DIR", "")
    trial_calibration_artifacts_dir: str = os.getenv("TRIAL_CALIBRATION_ARTIFACTS_DIR", "")
    live_pilot_allowed_shop_ids_raw: str = os.getenv("LIVE_PILOT_ALLOWED_SHOP_IDS", "")

    def normalized_runtime_mode(self) -> str:
        normalized = self.app_runtime_mode.strip().lower()
        return normalized or "local-demo"

    def normalized_object_storage_provider(self) -> str:
        normalized = self.object_storage_provider.strip().lower()
        return normalized or "mock"

    def object_storage_live_required_config(self) -> dict[str, str]:
        return {
            "bucket": self.object_storage_bucket or "",
            "region": self.object_storage_region or "",
            "endpoint_url": self.object_storage_endpoint_url or "",
            "access_key": self.object_storage_access_key or "",
            "secret_key": self.object_storage_secret_key or "",
        }

    def live_pilot_allowed_shop_ids(self) -> list[str]:
        raw = self.live_pilot_allowed_shop_ids_raw.strip()
        return [shop_id.strip() for shop_id in raw.split(",") if shop_id.strip()]


def _build_default_database_url() -> str:
    mysql_user = os.getenv("MYSQL_USER", "aism")
    mysql_password = os.getenv("MYSQL_PASSWORD", "aism_password")
    mysql_host = os.getenv("MYSQL_HOST", "mysql")
    mysql_port = os.getenv("MYSQL_PORT", "3306")
    mysql_database = os.getenv("MYSQL_DATABASE", "ai_store_manager")
    return (
        f"mysql+pymysql://{mysql_user}:{mysql_password}"
        f"@{mysql_host}:{mysql_port}/{mysql_database}?charset=utf8mb4"
    )


def _parse_bool_env(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value not in ("0", "false", "False")


def get_settings() -> Settings:
    app_env = os.getenv("APP_ENV", "development")
    ocr_provider = os.getenv("OCR_PROVIDER", "")
    ocr_allow_env = os.getenv("OCR_ALLOW_MOCK_FALLBACK")
    vision_allow_env = os.getenv("VISION_ALLOW_MOCK_FALLBACK")
    return Settings(
        app_env=app_env,
        app_runtime_mode=os.getenv("APP_RUNTIME_MODE", "local-demo"),
        app_host=os.getenv("APP_HOST", "0.0.0.0"),
        app_port=int(os.getenv("APP_PORT", "8001")),
        redis_url=os.getenv("REDIS_URL", "redis://redis:6379/0"),
        database_url=os.getenv("DATABASE_URL", _build_default_database_url()),
        session_stream_keepalive_seconds=float(os.getenv("SESSION_STREAM_KEEPALIVE_SECONDS", "20")),
        session_stream_pending_poll_seconds=float(os.getenv("SESSION_STREAM_PENDING_POLL_SECONDS", "1")),
        v2_outbox_due_sweep_interval_seconds=int(os.getenv("V2_OUTBOX_DUE_SWEEP_INTERVAL_SECONDS", "30")),
        v2_outbox_due_sweep_scope_limit=int(os.getenv("V2_OUTBOX_DUE_SWEEP_SCOPE_LIMIT", "20")),
        v2_outbox_due_sweep_batch_limit_per_scope=int(
            os.getenv("V2_OUTBOX_DUE_SWEEP_BATCH_LIMIT_PER_SCOPE", "50")
        ),
        v2_outbox_due_sweep_max_batches_per_scope=int(
            os.getenv("V2_OUTBOX_DUE_SWEEP_MAX_BATCHES_PER_SCOPE", "10")
        ),
        v2_outbox_due_sweep_retry_after_seconds=int(
            os.getenv("V2_OUTBOX_DUE_SWEEP_RETRY_AFTER_SECONDS", "60")
        ),
        object_storage_provider=os.getenv("OBJECT_STORAGE_PROVIDER", "mock"),
        object_storage_bucket=os.getenv("OBJECT_STORAGE_BUCKET"),
        object_storage_region=os.getenv("OBJECT_STORAGE_REGION"),
        object_storage_endpoint_url=os.getenv("OBJECT_STORAGE_ENDPOINT_URL"),
        object_storage_access_key=os.getenv("OBJECT_STORAGE_ACCESS_KEY"),
        object_storage_secret_key=os.getenv("OBJECT_STORAGE_SECRET_KEY"),
        object_storage_public_base_url=os.getenv("OBJECT_STORAGE_PUBLIC_BASE_URL"),
        object_storage_presign_ttl_seconds=int(os.getenv("OBJECT_STORAGE_PRESIGN_TTL_SECONDS", "900")),
        default_shop_id=os.getenv("DEFAULT_SHOP_ID", "shop_default"),
        default_owner_actor_id=os.getenv("DEFAULT_OWNER_ACTOR_ID", "owner_default"),
        default_session_id=os.getenv("DEFAULT_SESSION_ID", "sess_default"),
        seed_owner_email=os.getenv("SEED_OWNER_EMAIL"),
        seed_owner_password=os.getenv("SEED_OWNER_PASSWORD"),
        seed_owner_display_name=os.getenv("SEED_OWNER_DISPLAY_NAME", "Default Owner"),
        auth_session_ttl_minutes=int(os.getenv("AUTH_SESSION_TTL_MINUTES", "120")),
        asr_provider=os.getenv("ASR_PROVIDER", "mock"),
        asr_provider_api_url=os.getenv("ASR_PROVIDER_API_URL"),
        asr_provider_api_key=os.getenv("ASR_PROVIDER_API_KEY"),
        asr_provider_model=os.getenv("ASR_PROVIDER_MODEL"),
        asr_timeout_seconds=float(os.getenv("ASR_TIMEOUT_SECONDS", "15")),
        asr_allow_mock_fallback=os.getenv("ASR_ALLOW_MOCK_FALLBACK", "1") not in ("0", "false", "False"),
        ocr_provider=ocr_provider,
        ocr_provider_api_url=os.getenv("OCR_PROVIDER_API_URL"),
        ocr_provider_api_key=os.getenv("OCR_PROVIDER_API_KEY"),
        ocr_provider_model=os.getenv("OCR_PROVIDER_MODEL"),
        ocr_timeout_seconds=float(os.getenv("OCR_TIMEOUT_SECONDS", "15")),
        ocr_allow_mock_fallback=_parse_bool_env(
            ocr_allow_env,
            app_env.lower() != "production",
        ),
        vision_provider=os.getenv("VISION_PROVIDER", ""),
        vision_provider_api_url=os.getenv("VISION_PROVIDER_API_URL"),
        vision_provider_api_key=os.getenv("VISION_PROVIDER_API_KEY"),
        vision_provider_model=os.getenv("VISION_PROVIDER_MODEL"),
        vision_timeout_seconds=float(os.getenv("VISION_TIMEOUT_SECONDS", "15")),
        vision_allow_mock_fallback=_parse_bool_env(
            vision_allow_env,
            app_env.lower() != "production",
        ),
        trial_provider_profile=os.getenv("TRIAL_PROVIDER_PROFILE", ""),
        asr_provider_label=os.getenv("ASR_PROVIDER_LABEL", ""),
        ocr_provider_label=os.getenv("OCR_PROVIDER_LABEL", ""),
        vision_provider_label=os.getenv("VISION_PROVIDER_LABEL", ""),
        trial_calibration_dataset_dir=os.getenv("TRIAL_CALIBRATION_DATASET_DIR", ""),
        trial_calibration_artifacts_dir=os.getenv("TRIAL_CALIBRATION_ARTIFACTS_DIR", ""),
        live_pilot_allowed_shop_ids_raw=os.getenv("LIVE_PILOT_ALLOWED_SHOP_IDS", ""),
    )
