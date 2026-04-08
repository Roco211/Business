import hashlib

import pytest

from app.core.config import Settings
from app.services.object_storage import (
    DEFAULT_MOCK_PUBLIC_BASE_URL,
    MAX_OBJECT_KEY_LENGTH,
    MockObjectStorageProvider,
    ObjectStorageConfigurationError,
    ObjectStorageObjectNotFoundError,
    ObjectStorageUploadTarget,
    ObjectStorageVerificationError,
    S3CompatibleObjectStorageProvider,
    build_object_storage,
    derive_media_object_key,
)


def _build_settings(**overrides: object) -> Settings:
    values = {
        "app_env": "test",
        "app_host": "127.0.0.1",
        "app_port": 8001,
        "redis_url": "redis://localhost:6379/0",
        "database_url": "sqlite:///tmp.db",
        "session_stream_keepalive_seconds": 20.0,
        "app_runtime_mode": "local-demo",
        "object_storage_provider": "mock",
        "object_storage_bucket": None,
        "object_storage_region": None,
        "object_storage_endpoint_url": None,
        "object_storage_access_key": None,
        "object_storage_secret_key": None,
        "object_storage_public_base_url": None,
        "object_storage_presign_ttl_seconds": 900,
    }
    values.update(overrides)
    return Settings(**values)


def test_build_object_storage_rejects_missing_s3_config_in_trial_mode() -> None:
    settings = _build_settings(
        app_runtime_mode="trial",
        object_storage_provider="s3-compatible",
        object_storage_bucket=None,
        object_storage_region=None,
        object_storage_endpoint_url=None,
        object_storage_access_key=None,
        object_storage_secret_key=None,
    )

    with pytest.raises(ObjectStorageConfigurationError) as excinfo:
        build_object_storage(settings)

    assert str(excinfo.value) == "missing required object storage configuration: bucket,region,endpoint_url,access_key,secret_key"


def test_mock_provider_generates_deterministic_upload_and_public_urls() -> None:
    provider = MockObjectStorageProvider()
    object_key = "shops/shop_default/media/media_001/voice.m4a"

    target = provider.create_upload_target(
        object_key=object_key,
        content_type="audio/m4a",
        size_bytes=1024,
    )

    assert target == ObjectStorageUploadTarget(
        object_key=object_key,
        upload_url="mock-upload://shops/shop_default/media/media_001/voice.m4a",
        public_url=f"{DEFAULT_MOCK_PUBLIC_BASE_URL}/shops/shop_default/media/media_001/voice.m4a",
    )


def test_mock_provider_requires_stored_bytes_for_verification_and_validates_checksum() -> None:
    provider = MockObjectStorageProvider()
    object_key = "shops/shop_default/media/media_001/voice.m4a"
    payload = b"voice media bytes"
    checksum_sha256 = hashlib.sha256(payload).hexdigest()

    with pytest.raises(ObjectStorageObjectNotFoundError):
        provider.verify_uploaded_object(
            object_key=object_key,
            expected_size_bytes=len(payload),
            expected_checksum_sha256=checksum_sha256,
        )

    provider.store_uploaded_object(object_key=object_key, payload=payload)
    metadata = provider.verify_uploaded_object(
        object_key=object_key,
        expected_size_bytes=len(payload),
        expected_checksum_sha256=checksum_sha256,
    )

    assert metadata.object_key == object_key
    assert metadata.size_bytes == len(payload)
    assert metadata.checksum_sha256 == checksum_sha256

    with pytest.raises(ObjectStorageVerificationError):
        provider.verify_uploaded_object(
            object_key=object_key,
            expected_size_bytes=len(payload),
            expected_checksum_sha256=hashlib.sha256(b"other bytes").hexdigest(),
        )


def test_s3_provider_generates_upload_target_using_client() -> None:
    class _FakeS3Client:
        def __init__(self) -> None:
            self.calls: list[tuple[str, dict[str, object], int, str]] = []

        def generate_presigned_url(
            self,
            client_method: str,
            *,
            Params: dict[str, object],
            ExpiresIn: int,
            HttpMethod: str,
        ) -> str:
            self.calls.append((client_method, Params, ExpiresIn, HttpMethod))
            return "https://s3.example.com/upload/presigned"

    client = _FakeS3Client()
    provider = S3CompatibleObjectStorageProvider(
        bucket="trial-bucket",
        region="ap-southeast-1",
        endpoint_url="https://s3.example.com",
        access_key="access",
        secret_key="secret",
        public_base_url="https://cdn.example.com",
        presign_ttl_seconds=1200,
        s3_client=client,
    )

    target = provider.create_upload_target(
        object_key="shops/shop_default/media/media_001/voice.m4a",
        content_type="audio/m4a",
        size_bytes=1024,
    )

    assert target.upload_url == "https://s3.example.com/upload/presigned"
    assert target.public_url == "https://cdn.example.com/shops/shop_default/media/media_001/voice.m4a"
    assert client.calls == [
        (
            "put_object",
            {
                "Bucket": "trial-bucket",
                "Key": "shops/shop_default/media/media_001/voice.m4a",
                "ContentType": "audio/m4a",
            },
            1200,
            "PUT",
        )
    ]


