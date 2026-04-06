def test_health_returns_ok_payload(client) -> None:
    response = client.get("/health")
    payload = response.json()

    assert response.status_code == 200
    assert payload == {"status": "ok"}
    assert "data" not in payload
