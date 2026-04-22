from __future__ import annotations

from dataclasses import asdict, dataclass
from json import JSONDecodeError
import os
from typing import Any, Protocol

import httpx


EXPECTED_DEMO_SUMMARY = {
    "shop_id": "shop_default",
    "session_id": "sess_default",
    "inventory_item_count": 3,
    "inventory_item_names": ["Coca Cola 500ml", "Cola", "Red Bull 250ml"],
    "pending_confirmation_count": 2,
    "pending_confirmation_types": ["receipt-stock-in-batch", "stock-out"],
    "open_low_stock_alert_count": 1,
    "open_low_stock_item_names": ["Cola"],
    "message_count": 10,
    "task_run_count": 4,
}
RECENT_MESSAGE_PREVIEW_LIMIT = 4


DEFAULT_LOGIN_EMAIL = "owner@example.com"
DEFAULT_LOGIN_PASSWORD = "dev-password"


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


class LocalDemoSmokeError(RuntimeError):
    """Raised when the live local demo stack drifts from the expected shape."""


@dataclass(frozen=True)
class LocalDemoSmokeResult:
    api_base_url: str
    health_status: str
    shop_id: str
    session_id: str
    inventory_item_count: int
    inventory_item_names: list[str]
    pending_confirmation_count: int
    pending_confirmation_types: list[str]
    open_low_stock_alert_count: int
    open_low_stock_item_names: list[str]
    message_count: int
    task_run_count: int
    recent_messages: list[dict[str, str | None]]
    replay_event_count: int
    latest_replay_seq: int | None

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
            raise LocalDemoSmokeError(f"Request failed for {method} {path}: {exc}") from exc

        try:
            body: object = response.json()
        except JSONDecodeError as exc:  # pragma: no cover - exercised by live script usage
            raise LocalDemoSmokeError(f"Response from {method} {path} was not valid JSON") from exc
        return response.status_code, body

    return request_json


def _expect_status_ok(*, status_code: int, body: object, label: str) -> dict[str, Any]:
    if status_code != 200:
        raise LocalDemoSmokeError(f"{label} returned HTTP {status_code}: {body}")
    if not isinstance(body, dict):
        raise LocalDemoSmokeError(f"{label} returned a non-object payload")
    return body


def _expect_data_envelope(*, status_code: int, body: object, label: str) -> object:
    payload = _expect_status_ok(status_code=status_code, body=body, label=label)
    if "data" not in payload:
        raise LocalDemoSmokeError(f"{label} did not return a data envelope")
    return payload["data"]


