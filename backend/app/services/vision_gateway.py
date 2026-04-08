from dataclasses import dataclass, replace
from functools import lru_cache

from app.core.config import Settings, get_settings
from app.runtime.guardrails import provider_trial_violation
from app.services.vision_mock_provider import MockVisionProvider
from app.services.vision_real_provider import RealVisionProvider
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
        fallback_recognition = self.fallback_provider.recognize_product(media_input)
        if fallback_recognition.used_fallback:
            return fallback_recognition
        return replace(fallback_recognition, used_fallback=True)


def build_vision_gateway(settings: Settings) -> VisionGateway:
    provider_name = settings.vision_provider.strip().lower()
    allow_mock = settings.vision_allow_mock_fallback
    trial_violation = provider_trial_violation(
        settings=settings,
        provider_name=provider_name,
        allow_mock_fallback=allow_mock,
        capability_label="Vision",
    )
    if trial_violation is not None:
        raise VisionProviderError(
            "vision_unavailable",
            trial_violation,
            retryable=False,
        )

    if not provider_name:
        if not allow_mock:
            raise VisionProviderError(
                "vision_unavailable",
                "vision provider is not configured",
                retryable=False,
            )
        return VisionGateway(primary_provider=MockVisionProvider())

    if provider_name == "mock":
        if not allow_mock:
            raise VisionProviderError(
                "vision_unavailable",
                "mock vision provider is disabled by configuration",
                retryable=False,
            )
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

    fallback_provider = MockVisionProvider() if allow_mock else None
    return VisionGateway(
        primary_provider=RealVisionProvider(
            api_url=settings.vision_provider_api_url,
            api_key=settings.vision_provider_api_key,
            model=settings.vision_provider_model,
            timeout_seconds=settings.vision_timeout_seconds,
        ),
        fallback_provider=fallback_provider,
    )


@lru_cache(maxsize=1)
def get_default_vision_gateway() -> VisionGateway:
    return build_vision_gateway(get_settings())
