from io import BytesIO

import pytest

from app.core.config import Settings
from app.services.object_storage import (
    ObjectStorageConfigurationError,
    S3CompatibleObjectStorageProvider,
    build_object_storage,
)


class FakeS3Client:
    def __init__(self) -> None:
        self.presigned_requests = []
        self.head_requests = []
        self.get_requests = []
        self.objects = {
            "tenants/t1/shops/s1/media/m1/a.jpg": b"image-payload",
        }

    def generate_presigned_url(self, operation_name, Params, ExpiresIn, HttpMethod):
        self.presigned_requests.append((operation_name, Params, ExpiresIn, HttpMethod))
        return f"https://upload.example.test/{Params['Bucket']}/{Params['Key']}?signature=redacted"

    def head_object(self, Bucket, Key):
        self.head_requests.append((Bucket, Key))
        payload = self.objects[Key]
        return {"ContentLength": len(payload), "ETag": '"etag-value"'}

    def get_object(self, Bucket, Key):
        self.get_requests.append((Bucket, Key))
        return {"Body": BytesIO(self.objects[Key])}


def test_production_s3_requires_bucket_endpoint_and_credentials():
    settings = Settings(app_env="production", object_storage_provider="s3-compatible")

    with pytest.raises(ObjectStorageConfigurationError) as exc_info:
        build_object_storage(settings)

    message = str(exc_info.value)
    assert "missing required object storage configuration" in message
    assert "bucket" in message
    assert "endpoint_url" in message
    assert "access_key" in message
    assert "secret_key" in message
    assert "configured" not in message


def test_tencent_cos_provider_alias_uses_s3_compatible_provider():
    settings = Settings(
        app_env="production",
        object_storage_provider="tencent-cos",
        object_storage_bucket="business-prod-1250000000",
        object_storage_region="ap-guangzhou",
        object_storage_endpoint_url="https://cos.ap-guangzhou.myqcloud.com",
        object_storage_access_key="cos-secret-id",
        object_storage_secret_key="cos-secret-key",
        object_storage_public_base_url="https://business-prod-1250000000.cos.ap-guangzhou.myqcloud.com",
    )

    provider = build_object_storage(settings)

    assert isinstance(provider, S3CompatibleObjectStorageProvider)
    assert provider.bucket == "business-prod-1250000000"
    assert provider.region == "ap-guangzhou"
    assert provider.endpoint_url == "https://cos.ap-guangzhou.myqcloud.com"
    assert provider.public_base_url == "https://business-prod-1250000000.cos.ap-guangzhou.myqcloud.com"
    assert provider.addressing_style == "virtual"


def test_settings_reads_tencent_cos_environment_aliases(monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setenv("OBJECT_STORAGE_PROVIDER", "cos")
    monkeypatch.setenv("COS_BUCKET", "business-prod-1250000000")
    monkeypatch.setenv("COS_REGION", "ap-shanghai")
    monkeypatch.setenv("COS_ENDPOINT_URL", "https://cos.ap-shanghai.myqcloud.com")
    monkeypatch.setenv("COS_SECRET_ID", "cos-secret-id")
    monkeypatch.setenv("COS_SECRET_KEY", "cos-secret-key")
    monkeypatch.setenv("COS_PUBLIC_BASE_URL", "https://media.example.com")

    settings = get_settings()

    assert settings.object_storage_provider == "cos"
    assert settings.normalized_object_storage_provider() == "s3-compatible"
    assert settings.object_storage_bucket == "business-prod-1250000000"
    assert settings.object_storage_region == "ap-shanghai"
    assert settings.object_storage_endpoint_url == "https://cos.ap-shanghai.myqcloud.com"
    assert settings.object_storage_access_key == "cos-secret-id"
    assert settings.object_storage_secret_key == "cos-secret-key"
    assert settings.object_storage_public_base_url == "https://media.example.com"


def test_s3_compatible_provider_builds_presigned_upload_target_with_public_url():
    fake_s3_client = FakeS3Client()
    provider = S3CompatibleObjectStorageProvider(
        bucket="business-prod-media",
        endpoint_url="https://tos.example.com",
        region="cn-beijing",
        access_key_id="configured",
        secret_access_key="configured",
        public_base_url="https://cdn.example.com",
        presign_ttl_seconds=600,
        s3_client=fake_s3_client,
    )

    target = provider.create_upload_target(
        object_key="tenants/t1/shops/s1/media/m1/a.jpg",
        content_type="image/jpeg",
    )

    assert target.object_key.endswith("a.jpg")
    assert target.upload_url.startswith("https://upload.example.test/business-prod-media/")
    assert target.public_url == "https://cdn.example.com/tenants/t1/shops/s1/media/m1/a.jpg"
    assert fake_s3_client.presigned_requests == [
        (
            "put_object",
            {
                "Bucket": "business-prod-media",
                "Key": "tenants/t1/shops/s1/media/m1/a.jpg",
                "ContentType": "image/jpeg",
            },
            600,
            "PUT",
        )
    ]


def test_s3_compatible_provider_verifies_and_reads_object_without_leaking_credentials():
    fake_s3_client = FakeS3Client()
    provider = S3CompatibleObjectStorageProvider(
        bucket="business-prod-media",
        endpoint_url="https://tos.example.com",
        region="cn-beijing",
        access_key_id="access-key-should-not-leak",
        secret_access_key="secret-key-should-not-leak",
        public_base_url=None,
        presign_ttl_seconds=600,
        s3_client=fake_s3_client,
    )

    metadata = provider.verify_uploaded_object(
        object_key="tenants/t1/shops/s1/media/m1/a.jpg",
        expected_size_bytes=len(b"image-payload"),
    )
    payload = provider.read_object_bytes(object_key="tenants/t1/shops/s1/media/m1/a.jpg")

    assert metadata.size_bytes == len(b"image-payload")
    assert metadata.etag == "etag-value"
    assert payload == b"image-payload"
    assert fake_s3_client.head_requests == [("business-prod-media", "tenants/t1/shops/s1/media/m1/a.jpg")]
    assert fake_s3_client.get_requests == [("business-prod-media", "tenants/t1/shops/s1/media/m1/a.jpg")]
