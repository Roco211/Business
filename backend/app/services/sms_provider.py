from typing import Protocol

from app.core.config import Settings


class SmsProviderConfigurationError(ValueError):
    pass


class SmsProviderUnavailableError(RuntimeError):
    pass


class SmsProvider(Protocol):
    def send_verification_code(self, *, phone: str, code: str) -> None:
        ...


class DemoSmsProvider:
    """Local-demo provider: records no external side effect."""

    def send_verification_code(self, *, phone: str, code: str) -> None:
        del phone, code


class HttpSmsProvider:
    """Placeholder for commercial SMS providers configured outside source control."""

    def __init__(self, *, api_url: str, access_key_id: str, secret_access_key: str, sign_name: str, template_id: str) -> None:
        self.api_url = api_url
        self.access_key_id = access_key_id
        self.secret_access_key = secret_access_key
        self.sign_name = sign_name
        self.template_id = template_id

    def send_verification_code(self, *, phone: str, code: str) -> None:  # pragma: no cover - provider-specific integration
        del phone, code
        raise SmsProviderUnavailableError("real SMS provider adapter is not configured in this environment")


def get_default_sms_provider(settings: Settings) -> SmsProvider:
    provider = settings.sms_provider.strip().lower()
    if provider in {"", "demo", "mock"}:
        if settings.is_production():
            raise SmsProviderConfigurationError("production requires a real SMS provider")
        return DemoSmsProvider()

    if provider in {"http", "volcengine", "aliyun", "tencent"}:
        missing = [key for key, value in settings.sms_required_config().items() if not value.strip()]
        if missing:
            raise SmsProviderConfigurationError(f"missing required SMS configuration: {','.join(missing)}")
        return HttpSmsProvider(
            api_url=settings.sms_api_url or "",
            access_key_id=settings.sms_access_key_id or "",
            secret_access_key=settings.sms_secret_access_key or "",
            sign_name=settings.sms_sign_name or "",
            template_id=settings.sms_template_id or "",
        )

    raise SmsProviderConfigurationError(f"unsupported SMS provider: {settings.sms_provider}")
