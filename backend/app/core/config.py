from dataclasses import dataclass
import os


@dataclass(frozen=True)
class Settings:
    default_shop_id: str = os.getenv("DEFAULT_SHOP_ID", "shop_default")
    default_owner_actor_id: str = os.getenv("DEFAULT_OWNER_ACTOR_ID", "owner_default")
    default_session_id: str = os.getenv("DEFAULT_SESSION_ID", "sess_default")


def get_settings() -> Settings:
    return Settings()