def test_s3_provider_verify_uploaded_object_raises_for_missing_object() -> None:
    class _FakeNotFoundError(Exception):
        def __init__(self) -> None:
            self.response = {"Error": {"Code": "404"}}
            super().__init__("missing")

    class _FakeS3Client:
        def head_object(self, *, Bucket: str, Key: str) -> dict[str, object]:
            del Bucket, Key
            raise _FakeNotFoundError()

    provider = S3CompatibleObjectStorageProvider(
        bucket="trial-bucket",
        region="ap-southeast-1",
        endpoint_url="https://s3.example.com",
        access_key="access",
        secret_key="secret",
        public_base_url="https://cdn.example.com",
        presign_ttl_seconds=1200,
        s3_client=_FakeS3Client(),
    )

    with pytest.raises(ObjectStorageObjectNotFoundError) as excinfo:
        provider.verify_uploaded_object(
            object_key="shops/shop_default/media/media_001/voice.m4a",
            expected_size_bytes=1024,
        )

    assert str(excinfo.value) == "object not found: shops/shop_default/media/media_001/voice.m4a"


def test_s3_provider_verify_uploaded_object_raises_for_size_mismatch() -> None:
    class _FakeS3Client:
        def head_object(self, *, Bucket: str, Key: str) -> dict[str, object]:
            del Bucket, Key
            return {"ContentLength": 2048}

    provider = S3CompatibleObjectStorageProvider(
        bucket="trial-bucket",
        region="ap-southeast-1",
        endpoint_url="https://s3.example.com",
        access_key="access",
        secret_key="secret",
        public_base_url="https://cdn.example.com",
        presign_ttl_seconds=1200,
        s3_client=_FakeS3Client(),
    )

    with pytest.raises(ObjectStorageVerificationError) as excinfo:
        provider.verify_uploaded_object(
            object_key="shops/shop_default/media/media_001/voice.m4a",
            expected_size_bytes=1024,
        )

    assert str(excinfo.value) == (
        "object size mismatch for shops/shop_default/media/media_001/voice.m4a: expected 1024, got 2048"
    )


def test_s3_provider_verify_uploaded_object_raises_for_checksum_mismatch() -> None:
    class _FakeBody:
        def read(self) -> bytes:
            return b"uploaded payload"

    class _FakeS3Client:
        def head_object(self, *, Bucket: str, Key: str) -> dict[str, object]:
            del Bucket, Key
            return {"ContentLength": 16}

        def get_object(self, *, Bucket: str, Key: str) -> dict[str, object]:
            del Bucket, Key
            return {"Body": _FakeBody()}

    provider = S3CompatibleObjectStorageProvider(
        bucket="trial-bucket",
        region="ap-southeast-1",
        endpoint_url="https://s3.example.com",
        access_key="access",
        secret_key="secret",
        public_base_url="https://cdn.example.com",
        presign_ttl_seconds=1200,
        s3_client=_FakeS3Client(),
    )

    with pytest.raises(ObjectStorageVerificationError) as excinfo:
        provider.verify_uploaded_object(
            object_key="shops/shop_default/media/media_001/voice.m4a",
            expected_size_bytes=16,
            expected_checksum_sha256="bad-checksum",
        )

    assert str(excinfo.value) == "object checksum mismatch for shops/shop_default/media/media_001/voice.m4a"


def test_derive_media_object_key_is_deterministic() -> None:
    first = derive_media_object_key(
        shop_id="shop_default",
        media_id="media_001",
        file_name=" receipt\\voice.m4a ",
    )
    second = derive_media_object_key(
        shop_id="shop_default",
        media_id="media_001",
        file_name=" receipt\\voice.m4a ",
    )

    assert first == second
    assert first.startswith("shops/shop_default/media/media_001/")
    assert first.endswith(".m4a")


def test_derive_media_object_key_is_url_safe_and_bounded_for_tricky_filenames() -> None:
    tricky_name = "  #Sales?Report%2026 / final?.very-long-extension-name !!!.jpg  "
    very_long_name = tricky_name * 30

    object_key = derive_media_object_key(
        shop_id="shop_default",
        media_id="media_001",
        file_name=very_long_name,
    )
    target = MockObjectStorageProvider(
        public_base_url="https://mock.example/media",
    ).create_upload_target(
        object_key=object_key,
        content_type="image/jpeg",
        size_bytes=1024,
    )

    assert len(object_key) <= MAX_OBJECT_KEY_LENGTH
    assert "#" not in object_key
    assert "?" not in object_key
    assert " " not in object_key
    assert len(target.public_url) <= 255
