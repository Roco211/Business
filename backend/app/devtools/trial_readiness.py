from __future__ import annotations

from dataclasses import asdict, dataclass
from json import JSONDecodeError
import os
from typing import Any, Protocol

import httpx

from app.devtools.local_demo_smoke import DEFAULT_LOGIN_EMAIL, DEFAULT_LOGIN_PASSWORD

READY_STATUS = "ready"


class RequestJson(Protocol):
    def __call__(
        self,
        method: str,
        path: str,
        *,
        token: str | None = None,
        payload: dict[str, object] | None = None,
    ) -> tuple[int, object]:
        ...


class TrialReadinessError(RuntimeError):
    """Raised when operator-facing trial readiness checks cannot be completed."""


@dataclass(frozen=True)
class TrialReadinessSummary:
    api_base_url: str
    health_status: str
    runtime_mode: str
    readiness_status: str
    overall_status: str
    object_storage: dict[str, str]
    providers: dict[str, dict[str, str]]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _build_live_request(api_base_url: str) -> RequestJson:
    base_url = api_base_url.rstrip("/")

    def request_json(
        method: str,
        path: str,
        *,
        token: str | None = None,
        payload: dict[str, object] | None = None,
    ) -> tuple[int, object]:
        headers = {"Authorization": f"Bearer {token}"} if token is not None else {}
        try:
            request_kwargs: dict[str, object] = {
                "headers": headers,
                "timeout": 10.0,
            }
            if payload is not None:
                request_kwargs["json"] = payload
            response = httpx.request(method, f"{base_url}{path}", **request_kwargs)
        except httpx.HTTPError as exc:  # pragma: no cover - exercised by live script usage
            raise TrialReadinessError(f"Request failed for {method} {path}: {exc}") from exc

        try:
            body: object = response.json()
        except JSONDecodeError as exc:  # pragma: no cover - exercised by live script usage
            raise TrialReadinessError(f"Response from {method} {path} was not valid JSON") from exc
        return response.status_code, body

    return request_json


def _expect_status_ok(*, status_code: int, body: object, label: str) -> dict[str, Any]:
    if status_code != 200:
        raise TrialReadinessError(f"{label} returned HTTP {status_code}: {body}")
    if not isinstance(body, dict):
        raise TrialReadinessError(f"{label} returned a non-object payload")
    return body


def _expect_data_envelope(*, status_code: int, body: object, label: str) -> object:
    payload = _expect_status_ok(status_code=status_code, body=body, label=label)
    if "data" not in payload:
        raise TrialReadinessError(f"{label} did not return a data envelope")
    return payload["data"]


def _expect_string(value: object, *, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise TrialReadinessError(f"{label} was missing or not a non-empty string")
    return value


def _extract_check_summary(checks: object, *, key: str) -> dict[str, str]:
    if not isinstance(checks, dict):
        raise TrialReadinessError("Readiness checks payload was not an object")
    check_payload = checks.get(key)
    if not isinstance(check_payload, dict):
        raise TrialReadinessError(f"Readiness checks payload did not include '{key}'")

    return {
        "status": _expect_string(check_payload.get("status"), label=f"Readiness check '{key}'.status"),
        "mode": _expect_string(check_payload.get("mode"), label=f"Readiness check '{key}'.mode"),
    }


def run_trial_readiness(
    *,
    api_base_url: str,
    auth_token: str | None = None,
    login_email: str | None = None,
    login_password: str | None = None,
    request_json: RequestJson | None = None,
) -> TrialReadinessSummary:
    request = request_json or _build_live_request(api_base_url)

    health_status_code, health_body = request("GET", "/health", token=None, payload=None)
    health_payload = _expect_status_ok(status_code=health_status_code, body=health_body, label="GET /health")
    health_status = _expect_string(health_payload.get("status"), label="GET /health status")
    if health_status != "ok":
        raise TrialReadinessError("Health status was not ok")

    resolved_login_email = login_email or os.getenv("SEED_OWNER_EMAIL", DEFAULT_LOGIN_EMAIL)
    resolved_login_password = login_password or os.getenv("SEED_OWNER_PASSWORD", DEFAULT_LOGIN_PASSWORD)

    active_auth_token = auth_token
    if active_auth_token is None:
        login_status_code, login_body = request(
            "POST",
            "/api/v1/auth/login",
            token=None,
            payload={"email": resolved_login_email, "password": resolved_login_password},
        )
        login_data = _expect_data_envelope(
            status_code=login_status_code,
            body=login_body,
            label="POST /api/v1/auth/login",
        )
        if not isinstance(login_data, dict):
            raise TrialReadinessError("Login payload was not an object")
        active_auth_token = _expect_string(
            login_data.get("access_token"),
            label="POST /api/v1/auth/login access_token",
        )

    readiness_status_code, readiness_body = request(
        "GET",
        "/api/v1/system/readiness",
        token=active_auth_token,
        payload=None,
    )
    readiness_data = _expect_data_envelope(
        status_code=readiness_status_code,
        body=readiness_body,
        label="GET /api/v1/system/readiness",
    )
    if not isinstance(readiness_data, dict):
        raise TrialReadinessError("Readiness payload was not an object")

    readiness_status = _expect_string(
        readiness_data.get("overall_status"),
        label="GET /api/v1/system/readiness overall_status",
    )
    runtime_mode = _expect_string(
        readiness_data.get("runtime_mode"),
        label="GET /api/v1/system/readiness runtime_mode",
    )
    checks = readiness_data.get("checks")

    object_storage = _extract_check_summary(checks, key="object_storage")
    providers = {
        "asr": _extract_check_summary(checks, key="asr"),
        "ocr": _extract_check_summary(checks, key="ocr"),
        "vision": _extract_check_summary(checks, key="vision"),
    }

    return TrialReadinessSummary(
        api_base_url=api_base_url,
        health_status=health_status,
        runtime_mode=runtime_mode,
        readiness_status=readiness_status,
        overall_status=readiness_status,
        object_storage=object_storage,
        providers=providers,
    )
