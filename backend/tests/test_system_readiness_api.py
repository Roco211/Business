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


def test_readiness_endpoint_reports_degraded_for_trial_with_unsupported_live_providers(client, monkeypatch) -> None:
    monkeypatch.setenv("APP_RUNTIME_MODE", "trial")
    monkeypatch.setenv("OBJECT_STORAGE_PROVIDER", "typo-storage")
    monkeypatch.setenv("ASR_PROVIDER", "typo-asr")
    monkeypatch.setenv("OCR_PROVIDER", "typo-ocr")
    monkeypatch.setenv("VISION_PROVIDER", "typo-vision")

    response = client.get("/api/v1/system/readiness", headers=_auth_headers(client, monkeypatch))

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["overall_status"] == "degraded"
    assert payload["checks"]["object_storage"]["status"] == "degraded"
    assert payload["checks"]["object_storage"]["mode"] == "typo-storage"
    assert payload["checks"]["object_storage"]["details"]["reason"] == "unsupported_provider"
    assert payload["checks"]["asr"]["status"] == "degraded"
    assert payload["checks"]["asr"]["mode"] == "typo-asr"
    assert payload["checks"]["ocr"]["status"] == "degraded"
    assert payload["checks"]["ocr"]["mode"] == "typo-ocr"
    assert payload["checks"]["vision"]["status"] == "degraded"
    assert payload["checks"]["vision"]["mode"] == "typo-vision"


def test_readiness_endpoint_reports_degraded_for_trial_when_live_provider_config_is_missing(client, monkeypatch) -> None:
    monkeypatch.setenv("APP_RUNTIME_MODE", "trial")
    monkeypatch.setenv("OBJECT_STORAGE_PROVIDER", "s3-compatible")
    monkeypatch.delenv("OBJECT_STORAGE_BUCKET", raising=False)
    monkeypatch.delenv("OBJECT_STORAGE_REGION", raising=False)
    monkeypatch.delenv("OBJECT_STORAGE_ENDPOINT_URL", raising=False)
    monkeypatch.delenv("OBJECT_STORAGE_ACCESS_KEY", raising=False)
    monkeypatch.delenv("OBJECT_STORAGE_SECRET_KEY", raising=False)
    monkeypatch.setenv("ASR_PROVIDER", "real-provider")
    monkeypatch.delenv("ASR_PROVIDER_API_URL", raising=False)
    monkeypatch.delenv("ASR_PROVIDER_API_KEY", raising=False)
    monkeypatch.delenv("ASR_PROVIDER_MODEL", raising=False)
    monkeypatch.setenv("OCR_PROVIDER", "real-provider")
    monkeypatch.delenv("OCR_PROVIDER_API_URL", raising=False)
    monkeypatch.delenv("OCR_PROVIDER_API_KEY", raising=False)
    monkeypatch.delenv("OCR_PROVIDER_MODEL", raising=False)
    monkeypatch.setenv("VISION_PROVIDER", "real-provider")
    monkeypatch.delenv("VISION_PROVIDER_API_URL", raising=False)
    monkeypatch.delenv("VISION_PROVIDER_API_KEY", raising=False)
    monkeypatch.delenv("VISION_PROVIDER_MODEL", raising=False)

    response = client.get("/api/v1/system/readiness", headers=_auth_headers(client, monkeypatch))

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["overall_status"] == "degraded"
    assert payload["checks"]["object_storage"]["status"] == "degraded"
    assert payload["checks"]["object_storage"]["mode"] == "s3-compatible"
    assert payload["checks"]["object_storage"]["details"]["reason"] == "missing_config"
    assert payload["checks"]["asr"]["status"] == "degraded"
    assert payload["checks"]["asr"]["mode"] == "real-provider"
    assert payload["checks"]["ocr"]["status"] == "degraded"
    assert payload["checks"]["ocr"]["mode"] == "real-provider"
    assert payload["checks"]["vision"]["status"] == "degraded"
    assert payload["checks"]["vision"]["mode"] == "real-provider"


