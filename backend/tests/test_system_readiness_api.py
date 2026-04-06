from conftest import auth_headers, login_and_get_token


def _auth_headers(client, monkeypatch=None) -> dict[str, str]:
    return auth_headers(login_and_get_token(client, monkeypatch))


def test_readiness_endpoint_requires_owner_auth(client) -> None:
    response = client.get("/api/v1/system/readiness")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


def test_readiness_endpoint_reports_ready_for_local_demo_with_mock_dependencies(client, monkeypatch) -> None:
    monkeypatch.setenv("APP_RUNTIME_MODE", "local-demo")
    monkeypatch.setenv("OBJECT_STORAGE_PROVIDER", "mock")
    monkeypatch.setenv("ASR_PROVIDER", "mock")
    monkeypatch.setenv("OCR_PROVIDER", "mock")
    monkeypatch.setenv("VISION_PROVIDER", "mock")

    response = client.get("/api/v1/system/readiness", headers=_auth_headers(client, monkeypatch))

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["overall_status"] == "ready"
    assert payload["runtime_mode"] == "local-demo"
    assert payload["checks"]["object_storage"]["status"] == "ready"
    assert payload["checks"]["object_storage"]["mode"] == "mock"
    assert payload["checks"]["asr"]["status"] == "ready"
    assert payload["checks"]["asr"]["mode"] == "mock"
    assert payload["checks"]["ocr"]["status"] == "ready"
    assert payload["checks"]["ocr"]["mode"] == "mock"
    assert payload["checks"]["vision"]["status"] == "ready"
    assert payload["checks"]["vision"]["mode"] == "mock"


def test_readiness_endpoint_reports_degraded_for_trial_with_mock_or_unset_dependencies(client, monkeypatch) -> None:
    monkeypatch.setenv("APP_RUNTIME_MODE", "trial")
    monkeypatch.setenv("OBJECT_STORAGE_PROVIDER", "mock")
    monkeypatch.setenv("ASR_PROVIDER", "mock")
    monkeypatch.delenv("OCR_PROVIDER", raising=False)
    monkeypatch.delenv("VISION_PROVIDER", raising=False)

    response = client.get("/api/v1/system/readiness", headers=_auth_headers(client, monkeypatch))

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["overall_status"] == "degraded"
    assert payload["runtime_mode"] == "trial"
    assert payload["checks"]["object_storage"]["status"] == "degraded"
    assert payload["checks"]["object_storage"]["mode"] == "mock"
    assert payload["checks"]["asr"]["status"] == "degraded"
    assert payload["checks"]["asr"]["mode"] == "mock"
    assert payload["checks"]["ocr"]["status"] == "degraded"
    assert payload["checks"]["ocr"]["mode"] == "unset"
    assert payload["checks"]["vision"]["status"] == "degraded"
    assert payload["checks"]["vision"]["mode"] == "unset"
