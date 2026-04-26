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
    monkeypatch.setenv("TRIAL_PROVIDER_PROFILE", "pilot-v1")
    monkeypatch.setenv("ASR_PROVIDER_LABEL", "asr-primary")
    monkeypatch.setenv("OCR_PROVIDER_LABEL", "ocr-primary")
    monkeypatch.setenv("VISION_PROVIDER_LABEL", "vision-primary")
    monkeypatch.setenv("TRIAL_CALIBRATION_DATASET_DIR", "/tmp/trial/calibration-dataset")
    monkeypatch.setenv("TRIAL_CALIBRATION_ARTIFACTS_DIR", "/tmp/trial/calibration-artifacts")
    monkeypatch.setenv("LIVE_PILOT_ALLOWED_SHOP_IDS", "shop_default")
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
    assert payload["trial_provider_profile"] == "pilot-v1"
    assert payload["checks"]["object_storage"]["status"] == "ready"
    assert payload["checks"]["object_storage"]["mode"] == "s3-compatible"
    assert payload["checks"]["asr"]["status"] == "ready"
    assert payload["checks"]["asr"]["mode"] == "real-provider"
    assert payload["checks"]["asr"]["details"]["provider_label"] == "asr-primary"
    assert payload["checks"]["ocr"]["status"] == "ready"
    assert payload["checks"]["ocr"]["mode"] == "real-provider"
    assert payload["checks"]["ocr"]["details"]["provider_label"] == "ocr-primary"
    assert payload["checks"]["vision"]["status"] == "ready"
    assert payload["checks"]["vision"]["mode"] == "real-provider"
    assert payload["checks"]["vision"]["details"]["provider_label"] == "vision-primary"
    assert payload["checks"]["trial_profile"]["status"] == "ready"
    assert payload["checks"]["trial_profile"]["details"]["calibration_dataset_dir_configured"] == "true"
    assert payload["checks"]["trial_profile"]["details"]["calibration_artifacts_dir_configured"] == "true"


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


def test_readiness_endpoint_reports_degraded_for_trial_when_profile_metadata_is_missing(client, monkeypatch) -> None:
    monkeypatch.setenv("APP_RUNTIME_MODE", "trial")
    monkeypatch.delenv("TRIAL_PROVIDER_PROFILE", raising=False)
    monkeypatch.delenv("ASR_PROVIDER_LABEL", raising=False)
    monkeypatch.delenv("OCR_PROVIDER_LABEL", raising=False)
    monkeypatch.delenv("VISION_PROVIDER_LABEL", raising=False)
    monkeypatch.delenv("TRIAL_CALIBRATION_DATASET_DIR", raising=False)
    monkeypatch.delenv("TRIAL_CALIBRATION_ARTIFACTS_DIR", raising=False)
    monkeypatch.delenv("LIVE_PILOT_ALLOWED_SHOP_IDS", raising=False)
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
    assert payload["overall_status"] == "degraded"
    assert payload["runtime_mode"] == "trial"
    assert payload["trial_provider_profile"] == ""
    assert payload["checks"]["trial_profile"]["status"] == "degraded"
    assert payload["checks"]["trial_profile"]["details"]["reason"] == "missing_config"
    assert payload["checks"]["trial_profile"]["details"]["missing_fields"] == (
        "trial_provider_profile,asr_provider_label,ocr_provider_label,vision_provider_label,"
        "trial_calibration_dataset_dir,trial_calibration_artifacts_dir,allowed_live_pilot_shop_ids"
    )


def test_readiness_endpoint_surfaces_current_pilot_control_contract_fields(client, monkeypatch) -> None:
    monkeypatch.setenv("TRIAL_PROVIDER_PROFILE", "pilot-v1")

    response = client.get("/api/v1/system/readiness", headers=_auth_headers(client, monkeypatch))

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["trial_provider_profile"] == "pilot-v1"
    assert payload["approved_calibration_artifact_id"] is None
    assert payload["cutover_mode"] == "closed"


def test_readiness_and_pilot_control_preserve_stored_profile_when_trial_profile_env_changes(
    client,
    monkeypatch,
) -> None:
    monkeypatch.setenv("TRIAL_PROVIDER_PROFILE", "pilot-v1")
    headers = _auth_headers(client, monkeypatch)

    first_pilot_control = client.get("/api/v1/system/pilot-control", headers=headers)
    assert first_pilot_control.status_code == 200
    assert first_pilot_control.json()["data"]["trial_provider_profile"] == "pilot-v1"

    monkeypatch.setenv("TRIAL_PROVIDER_PROFILE", "pilot-v2")

    readiness_response = client.get("/api/v1/system/readiness", headers=headers)
    assert readiness_response.status_code == 200
    readiness_payload = readiness_response.json()["data"]
    assert readiness_payload["trial_provider_profile"] == "pilot-v1"
    assert readiness_payload["checks"]["trial_profile"]["details"]["trial_provider_profile"] == "pilot-v2"

    second_pilot_control = client.get("/api/v1/system/pilot-control", headers=headers)
    assert second_pilot_control.status_code == 200
    assert second_pilot_control.json()["data"]["trial_provider_profile"] == "pilot-v1"

def test_readiness_endpoint_degrades_production_when_database_is_sqlite(client, monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("APP_RUNTIME_MODE", "local-demo")
    monkeypatch.setenv("DATABASE_URL", "sqlite:////tmp/business-prod.db")
    monkeypatch.setenv("APP_CORS_ORIGINS", "https://business.example.com")
    monkeypatch.setenv("APP_SECURITY_HEADERS_ENABLED", "1")
    monkeypatch.setenv("APP_RATE_LIMIT_PER_MINUTE", "120")

    response = client.get("/api/v1/system/readiness", headers=_auth_headers(client, monkeypatch))

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["overall_status"] == "degraded"
    assert payload["checks"]["production_database"]["status"] == "degraded"
    assert payload["checks"]["production_database"]["mode"] == "sqlite"
    assert payload["checks"]["production_database"]["details"]["reason"] == "unsupported_production_database"
    assert "business-prod.db" not in str(payload["checks"]["production_database"]["details"])


def test_readiness_endpoint_reports_ready_for_production_postgres_and_safe_config(client, monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("APP_RUNTIME_MODE", "local-demo")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://business:secret@postgres:5432/business")
    monkeypatch.setenv("APP_CORS_ORIGINS", "https://business.example.com,https://admin.business.example.com")
    monkeypatch.setenv("APP_SECURITY_HEADERS_ENABLED", "1")
    monkeypatch.setenv("APP_RATE_LIMIT_PER_MINUTE", "120")

    response = client.get("/api/v1/system/readiness", headers=_auth_headers(client, monkeypatch))

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["overall_status"] == "ready"
    assert payload["checks"]["production_database"]["status"] == "ready"
    assert payload["checks"]["production_database"]["mode"] == "postgresql"
    assert payload["checks"]["production_database"]["details"]["database_url_configured"] == "true"
    assert "secret" not in str(payload["checks"]["production_database"]["details"])
    assert payload["checks"]["production_config"]["status"] == "ready"
    assert payload["checks"]["production_config"]["details"]["cors_origin_count"] == "2"
    assert payload["checks"]["production_config"]["details"]["security_headers_enabled"] == "true"
    assert payload["checks"]["production_config"]["details"]["rate_limit_per_minute"] == "120"
