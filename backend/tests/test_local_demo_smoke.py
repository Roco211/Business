import importlib

import pytest


AUTH_TOKEN = "mock_owner_token"


def _load_local_demo_smoke_module():
    try:
        return importlib.import_module("app.devtools.local_demo_smoke")
    except ModuleNotFoundError as exc:
        pytest.fail(f"app.devtools.local_demo_smoke module is missing: {exc}")


def _build_request_adapter(client):
    def request_json(
        method: str,
        path: str,
        *,
        token: str | None = None,
        payload: dict[str, object] | None = None,
    ) -> tuple[int, object]:
        headers = {"Authorization": f"Bearer {token}"} if token is not None else {}
        response = client.request(method, path, headers=headers, json=payload)
        return response.status_code, response.json()

    return request_json


def test_run_local_demo_smoke_validates_known_good_demo_state(client) -> None:
    module = _load_local_demo_smoke_module()

    result = module.run_local_demo_smoke(
        api_base_url="http://127.0.0.1:8001",
        auth_token=AUTH_TOKEN,
        request_json=_build_request_adapter(client),
    )

    assert result.api_base_url == "http://127.0.0.1:8001"
    assert result.health_status == "ok"
    assert result.shop_id == "shop_default"
    assert result.session_id == "sess_default"
    assert result.inventory_item_count == 3
    assert result.pending_confirmation_count == 2
    assert result.open_low_stock_alert_count == 1
    assert result.message_count == 10
    assert result.replay_event_count > 0
    assert result.latest_replay_seq is not None


def test_run_local_demo_smoke_raises_clear_error_on_demo_state_drift(client) -> None:
    module = _load_local_demo_smoke_module()
    base_request = _build_request_adapter(client)

    def drifting_request(
        method: str,
        path: str,
        *,
        token: str | None = None,
        payload: dict[str, object] | None = None,
    ) -> tuple[int, object]:
        status_code, body = base_request(method, path, token=token, payload=payload)
        if path == "/api/v1/dashboard/summary":
            body = {
                "data": {
                    **body["data"],
                    "pending_confirmations_count": 999,
                }
            }
        return status_code, body

    with pytest.raises(module.LocalDemoSmokeError, match="pending confirmations"):
        module.run_local_demo_smoke(
            api_base_url="http://127.0.0.1:8001",
            auth_token=AUTH_TOKEN,
            request_json=drifting_request,
        )
