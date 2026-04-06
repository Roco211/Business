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
    ocr_provider: str = os.getenv("OCR_PROVIDER", "mock")
    ocr_provider_api_url: str | None = os.getenv("OCR_PROVIDER_API_URL")
    ocr_provider_api_key: str | None = os.getenv("OCR_PROVIDER_API_KEY")
    ocr_provider_model: str | None = os.getenv("OCR_PROVIDER_MODEL")
    ocr_timeout_seconds: float = float(os.getenv("OCR_TIMEOUT_SECONDS", "15"))
    ocr_allow_mock_fallback: bool = os.getenv("OCR_ALLOW_MOCK_FALLBACK", "1") not in ("0", "false", "False")


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


def get_settings() -> Settings:
    return Settings(
        app_env=os.getenv("APP_ENV", "development"),
        app_host=os.getenv("APP_HOST", "0.0.0.0"),
        app_port=int(os.getenv("APP_PORT", "8001")),
        redis_url=os.getenv("REDIS_URL", "redis://redis:6379/0"),
        database_url=os.getenv("DATABASE_URL", _build_default_database_url()),
        session_stream_keepalive_seconds=float(os.getenv("SESSION_STREAM_KEEPALIVE_SECONDS", "20")),
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
        ocr_provider=os.getenv("OCR_PROVIDER", "mock"),
        ocr_provider_api_url=os.getenv("OCR_PROVIDER_API_URL"),
        ocr_provider_api_key=os.getenv("OCR_PROVIDER_API_KEY"),
        ocr_provider_model=os.getenv("OCR_PROVIDER_MODEL"),
        ocr_timeout_seconds=float(os.getenv("OCR_TIMEOUT_SECONDS", "15")),
        ocr_allow_mock_fallback=os.getenv("OCR_ALLOW_MOCK_FALLBACK", "1") not in ("0", "false", "False"),
    )
