from dataclasses import dataclass, replace
from functools import lru_cache

from app.core.config import Settings, get_settings
from app.services.ocr_mock_provider import MockOcrProvider
from app.services.ocr_real_provider import RealOcrProvider
from app.services.ocr_types import (
    OcrExtraction,
    OcrMediaInput,
    OcrProvider,
    OcrProviderError,
)


SUPPORTED_REAL_PROVIDER_NAMES = {"real-provider"}


@dataclass(frozen=True)
class OcrGateway:
    primary_provider: OcrProvider
    fallback_provider: OcrProvider | None = None

    def extract_purchase_receipt(self, media_input: OcrMediaInput) -> OcrExtraction:
        try:
            return self.primary_provider.extract_purchase_receipt(media_input)
        except OcrProviderError as exc:
            if self.fallback_provider is None or not exc.retryable:
                raise
        fallback_extraction = self.fallback_provider.extract_purchase_receipt(media_input)
        return replace(fallback_extraction, used_fallback=True)


def build_ocr_gateway(settings: Settings) -> OcrGateway:
    provider_name = settings.ocr_provider.strip().lower()
    if not provider_name:
        if settings.ocr_allow_mock_fallback:
            return OcrGateway(primary_provider=MockOcrProvider())
        raise OcrProviderError(
            "ocr_unavailable",
            "OCR provider is not configured",
            retryable=False,
        )
    if provider_name == "mock":
        if not settings.ocr_allow_mock_fallback:
            raise OcrProviderError(
                "ocr_unavailable",
                "mock OCR provider is disabled by configuration",
                retryable=False,
            )
        return OcrGateway(primary_provider=MockOcrProvider())

    if provider_name == "real-provider":
        if (
            not settings.ocr_provider_api_url
            or not settings.ocr_provider_api_key
            or not settings.ocr_provider_model
        ):
            raise OcrProviderError(
                "ocr_unavailable",
                "missing OCR provider configuration",
                retryable=False,
            )
        fallback_provider = MockOcrProvider() if settings.ocr_allow_mock_fallback else None
        return OcrGateway(
            primary_provider=RealOcrProvider(
                api_url=settings.ocr_provider_api_url,
                api_key=settings.ocr_provider_api_key,
                model=settings.ocr_provider_model,
                timeout_seconds=settings.ocr_timeout_seconds,
            ),
            fallback_provider=fallback_provider,
        )

    raise OcrProviderError(
        "ocr_unavailable",
        f"unsupported OCR provider: {settings.ocr_provider}",
        retryable=False,
    )


@lru_cache(maxsize=1)
def get_default_ocr_gateway() -> OcrGateway:
    return build_ocr_gateway(get_settings())
