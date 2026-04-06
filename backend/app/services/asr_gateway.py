from dataclasses import dataclass
from functools import lru_cache

from app.core.config import Settings, get_settings
from app.services.asr_mock_provider import MockAsrProvider
from app.services.asr_real_provider import RealAsrProvider
from app.services.asr_types import AsrMediaInput, AsrProvider, AsrProviderError, AsrTranscription


@dataclass(frozen=True)
class AsrGateway:
    primary_provider: AsrProvider
    fallback_provider: AsrProvider | None = None

    def transcribe(self, media_input: AsrMediaInput) -> AsrTranscription:
        try:
            return self.primary_provider.transcribe(media_input)
        except AsrProviderError:
            if self.fallback_provider is None:
                raise
        return self.fallback_provider.transcribe(media_input)


def build_asr_gateway(settings: Settings) -> AsrGateway:
    provider_name = settings.asr_provider.strip().lower()
    if provider_name == "mock":
        return AsrGateway(primary_provider=MockAsrProvider())

    if not settings.asr_provider_api_url or not settings.asr_provider_api_key or not settings.asr_provider_model:
        raise AsrProviderError(
            "asr_unavailable",
            "missing ASR provider configuration",
            retryable=False,
        )

    fallback_provider = MockAsrProvider() if settings.asr_allow_mock_fallback else None
    return AsrGateway(
        primary_provider=RealAsrProvider(
            api_url=settings.asr_provider_api_url,
            api_key=settings.asr_provider_api_key,
            model=settings.asr_provider_model,
            timeout_seconds=settings.asr_timeout_seconds,
        ),
        fallback_provider=fallback_provider,
    )


@lru_cache(maxsize=1)
def get_default_asr_gateway() -> AsrGateway:
    return build_asr_gateway(get_settings())
