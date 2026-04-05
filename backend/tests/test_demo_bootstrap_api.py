from conftest import auth_headers, login_and_get_token

DEFAULT_SESSION_ID = "sess_default"


def _auth_headers(client, monkeypatch=None) -> dict[str, str]:
    return auth_headers(login_and_get_token(client, monkeypatch))


def _post_demo_bootstrap(client) -> dict[str, object]:
    response = client.post("/api/v1/system/demo/bootstrap", headers=_auth_headers(client))
    assert response.status_code == 200
    return response.json()["data"]


def test_demo_bootstrap_endpoint_requires_owner_auth(client) -> None:
    response = client.post("/api/v1/system/demo/bootstrap")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


def test_demo_bootstrap_endpoint_returns_stable_summary_and_seeded_state(client) -> None:
    summary = _post_demo_bootstrap(client)
    messages_response = client.get(f"/api/v1/sessions/{DEFAULT_SESSION_ID}/messages", headers=_auth_headers(client))
    dashboard_response = client.get("/api/v1/dashboard/summary", headers=_auth_headers(client))

    assert summary == {
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
    assert messages_response.status_code == 200
    assert len(messages_response.json()["data"]) == 10
    assert dashboard_response.status_code == 200
    assert dashboard_response.json()["data"]["today_stock_in_count"] == 3
    assert dashboard_response.json()["data"]["pending_confirmations_count"] == 2
    assert dashboard_response.json()["data"]["open_low_stock_alert_count"] == 1


def test_demo_bootstrap_endpoint_is_repeatable(client) -> None:
    first_summary = _post_demo_bootstrap(client)
    second_summary = _post_demo_bootstrap(client)

    assert second_summary == first_summary