def _expect_object(value: object, *, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise LocalDemoSmokeError(f"{label} was not an object")
    return value


def _expect_int(value: object, *, label: str) -> int:
    if not isinstance(value, int):
        raise LocalDemoSmokeError(f"{label} was not an integer")
    return value


def _expect_list(value: object, *, label: str) -> list[object]:
    if not isinstance(value, list):
        raise LocalDemoSmokeError(f"{label} was not a list")
    return value


def _expect_string(value: object, *, label: str) -> str:
    if not isinstance(value, str):
        raise LocalDemoSmokeError(f"{label} was not a string")
    return value


def _expect_optional_string(value: object, *, label: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise LocalDemoSmokeError(f"{label} was not a string or null")
    return value


def _build_recent_message_preview(messages: list[object]) -> list[dict[str, str | None]]:
    preview: list[dict[str, str | None]] = []
    for index, raw_message in enumerate(messages[:RECENT_MESSAGE_PREVIEW_LIMIT]):
        message = _expect_object(raw_message, label=f"Session message[{index}]")
        preview.append(
            {
                "actor_type": _expect_string(message.get("actor_type"), label=f"Session message[{index}].actor_type"),
                "message_type": _expect_string(
                    message.get("message_type"),
                    label=f"Session message[{index}].message_type",
                ),
                "text": _expect_optional_string(message.get("text"), label=f"Session message[{index}].text"),
            }
        )
    return preview


def run_local_demo_smoke(
    *,
    api_base_url: str,
    auth_token: str | None = None,
    login_email: str | None = None,
    login_password: str | None = None,
    request_json: RequestJson | None = None,
) -> LocalDemoSmokeResult:
    request = request_json or _build_live_request(api_base_url)

    health_status_code, health_body = request("GET", "/health", token=None, payload=None)
    health_payload = _expect_status_ok(status_code=health_status_code, body=health_body, label="GET /health")
    health_status = health_payload.get("status")
    if health_status != "ok":
        raise LocalDemoSmokeError("Health status was not ok")

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
            raise LocalDemoSmokeError("Login payload was not an object")
        issued_access_token = login_data.get("access_token")
        if not isinstance(issued_access_token, str) or not issued_access_token:
            raise LocalDemoSmokeError("Login response did not include an access_token")
        active_auth_token = issued_access_token

    demo_status_code, demo_body = request(
        "POST",
        "/api/v1/system/demo/bootstrap",
        token=active_auth_token,
        payload={},
    )
    demo_summary = _expect_data_envelope(
        status_code=demo_status_code,
        body=demo_body,
        label="POST /api/v1/system/demo/bootstrap",
    )
    if demo_summary != EXPECTED_DEMO_SUMMARY:
        raise LocalDemoSmokeError(
            "Demo bootstrap summary drifted from the expected known-good state"
        )

    session_status_code, session_body = request(
        "POST",
        "/api/v1/sessions/bootstrap",
        token=active_auth_token,
        payload={},
    )
    session_data = _expect_data_envelope(
        status_code=session_status_code,
        body=session_body,
        label="POST /api/v1/sessions/bootstrap",
    )
    if not isinstance(session_data, dict):
        raise LocalDemoSmokeError("Session bootstrap payload was not an object")
    session_id = session_data.get("session_id")
    if session_id != EXPECTED_DEMO_SUMMARY["session_id"]:
        raise LocalDemoSmokeError("Session bootstrap returned an unexpected session_id")

    dashboard_status_code, dashboard_body = request(
        "GET",
        "/api/v1/dashboard/summary",
        token=active_auth_token,
        payload=None,
    )
    dashboard_data = _expect_data_envelope(
        status_code=dashboard_status_code,
        body=dashboard_body,
        label="GET /api/v1/dashboard/summary",
    )
    if not isinstance(dashboard_data, dict):
        raise LocalDemoSmokeError("Dashboard summary payload was not an object")
    if dashboard_data.get("pending_confirmations_count") != EXPECTED_DEMO_SUMMARY["pending_confirmation_count"]:
        raise LocalDemoSmokeError("Dashboard pending confirmations count drifted from the demo state")
    if dashboard_data.get("open_low_stock_alert_count") != EXPECTED_DEMO_SUMMARY["open_low_stock_alert_count"]:
        raise LocalDemoSmokeError("Dashboard low-stock alert count drifted from the demo state")

    alerts_status_code, alerts_body = request(
        "GET",
        "/api/v1/alerts?type=low-stock",
        token=active_auth_token,
        payload=None,
    )
    alerts_data = _expect_data_envelope(
        status_code=alerts_status_code,
        body=alerts_body,
        label="GET /api/v1/alerts?type=low-stock",
    )
    alerts = _expect_list(alerts_data, label="Low-stock alerts")
    if len(alerts) != EXPECTED_DEMO_SUMMARY["open_low_stock_alert_count"]:
        raise LocalDemoSmokeError("Low-stock alert count drifted from the demo state")

    confirmations_status_code, confirmations_body = request(
        "GET",
        "/api/v1/confirmations?status=pending",
        token=active_auth_token,
        payload=None,
    )
    confirmations_data = _expect_data_envelope(
        status_code=confirmations_status_code,
        body=confirmations_body,
        label="GET /api/v1/confirmations?status=pending",
    )
    confirmations = _expect_list(confirmations_data, label="Pending confirmations")
    if len(confirmations) != EXPECTED_DEMO_SUMMARY["pending_confirmation_count"]:
        raise LocalDemoSmokeError("Pending confirmations count drifted from the demo state")

    messages_status_code, messages_body = request(
        "GET",
        f"/api/v1/sessions/{session_id}/messages",
        token=active_auth_token,
        payload=None,
    )
    messages_data = _expect_data_envelope(
        status_code=messages_status_code,
        body=messages_body,
        label=f"GET /api/v1/sessions/{session_id}/messages",
    )
    messages = _expect_list(messages_data, label="Session messages")
    if len(messages) != EXPECTED_DEMO_SUMMARY["message_count"]:
        raise LocalDemoSmokeError("Message count drifted from the demo state")
    recent_messages = _build_recent_message_preview(messages)

    replay_status_code, replay_body = request(
        "GET",
        f"/api/v1/sessions/{session_id}/stream-events?after_seq=0&limit=50",
        token=active_auth_token,
        payload=None,
    )
    replay_data = _expect_data_envelope(
        status_code=replay_status_code,
        body=replay_body,
        label=f"GET /api/v1/sessions/{session_id}/stream-events",
    )
    replay_events = _expect_list(replay_data, label="Replay events")
    if not replay_events:
        raise LocalDemoSmokeError("Replay endpoint returned no durable session events")

    replay_seqs = [_expect_int(event.get("seq"), label="Replay event seq") for event in replay_events if isinstance(event, dict)]
    if replay_seqs != sorted(replay_seqs):
        raise LocalDemoSmokeError("Replay events were not returned in ascending seq order")

    return LocalDemoSmokeResult(
        api_base_url=api_base_url,
        health_status=str(health_status),
        shop_id=str(EXPECTED_DEMO_SUMMARY["shop_id"]),
        session_id=str(session_id),
        inventory_item_count=int(EXPECTED_DEMO_SUMMARY["inventory_item_count"]),
        inventory_item_names=list(EXPECTED_DEMO_SUMMARY["inventory_item_names"]),
        pending_confirmation_count=int(EXPECTED_DEMO_SUMMARY["pending_confirmation_count"]),
        pending_confirmation_types=list(EXPECTED_DEMO_SUMMARY["pending_confirmation_types"]),
        open_low_stock_alert_count=int(EXPECTED_DEMO_SUMMARY["open_low_stock_alert_count"]),
        open_low_stock_item_names=list(EXPECTED_DEMO_SUMMARY["open_low_stock_item_names"]),
        message_count=int(EXPECTED_DEMO_SUMMARY["message_count"]),
        task_run_count=int(EXPECTED_DEMO_SUMMARY["task_run_count"]),
        recent_messages=recent_messages,
        replay_event_count=len(replay_events),
        latest_replay_seq=replay_seqs[-1] if replay_seqs else None,
    )
