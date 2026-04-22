import importlib

import pytest

from conftest import login_and_get_token


def _load_local_demo_smoke_module():
    try:
        return importlib.import_module("app.devtools.local_demo_smoke")
    except ModuleNotFoundError as exc:
        pytest.fail(f"app.devtools.local_demo_smoke module is missing: {exc}")


def _load_local_demo_smoke_script_module():
    try:
        return importlib.import_module("scripts.run_local_demo_smoke")
    except ModuleNotFoundError as exc:
        pytest.fail(f"scripts.run_local_demo_smoke module is missing: {exc}")


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
    auth_token = login_and_get_token(client)

    result = module.run_local_demo_smoke(
        api_base_url="http://127.0.0.1:8001",
        auth_token=auth_token,
        request_json=_build_request_adapter(client),
    )

    assert result.api_base_url == "http://127.0.0.1:8001"
    assert result.health_status == "ok"
    assert result.shop_id == "shop_default"
    assert result.session_id == "sess_default"
    assert result.inventory_item_count == 3
    assert result.inventory_item_names == ["Coca Cola 500ml", "Cola", "Red Bull 250ml"]
    assert result.pending_confirmation_count == 2
    assert result.pending_confirmation_types == ["receipt-stock-in-batch", "stock-out"]
    assert result.open_low_stock_alert_count == 1
    assert result.open_low_stock_item_names == ["Cola"]
    assert result.message_count == 10
    assert result.task_run_count == 4
    assert result.recent_messages == [
        {
            "actor_type": "system",
            "message_type": "text",
            "text": "Please confirm the receipt line items before committing inventory.",
        },
        {
            "actor_type": "owner",
            "message_type": "receipt-image",
            "text": None,
        },
        {
            "actor_type": "system",
            "message_type": "text",
            "text": "Please confirm the stock-out details before commit.",
        },
        {
            "actor_type": "owner",
            "message_type": "text",
            "text": "stock out red bull for breakage",
        },
    ]
    assert result.replay_event_count > 0
    assert result.latest_replay_seq is not None


def test_run_local_demo_smoke_raises_clear_error_on_demo_state_drift(client) -> None:
    module = _load_local_demo_smoke_module()
    base_request = _build_request_adapter(client)
    auth_token = login_and_get_token(client)

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
            auth_token=auth_token,
            request_json=drifting_request,
        )


def test_run_local_demo_smoke_logs_in_when_auth_token_is_not_provided(client) -> None:
    module = _load_local_demo_smoke_module()

    result = module.run_local_demo_smoke(
        api_base_url="http://127.0.0.1:8001",
        auth_token=None,
        login_email="owner@example.com",
        login_password="dev-password",
        request_json=_build_request_adapter(client),
    )

    assert result.health_status == "ok"
    assert result.session_id == "sess_default"
    assert result.shop_id == "shop_default"


def test_run_local_demo_smoke_uses_seed_owner_env_credentials_by_default(client, monkeypatch) -> None:
    module = _load_local_demo_smoke_module()
    monkeypatch.setenv("SEED_OWNER_EMAIL", "pilot-owner@example.com")
    monkeypatch.setenv("SEED_OWNER_PASSWORD", "pilot-pass-123")

    result = module.run_local_demo_smoke(
        api_base_url="http://127.0.0.1:8001",
        auth_token=None,
        request_json=_build_request_adapter(client),
    )

    assert result.health_status == "ok"
    assert result.shop_id == "shop_default"


def test_run_local_demo_smoke_cli_defaults_to_login_credentials() -> None:
    script_module = _load_local_demo_smoke_script_module()
    parser = script_module.build_parser()

    args = parser.parse_args([])

    assert args.auth_token is None
    assert args.login_email == "owner@example.com"
    assert args.login_password == "dev-password"


def test_run_local_demo_smoke_cli_defaults_follow_seed_owner_env(monkeypatch) -> None:
    script_module = _load_local_demo_smoke_script_module()
    monkeypatch.setenv("SEED_OWNER_EMAIL", "pilot-owner@example.com")
    monkeypatch.setenv("SEED_OWNER_PASSWORD", "pilot-pass-123")
    parser = script_module.build_parser()

    args = parser.parse_args([])

    assert args.auth_token is None
    assert args.login_email == "pilot-owner@example.com"
    assert args.login_password == "pilot-pass-123"