def test_readiness_endpoint_reports_ready_for_trial_with_valid_live_config(client, monkeypatch) -> None:
    monkeypatch.setenv("APP_RUNTIME_MODE", "trial")
    monkeypatch.setenv("OBJECT_STORAGE_PROVIDER", "s3-compatible")
    monkeypatch.setenv("OBJECT_STORAGE_BUCKET", "trial-bucket")
    monkeypatch.setenv("OBJECT_STORAGE_REGION", "ap-southeast-1")
    monkeypatch.setenv("OBJECT_STORAGE_ENDPOINT_URL", "https://s3.example.com")
    monkeypatch.setenv("OBJECT_STORAGE_ACCESS_KEY", "access")
    monkeypatch.setenv("OBJECT_STORAGE_SECRET_KEY", "secret")
    monkeypatch.setenv("ASR_PROVIDER", "real-provider")
    monkeypatch.setenv("ASR_PROVIDER_API_URL", "https://asr.example.com/v1")
    monkeypatch.setenv("ASR_PROVIDER_API_KEY", "asr-key")
    monkeypatch.setenv("ASR_PROVIDER_MODEL", "asr-model")
    monkeypatch.setenv("ASR_ALLOW_MOCK_FALLBACK", "0")
    monkeypatch.setenv("OCR_PROVIDER", "real-provider")
    monkeypatch.setenv("OCR_PROVIDER_API_URL", "https://ocr.example.com/v1")
    monkeypatch.setenv("OCR_PROVIDER_API_KEY", "ocr-key")
    monkeypatch.setenv("OCR_PROVIDER_MODEL", "ocr-model")
    monkeypatch.setenv("OCR_ALLOW_MOCK_FALLBACK", "0")
    monkeypatch.setenv("VISION_PROVIDER", "real-provider")
    monkeypatch.setenv("VISION_PROVIDER_API_URL", "https://vision.example.com/v1")
    monkeypatch.setenv("VISION_PROVIDER_API_KEY", "vision-key")
    monkeypatch.setenv("VISION_PROVIDER_MODEL", "vision-model")
    monkeypatch.setenv("VISION_ALLOW_MOCK_FALLBACK", "0")

    response = client.get("/api/v1/system/readiness", headers=_auth_headers(client, monkeypatch))

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["overall_status"] == "ready"
    assert payload["runtime_mode"] == "trial"
    assert payload["checks"]["object_storage"]["status"] == "ready"
    assert payload["checks"]["object_storage"]["mode"] == "s3-compatible"
    assert payload["checks"]["asr"]["status"] == "ready"
    assert payload["checks"]["asr"]["mode"] == "real-provider"
    assert payload["checks"]["ocr"]["status"] == "ready"
    assert payload["checks"]["ocr"]["mode"] == "real-provider"
    assert payload["checks"]["vision"]["status"] == "ready"
    assert payload["checks"]["vision"]["mode"] == "real-provider"


def test_readiness_endpoint_reports_degraded_for_trial_when_live_provider_allows_mock_fallback(
    client,
    monkeypatch,
) -> None:
    monkeypatch.setenv("APP_RUNTIME_MODE", "trial")
    monkeypatch.setenv("OBJECT_STORAGE_PROVIDER", "s3-compatible")
    monkeypatch.setenv("OBJECT_STORAGE_BUCKET", "trial-bucket")
    monkeypatch.setenv("OBJECT_STORAGE_REGION", "ap-southeast-1")
    monkeypatch.setenv("OBJECT_STORAGE_ENDPOINT_URL", "https://s3.example.com")
    monkeypatch.setenv("OBJECT_STORAGE_ACCESS_KEY", "access")
    monkeypatch.setenv("OBJECT_STORAGE_SECRET_KEY", "secret")
    monkeypatch.setenv("ASR_PROVIDER", "real-provider")
    monkeypatch.setenv("ASR_PROVIDER_API_URL", "https://asr.example.com/v1")
    monkeypatch.setenv("ASR_PROVIDER_API_KEY", "asr-key")
    monkeypatch.setenv("ASR_PROVIDER_MODEL", "asr-model")
    monkeypatch.setenv("ASR_ALLOW_MOCK_FALLBACK", "1")
    monkeypatch.setenv("OCR_PROVIDER", "real-provider")
    monkeypatch.setenv("OCR_PROVIDER_API_URL", "https://ocr.example.com/v1")
    monkeypatch.setenv("OCR_PROVIDER_API_KEY", "ocr-key")
    monkeypatch.setenv("OCR_PROVIDER_MODEL", "ocr-model")
    monkeypatch.setenv("OCR_ALLOW_MOCK_FALLBACK", "1")
    monkeypatch.setenv("VISION_PROVIDER", "real-provider")
    monkeypatch.setenv("VISION_PROVIDER_API_URL", "https://vision.example.com/v1")
    monkeypatch.setenv("VISION_PROVIDER_API_KEY", "vision-key")
    monkeypatch.setenv("VISION_PROVIDER_MODEL", "vision-model")
    monkeypatch.setenv("VISION_ALLOW_MOCK_FALLBACK", "1")

    response = client.get("/api/v1/system/readiness", headers=_auth_headers(client, monkeypatch))

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["overall_status"] == "degraded"
    assert payload["runtime_mode"] == "trial"
    assert payload["checks"]["object_storage"]["status"] == "ready"
    assert payload["checks"]["asr"]["status"] == "degraded"
    assert payload["checks"]["asr"]["details"]["allow_mock_fallback"] == "true"
    assert payload["checks"]["asr"]["details"]["reason"] == "trial_guardrail"
    assert payload["checks"]["ocr"]["status"] == "degraded"
    assert payload["checks"]["ocr"]["details"]["allow_mock_fallback"] == "true"
    assert payload["checks"]["ocr"]["details"]["reason"] == "trial_guardrail"
    assert payload["checks"]["vision"]["status"] == "degraded"
    assert payload["checks"]["vision"]["details"]["allow_mock_fallback"] == "true"
    assert payload["checks"]["vision"]["details"]["reason"] == "trial_guardrail"
