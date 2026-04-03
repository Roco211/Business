def test_mock_login_returns_default_owner_context(client) -> None:
    response = client.post("/api/v1/auth/mock-login", json={"shop_id": "shop_default"})

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["access_token"] == "mock_owner_token"
    assert payload["owner_actor_id"] == "owner_default"
    assert payload["shop_id"] == "shop_default"
