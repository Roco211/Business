from dataclasses import dataclass
import os


@dataclass(frozen=True)
class Settings:
    app_env: str
    app_host: str
    app_port: int
    redis_url: str
    default_shop_id: str = os.getenv("DEFAULT_SHOP_ID", "shop_default")
    default_owner_actor_id: str = os.getenv("DEFAULT_OWNER_ACTOR_ID", "owner_default")
    default_session_id: str = os.getenv("DEFAULT_SESSION_ID", "sess_default")


def get_settings() -> Settings:
    return Settings(
        app_env=os.getenv("APP_ENV", "development"),
        app_host=os.getenv("APP_HOST", "0.0.0.0"),
        app_port=int(os.getenv("APP_PORT", "8001")),
        redis_url=os.getenv("REDIS_URL", "redis://redis:6379/0"),
        default_shop_id=os.getenv("DEFAULT_SHOP_ID", "shop_default"),
        default_owner_actor_id=os.getenv("DEFAULT_OWNER_ACTOR_ID", "owner_default"),
        default_session_id=os.getenv("DEFAULT_SESSION_ID", "sess_default"),
    )
