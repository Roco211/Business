from __future__ import annotations

from collections.abc import Mapping
import logging
import re
from typing import Any

REDACTED = "[REDACTED]"
SENSITIVE_KEYWORDS = (
    "token",
    "password",
    "secret",
    "api_key",
    "apikey",
    "authorization",
    "cookie",
    "database_url",
    "redis_url",
    "webhook_url",
)
SENSITIVE_TEXT_PATTERNS = (
    re.compile(r"(?i)(token\s*=\s*)([^\s&]+)"),
    re.compile(r"(?i)(password\s*=\s*)([^\s&]+)"),
    re.compile(r"(?i)(secret\s*=\s*)([^\s&]+)"),
    re.compile(r"(?i)(api[_-]?key\s*=\s*)([^\s&]+)"),
    re.compile(r"(?i)(authorization\s*[:=]\s*)([^\s&]+)"),
    re.compile(r"(?i)(redis://)([^\s]+)"),
    re.compile(r"(?i)(postgres(?:ql)?(?:\+\w+)?://)([^\s]+)"),
    re.compile(r"(?i)(https?://[^\s]*(?:hook|webhook)[^\s]*)"),
)


def _is_sensitive_key(key: str) -> bool:
    normalized = key.strip().lower().replace("-", "_")
    return any(keyword in normalized for keyword in SENSITIVE_KEYWORDS)


def _sanitize_text(value: str) -> str:
    sanitized = value
    for pattern in SENSITIVE_TEXT_PATTERNS:
        if pattern.groups >= 2:
            sanitized = pattern.sub(lambda match: f"{match.group(1)}{REDACTED}", sanitized)
        else:
            sanitized = pattern.sub(REDACTED, sanitized)
    return sanitized


def sanitize_for_log(value: Any) -> Any:
    if isinstance(value, Mapping):
        sanitized: dict[str, Any] = {}
        for raw_key, raw_value in value.items():
            key = str(raw_key)
            sanitized[key] = REDACTED if _is_sensitive_key(key) else sanitize_for_log(raw_value)
        return sanitized
    if isinstance(value, list):
        return [sanitize_for_log(item) for item in value]
    if isinstance(value, tuple):
        return tuple(sanitize_for_log(item) for item in value)
    if isinstance(value, str):
        return _sanitize_text(value)
    return value


def build_request_log_payload(
    *,
    event: str,
    request_id: str,
    method: str,
    path: str,
    status_code: int,
    latency_ms: float,
    client_ip: str = "",
    user_agent: str = "",
    account_id: str = "",
    tenant_id: str = "",
    shop_id: str = "",
    error_code: str = "",
    exception_type: str = "",
    exception_message: str = "",
) -> dict[str, str]:
    payload = {
        "event": event,
        "request_id": request_id,
        "method": method,
        "path": path,
        "status_code": str(status_code),
        "latency_ms": f"{latency_ms:.2f}",
        "client_ip": client_ip,
        "user_agent": user_agent,
        "account_id": account_id,
        "tenant_id": tenant_id,
        "shop_id": shop_id,
        "error_code": error_code,
        "exception_type": exception_type,
        "exception_message": exception_message,
    }
    return sanitize_for_log(payload)


def emit_structured_log(logger: logging.Logger, *, level: int, message: str, payload: Mapping[str, Any]) -> None:
    sanitized_payload = sanitize_for_log(dict(payload))
    logger.log(level, message, extra={"structured_payload": sanitized_payload})


class MockAlertSender:
    def __init__(self, *, enabled: bool, webhook_url: str = "") -> None:
        self.enabled = enabled
        self.webhook_url_configured = bool(webhook_url.strip())

    def send(self, *, title: str, payload: Mapping[str, Any]) -> dict[str, str]:
        return {
            "sent": str(self.enabled and self.webhook_url_configured).lower(),
            "title": sanitize_for_log(title),
            "webhook_url_configured": str(self.webhook_url_configured).lower(),
            "payload_keys": ",".join(sorted(str(key) for key in payload.keys())),
        }


def create_alert_sender(*, enabled: bool, webhook_url: str = "") -> MockAlertSender:
    return MockAlertSender(enabled=enabled, webhook_url=webhook_url)
