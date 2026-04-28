from app.core.config import Settings


def _settings(**overrides) -> Settings:
    base = {
        "app_env": "development",
        "app_host": "0.0.0.0",
        "app_port": 8001,
        "redis_url": "redis://redis:6379/0",
        "database_url": "sqlite:///./aism-dev.db",
    }
    base.update(overrides)
    return Settings(**base)


def _keys(violations: list[dict[str, str]]) -> set[str]:
    return {violation["key"] for violation in violations}


def test_development_allows_local_demo_mock_defaults():
    settings = _settings(app_env="development", app_runtime_mode="local-demo")

    assert settings.production_mock_violations() == []


def test_production_rejects_mock_object_storage():
    settings = _settings(app_env="production", object_storage_provider="mock")

    assert "OBJECT_STORAGE_PROVIDER" in _keys(settings.production_mock_violations())


def test_production_rejects_local_demo_runtime_mode_and_demo_phone_login():
    settings = _settings(app_env="production", app_runtime_mode="local-demo")

    keys = _keys(settings.production_mock_violations())
    assert "APP_RUNTIME_MODE" in keys
    assert "DEMO_PHONE_LOGIN" in keys


def test_production_rejects_empty_ocr_provider():
    settings = _settings(app_env="production", ocr_provider="", ocr_allow_mock_fallback=False)

    assert "OCR_PROVIDER" in _keys(settings.production_mock_violations())


def test_production_rejects_ocr_mock_fallback():
    settings = _settings(app_env="production", ocr_provider="volcano", ocr_allow_mock_fallback=True)

    assert "OCR_ALLOW_MOCK_FALLBACK" in _keys(settings.production_mock_violations())


def test_production_rejects_vision_mock_fallback():
    settings = _settings(app_env="production", vision_provider="volcano", vision_allow_mock_fallback=True)

    assert "VISION_ALLOW_MOCK_FALLBACK" in _keys(settings.production_mock_violations())


def test_production_rejects_server_asr_mock_fallback():
    settings = _settings(app_env="production", asr_provider="volcano", asr_allow_mock_fallback=True)

    assert "ASR_ALLOW_MOCK_FALLBACK" in _keys(settings.production_mock_violations())


def test_production_accepts_client_asr_real_deepseek_ark_and_s3_config():
    settings = _settings(
        app_env="production",
        app_runtime_mode="production",
        object_storage_provider="s3-compatible",
        object_storage_bucket="business-prod-media",
        object_storage_endpoint_url="https://tos.example.com",
        object_storage_region="cn-beijing",
        object_storage_access_key="configured",
        object_storage_secret_key="configured",
        ocr_provider="volcano",
        ocr_provider_api_url="https://ark.cn-beijing.volces.com/api/v3/chat/completions",
        ocr_provider_api_key="configured",
        ocr_provider_model="doubao-seed-2-0-pro-260215",
        ocr_allow_mock_fallback=False,
        vision_provider="volcano",
        vision_provider_api_url="https://ark.cn-beijing.volces.com/api/v3/chat/completions",
        vision_provider_api_key="configured",
        vision_provider_model="doubao-seed-2-0-pro-260215",
        vision_allow_mock_fallback=False,
        asr_provider="client",
        asr_allow_mock_fallback=False,
        llm_provider="deepseek",
        llm_provider_api_url="https://api.deepseek.com/v1/chat/completions",
        llm_provider_api_key="configured",
        llm_provider_model="deepseek-v4-flash",
        llm_allow_mock_fallback=False,
        sms_provider="volcengine",
        sms_api_url="https://sms.example.com",
        sms_access_key_id="configured",
        sms_secret_access_key="configured",
        sms_sign_name="configured",
        sms_template_id="configured",
    )

    assert settings.production_mock_violations() == []
