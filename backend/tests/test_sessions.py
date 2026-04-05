from conftest import auth_headers, login_and_get_token


def test_session_bootstrap_accepts_real_login_token(client, monkeypatch) -> None:
    token = login_and_get_token(client, monkeypatch)

    response = client.post(
        "/api/v1/sessions/bootstrap",
        headers=auth_headers(token),
    )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["session_id"] == "sess_default"
    assert payload["session_type"] == "workgroup"
    assert payload["title"] == "数字员工工作群"
    assert payload["participants"] == ["xiaoya", "laoli"]


def test_session_bootstrap_unauthorized_returns_error_envelope(client) -> None:
    response = client.post("/api/v1/sessions/bootstrap")

    assert response.status_code == 401
    assert response.json() == {
        "error": {
            "code": "unauthorized",
            "message": "Unauthorized",
            "details": [],
        }
    }


def test_openapi_documents_401_for_session_bootstrap(client) -> None:
    response = client.get("/openapi.json")

    responses = response.json()["paths"]["/api/v1/sessions/bootstrap"]["post"]["responses"]

    assert "401" in responses
