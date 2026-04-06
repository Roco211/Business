from dataclasses import dataclass
from functools import lru_cache

from app.core.config import Settings, get_settings
from app.services.vision_mock_provider import MockVisionProvider
from app.services.vision_types import (
    VisionMediaInput,
    VisionProvider,
    VisionProviderError,
    VisionRecognition,
)

SUPPORTED_REAL_PROVIDER_NAMES = {"real-provider"}


@dataclass(frozen=True)
class VisionGateway:
    primary_provider: VisionProvider
    fallback_provider: VisionProvider | None = None

    def recognize_product(self, media_input: VisionMediaInput) -> VisionRecognition:
        try:
            return self.primary_provider.recognize_product(media_input)
        except VisionProviderError as exc:
            if self.fallback_provider is None or not exc.retryable:
                raise
        return self.fallback_provider.recognize_product(media_input)


def build_vision_gateway(settings: Settings) -> VisionGateway:
    provider_name = settings.vision_provider.strip().lower()
    if not provider_name or provider_name == "mock":
        return VisionGateway(primary_provider=MockVisionProvider())

    if provider_name not in SUPPORTED_REAL_PROVIDER_NAMES:
        raise VisionProviderError(
            "vision_unavailable",
            f"unsupported vision provider: {settings.vision_provider}",
            retryable=False,
        )

    if (
        not settings.vision_provider_api_url
        or not settings.vision_provider_api_key
        or not settings.vision_provider_model
    ):
        raise VisionProviderError(
            "vision_unavailable",
            "missing vision provider configuration",
            retryable=False,
        )

    raise VisionProviderError(
        "vision_unavailable",
        "real vision provider is not implemented",
        retryable=False,
    )


@lru_cache(maxsize=1)
def get_default_vision_gateway() -> VisionGateway:
    return build_vision_gateway(get_settings())
