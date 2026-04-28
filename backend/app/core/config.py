from dataclasses import dataclass
import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env file if it exists. Process environment variables must win so
# Docker/CI/Provider trial preflight can inject production settings safely.
ENV_PATH = Path(__file__).resolve().parent.parent.parent / ".env"
if ENV_PATH.exists():
    load_dotenv(dotenv_path=ENV_PATH, override=False)


@dataclass(frozen=True)
class Settings:
    app_env: str
    app_host: str = "0.0.0.0"
    app_port: int = 8001
    redis_url: str = "redis://redis:6379/0"
    database_url: str = "sqlite:///./business.db"
    app_cors_origins_raw: str = ""
    rate_limit_per_minute: int = 0
    rate_limit_backend: str = "memory"
    structured_logging_enabled: bool = True
    alert_webhook_enabled: bool = False
    alert_webhook_url: str = ""
    security_headers_enabled: bool = False
    backup_dir: str = "/app/backups"
    session_stream_keepalive_seconds: float = 20.0
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
    object_storage_access_key: str | None = os.getenv("OBJECT_STORAGE_ACCESS_KEY_ID") or os.getenv("OBJECT_STORAGE_ACCESS_KEY")
    object_storage_secret_key: str | None = os.getenv("OBJECT_STORAGE_SECRET_ACCESS_KEY") or os.getenv("OBJECT_STORAGE_SECRET_KEY")
    object_storage_public_base_url: str | None = os.getenv("OBJECT_STORAGE_PUBLIC_BASE_URL")
    object_storage_presign_ttl_seconds: int = int(os.getenv("OBJECT_STORAGE_PRESIGN_TTL_SECONDS", "900"))
    default_shop_id: str = os.getenv("DEFAULT_SHOP_ID", "shop_default")
    default_owner_actor_id: str = os.getenv("DEFAULT_OWNER_ACTOR_ID", "owner_default")
    default_session_id: str = os.getenv("DEFAULT_SESSION_ID", "sess_default")
    seed_owner_email: str | None = os.getenv("SEED_OWNER_EMAIL")
    seed_owner_password: str | None = os.getenv("SEED_OWNER_PASSWORD")
    seed_owner_display_name: str = os.getenv("SEED_OWNER_DISPLAY_NAME", "Default Owner")
    auth_session_ttl_minutes: int = int(os.getenv("AUTH_SESSION_TTL_MINUTES", "120"))
    sms_provider: str = os.getenv("SMS_PROVIDER", "demo")
    sms_api_url: str | None = os.getenv("SMS_API_URL")
    sms_access_key_id: str | None = os.getenv("SMS_ACCESS_KEY_ID")
    sms_secret_access_key: str | None = os.getenv("SMS_SECRET_ACCESS_KEY")
    sms_sign_name: str | None = os.getenv("SMS_SIGN_NAME")
    sms_template_id: str | None = os.getenv("SMS_TEMPLATE_ID")
    sms_code_ttl_seconds: int = int(os.getenv("SMS_CODE_TTL_SECONDS", "300"))
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
    llm_provider: str = os.getenv("LLM_PROVIDER", "deepseek")
    llm_provider_api_url: str | None = os.getenv("LLM_PROVIDER_API_URL", "https://api.deepseek.com/v1/chat/completions")
    llm_provider_api_key: str | None = os.getenv("LLM_PROVIDER_API_KEY")
    llm_provider_model: str | None = os.getenv("LLM_PROVIDER_MODEL", "deepseek-v4-flash")
    llm_timeout_seconds: float = float(os.getenv("LLM_TIMEOUT_SECONDS", "30"))
    llm_max_tokens: int = int(os.getenv("LLM_MAX_TOKENS", "500"))
    llm_temperature: float = float(os.getenv("LLM_TEMPERATURE", "0.7"))
    llm_allow_mock_fallback: bool = False
    trial_calibration_dataset_dir: str = os.getenv("TRIAL_CALIBRATION_DATASET_DIR", "")
    trial_calibration_artifacts_dir: str = os.getenv("TRIAL_CALIBRATION_ARTIFACTS_DIR", "")
    live_pilot_allowed_shop_ids_raw: str = os.getenv("LIVE_PILOT_ALLOWED_SHOP_IDS", "")

    def cors_origins(self) -> list[str]:
        raw = self.app_cors_origins_raw.strip()
        if not raw:
            return []
        return [origin.strip() for origin in raw.split(",") if origin.strip()]

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

    def normalized_app_env(self) -> str:
        return self.app_env.strip().lower() or "development"

    def is_production(self) -> bool:
        return self.normalized_app_env() == "production"

    def demo_phone_login_enabled(self) -> bool:
        return (not self.is_production()) and self.normalized_runtime_mode() in {"local-demo", "demo", "development"}

    def sms_required_config(self) -> dict[str, str]:
        return {
            "api_url": self.sms_api_url or "",
            "access_key_id": self.sms_access_key_id or "",
            "secret_access_key": self.sms_secret_access_key or "",
            "sign_name": self.sms_sign_name or "",
            "template_id": self.sms_template_id or "",
        }

    def production_mock_violations(self) -> list[dict[str, str]]:
        if not self.is_production():
            return []

        violations: list[dict[str, str]] = []

        def add(key: str, message: str) -> None:
            violations.append({"key": key, "message": message})

        if self.normalized_runtime_mode() in {"local-demo", "demo", "development", "test"}:
            add("APP_RUNTIME_MODE", "production cannot run in demo/local runtime mode")
            add("DEMO_PHONE_LOGIN", "production cannot enable the 888888 demo phone login")

        if self.sms_provider.strip().lower() in {"", "demo", "mock"}:
            add("SMS_PROVIDER", "production requires a real SMS provider")

        if self.normalized_object_storage_provider() == "mock":
            add("OBJECT_STORAGE_PROVIDER", "production requires real object storage")

        if self.llm_provider.strip().lower() in {"", "mock"}:
            add("LLM_PROVIDER", "production requires real LLM provider")
        if self.llm_allow_mock_fallback:
            add("LLM_ALLOW_MOCK_FALLBACK", "production cannot allow LLM mock fallback")

        if self.ocr_provider.strip().lower() in {"", "mock"}:
            add("OCR_PROVIDER", "production requires real OCR provider")
        if self.ocr_allow_mock_fallback:
            add("OCR_ALLOW_MOCK_FALLBACK", "production cannot allow OCR mock fallback")

        if self.vision_provider.strip().lower() in {"", "mock"}:
            add("VISION_PROVIDER", "production requires real Vision provider")
        if self.vision_allow_mock_fallback:
            add("VISION_ALLOW_MOCK_FALLBACK", "production cannot allow Vision mock fallback")

        if self.asr_provider.strip().lower() not in {"", "client", "client-asr", "disabled", "none"} and self.asr_allow_mock_fallback:
            add("ASR_ALLOW_MOCK_FALLBACK", "production cannot allow ASR mock fallback when server ASR is enabled")

        return violations

    def live_pilot_allowed_shop_ids(self) -> list[str]:
        raw = self.live_pilot_allowed_shop_ids_raw.strip()
        return [shop_id.strip() for shop_id in raw.split(",") if shop_id.strip()]


