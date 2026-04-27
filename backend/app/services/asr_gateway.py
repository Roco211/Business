from dataclasses import dataclass
from functools import lru_cache

from app.core.config import Settings, get_settings
from app.runtime.guardrails import provider_trial_violation
from app.services.ark_multimodal_provider import ARK_CHAT_COMPLETIONS_URL, ArkAsrProvider
from app.services.asr_mock_provider import MockAsrProvider
from app.services.asr_real_provider import RealAsrProvider
from app.services.asr_types import AsrMediaInput, AsrProvider, AsrProviderError, AsrTranscription

SUPPORTED_REAL_PROVIDER_NAMES = {"real-provider", "volcano", "doubao", "ark", "ark-doubao"}


@dataclass(frozen=True)
class AsrGateway:
    primary_provider: AsrProvider
    fallback_provider: AsrProvider | None = None

    def transcribe(self, media_input: AsrMediaInput) -> AsrTranscription:
        try:
            return self.primary_provider.transcribe(media_input)
        except AsrProviderError as exc:
            if self.fallback_provider is None or not exc.retryable:
                raise
        return self.fallback_provider.transcribe(media_input)


def build_asr_gateway(settings: Settings) -> AsrGateway:
    provider_name = settings.asr_provider.strip().lower()
    trial_violation = provider_trial_violation(
        settings=settings,
        provider_name=provider_name,
        allow_mock_fallback=settings.asr_allow_mock_fallback,
        capability_label="ASR",
    )
    if trial_violation is not None:
        raise AsrProviderError(
            "asr_unavailable",
            trial_violation,
            retryable=False,
        )

    if provider_name == "mock":
        return AsrGateway(primary_provider=MockAsrProvider())
    if provider_name not in SUPPORTED_REAL_PROVIDER_NAMES:
        raise AsrProviderError(
            "asr_unavailable",
            f"unsupported ASR provider: {settings.asr_provider}",
            retryable=False,
        )

    if provider_name in {"volcano", "doubao", "ark", "ark-doubao"}:
        if not settings.asr_provider_api_key or not settings.asr_provider_model:
            raise AsrProviderError(
                "asr_unavailable",
                "missing ASR provider configuration",
                retryable=False,
            )

        fallback_provider = MockAsrProvider() if settings.asr_allow_mock_fallback else None
        return AsrGateway(
            primary_provider=ArkAsrProvider(
                api_url=settings.asr_provider_api_url or ARK_CHAT_COMPLETIONS_URL,
                api_key=settings.asr_provider_api_key,
                model=settings.asr_provider_model,
                timeout_seconds=settings.asr_timeout_seconds,
            ),
            fallback_provider=fallback_provider,
        )

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
