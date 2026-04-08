from app.main import create_app


def test_health_returns_ok_payload(client) -> None:
    response = client.get("/health")
    payload = response.json()

    assert response.status_code == 200
    assert payload == {"status": "ok"}
    assert "data" not in payload


def test_readiness_route_openapi_documents_401_response() -> None:
    schema = create_app().openapi()
    readiness_get = schema["paths"]["/api/v1/system/readiness"]["get"]

    assert "401" in readiness_get["responses"]