def _build_default_database_url() -> str:
    postgres_user = os.getenv("POSTGRES_USER", "business")
    postgres_password = os.getenv("POSTGRES_PASSWORD", "business_password")
    postgres_host = os.getenv("POSTGRES_HOST", "postgres")
    postgres_port = os.getenv("POSTGRES_PORT", "5432")
    postgres_database = os.getenv("POSTGRES_DB", "business")
    return (
        f"postgresql+psycopg://{postgres_user}:{postgres_password}@"
        f"{postgres_host}:{postgres_port}/{postgres_database}"
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
        app_cors_origins_raw=os.getenv("APP_CORS_ORIGINS", ""),
        rate_limit_per_minute=int(os.getenv("APP_RATE_LIMIT_PER_MINUTE", "0")),
        rate_limit_backend=os.getenv("APP_RATE_LIMIT_BACKEND", "memory"),
        structured_logging_enabled=_parse_bool_env(os.getenv("APP_STRUCTURED_LOGGING_ENABLED"), True),
        alert_webhook_enabled=_parse_bool_env(os.getenv("APP_ALERT_WEBHOOK_ENABLED"), False),
        alert_webhook_url=os.getenv("APP_ALERT_WEBHOOK_URL", ""),
        security_headers_enabled=_parse_bool_env(os.getenv("APP_SECURITY_HEADERS_ENABLED"), app_env.lower() == "production"),
        backup_dir=os.getenv("BACKUP_DIR", "/app/backups"),
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
        object_storage_access_key=os.getenv("OBJECT_STORAGE_ACCESS_KEY_ID") or os.getenv("OBJECT_STORAGE_ACCESS_KEY"),
        object_storage_secret_key=os.getenv("OBJECT_STORAGE_SECRET_ACCESS_KEY") or os.getenv("OBJECT_STORAGE_SECRET_KEY"),
        object_storage_public_base_url=os.getenv("OBJECT_STORAGE_PUBLIC_BASE_URL"),
        object_storage_presign_ttl_seconds=int(os.getenv("OBJECT_STORAGE_PRESIGN_TTL_SECONDS", "900")),
        default_shop_id=os.getenv("DEFAULT_SHOP_ID", "shop_default"),
        default_owner_actor_id=os.getenv("DEFAULT_OWNER_ACTOR_ID", "owner_default"),
        default_session_id=os.getenv("DEFAULT_SESSION_ID", "sess_default"),
        seed_owner_email=os.getenv("SEED_OWNER_EMAIL"),
        seed_owner_password=os.getenv("SEED_OWNER_PASSWORD"),
        seed_owner_display_name=os.getenv("SEED_OWNER_DISPLAY_NAME", "Default Owner"),
        auth_session_ttl_minutes=int(os.getenv("AUTH_SESSION_TTL_MINUTES", "120")),
        sms_provider=os.getenv("SMS_PROVIDER", "demo"),
        sms_api_url=os.getenv("SMS_API_URL"),
        sms_access_key_id=os.getenv("SMS_ACCESS_KEY_ID"),
        sms_secret_access_key=os.getenv("SMS_SECRET_ACCESS_KEY"),
        sms_sign_name=os.getenv("SMS_SIGN_NAME"),
        sms_template_id=os.getenv("SMS_TEMPLATE_ID"),
        sms_code_ttl_seconds=int(os.getenv("SMS_CODE_TTL_SECONDS", "300")),
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
        llm_provider=os.getenv("LLM_PROVIDER", "deepseek"),
        llm_provider_api_url=os.getenv("LLM_PROVIDER_API_URL", "https://api.deepseek.com/v1/chat/completions"),
        llm_provider_api_key=os.getenv("LLM_PROVIDER_API_KEY"),
        llm_provider_model=os.getenv("LLM_PROVIDER_MODEL", "deepseek-v4-flash"),
        llm_timeout_seconds=float(os.getenv("LLM_TIMEOUT_SECONDS", "30")),
        llm_max_tokens=int(os.getenv("LLM_MAX_TOKENS", "500")),
        llm_temperature=float(os.getenv("LLM_TEMPERATURE", "0.7")),
        llm_allow_mock_fallback=False,
        trial_calibration_dataset_dir=os.getenv("TRIAL_CALIBRATION_DATASET_DIR", ""),
        trial_calibration_artifacts_dir=os.getenv("TRIAL_CALIBRATION_ARTIFACTS_DIR", ""),
        live_pilot_allowed_shop_ids_raw=os.getenv("LIVE_PILOT_ALLOWED_SHOP_IDS", ""),
    )
