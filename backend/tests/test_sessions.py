def test_session_bootstrap_returns_default_workgroup(client) -> None:
    response = client.post(
        "/api/v1/sessions/bootstrap",
        headers={"Authorization": "Bearer mock_owner_token"},
    )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["session_id"] == "sess_default"
    assert payload["session_type"] == "workgroup"
    assert payload["participants"] == ["xiaoya", "laoli"]
