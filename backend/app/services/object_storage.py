from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Protocol

from app.core.config import Settings, get_settings

MOCK_PROVIDER = "mock"
S3_COMPATIBLE_PROVIDER = "s3-compatible"
DEFAULT_MOCK_UPLOAD_BASE_URL = "https://mock.example/uploads"
DEFAULT_MOCK_PUBLIC_BASE_URL = "https://mock.example/media"


class ObjectStorageConfigurationError(ValueError):
    pass


class ObjectStorageVerificationError(ValueError):
    pass


class ObjectStorageObjectNotFoundError(ObjectStorageVerificationError):
    def __init__(self, object_key: str) -> None:
        self.object_key = object_key
        super().__init__(f"object not found: {object_key}")


@dataclass(frozen=True)
class ObjectStorageUploadTarget:
    object_key: str
    upload_url: str
    public_url: str


@dataclass(frozen=True)
class ObjectStorageObjectMetadata:
    object_key: str
    size_bytes: int | None
    checksum_sha256: str | None = None
    etag: str | None = None


class ObjectStorageProvider(Protocol):
    def create_upload_target(
        self,
        *,
        object_key: str,
        content_type: str,
        size_bytes: int,
    ) -> ObjectStorageUploadTarget:
        ...

    def verify_uploaded_object(
        self,
        *,
        object_key: str,
        expected_size_bytes: int | None = None,
        expected_checksum_sha256: str | None = None,
    ) -> ObjectStorageObjectMetadata:
        ...


def _join_url(base_url: str, object_key: str) -> str:
    return f"{base_url.rstrip('/')}/{object_key}"


def _normalize_file_name(file_name: str) -> str:
    normalized = file_name.strip().replace("\\", "_").replace("/", "_").replace(" ", "_")
    while "__" in normalized:
        normalized = normalized.replace("__", "_")
    return normalized or "file"


def derive_media_object_key(*, shop_id: str, media_id: str, file_name: str) -> str:
    return f"shops/{shop_id}/media/{media_id}/{_normalize_file_name(file_name)}"


class MockObjectStorageProvider:
    def __init__(
        self,
        *,
        upload_base_url: str = DEFAULT_MOCK_UPLOAD_BASE_URL,
        public_base_url: str = DEFAULT_MOCK_PUBLIC_BASE_URL,
    ) -> None:
        self.upload_base_url = upload_base_url
        self.public_base_url = public_base_url

    def create_upload_target(
        self,
        *,
        object_key: str,
        content_type: str,
        size_bytes: int,
    ) -> ObjectStorageUploadTarget:
        del content_type, size_bytes
        return ObjectStorageUploadTarget(
            object_key=object_key,
            upload_url=_join_url(self.upload_base_url, object_key),
            public_url=_join_url(self.public_base_url, object_key),
        )

    def verify_uploaded_object(
        self,
        *,
        object_key: str,
        expected_size_bytes: int | None = None,
        expected_checksum_sha256: str | None = None,
    ) -> ObjectStorageObjectMetadata:
        return ObjectStorageObjectMetadata(
            object_key=object_key,
            size_bytes=expected_size_bytes,
            checksum_sha256=expected_checksum_sha256,
        )


class S3CompatibleObjectStorageProvider:
    def __init__(
        self,
        *,
        bucket: str,
        region: str,
        endpoint_url: str,
        access_key: str,
        secret_key: str,
        public_base_url: str | None,
        presign_ttl_seconds: int,
        s3_client: Any | None = None,
    ) -> None:
        self.bucket = bucket
        self.region = region
        self.endpoint_url = endpoint_url
        self.access_key = access_key
        self.secret_key = secret_key
        self.public_base_url = public_base_url
        self.presign_ttl_seconds = presign_ttl_seconds
        self._s3_client = s3_client

    def _get_client(self) -> Any:
        if self._s3_client is not None:
            return self._s3_client
        try:
            import boto3
        except ModuleNotFoundError as exc:  # pragma: no cover - environment-dependent
            raise ObjectStorageConfigurationError(
                "boto3 is required for s3-compatible object storage"
            ) from exc
        self._s3_client = boto3.client(
            "s3",
            region_name=self.region,
            endpoint_url=self.endpoint_url,
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
        )
        return self._s3_client

    def _public_url_for(self, object_key: str) -> str:
        if self.public_base_url:
            return _join_url(self.public_base_url, object_key)
        endpoint = self.endpoint_url.rstrip("/")
        return f"{endpoint}/{self.bucket}/{object_key}"

    def create_upload_target(
        self,
        *,
        object_key: str,
        content_type: str,
        size_bytes: int,
    ) -> ObjectStorageUploadTarget:
        del size_bytes
        upload_url = self._get_client().generate_presigned_url(
            "put_object",
            Params={
                "Bucket": self.bucket,
                "Key": object_key,
                "ContentType": content_type,
            },
            ExpiresIn=self.presign_ttl_seconds,
            HttpMethod="PUT",
        )
        return ObjectStorageUploadTarget(
            object_key=object_key,
            upload_url=upload_url,
            public_url=self._public_url_for(object_key),
        )

    def verify_uploaded_object(
        self,
        *,
        object_key: str,
        expected_size_bytes: int | None = None,
        expected_checksum_sha256: str | None = None,
    ) -> ObjectStorageObjectMetadata:
        try:
            head = self._get_client().head_object(Bucket=self.bucket, Key=object_key)
        except Exception as exc:
            error_code = _extract_s3_error_code(exc)
            if error_code in {"404", "NoSuchKey", "NotFound"}:
                raise ObjectStorageObjectNotFoundError(object_key) from exc
            raise ObjectStorageVerificationError(f"failed to verify uploaded object: {object_key}") from exc

        size_bytes = int(head.get("ContentLength", 0))
        if expected_size_bytes is not None and size_bytes != expected_size_bytes:
            raise ObjectStorageVerificationError(
                f"object size mismatch for {object_key}: expected {expected_size_bytes}, got {size_bytes}"
            )

        checksum_sha256 = head.get("ChecksumSHA256")
        del expected_checksum_sha256

        etag = head.get("ETag")
        if isinstance(etag, str):
            etag = etag.strip('"')

        return ObjectStorageObjectMetadata(
            object_key=object_key,
            size_bytes=size_bytes,
            checksum_sha256=checksum_sha256,
            etag=etag if isinstance(etag, str) else None,
        )


def _missing_required_s3_config(settings: Settings) -> list[str]:
    return [
        field_name
        for field_name, field_value in settings.object_storage_live_required_config().items()
        if not field_value.strip()
    ]


def _extract_s3_error_code(exc: Exception) -> str:
    response = getattr(exc, "response", None)
    if not isinstance(response, dict):
        return ""
    error = response.get("Error")
    if not isinstance(error, dict):
        return ""
    code = error.get("Code")
    return code if isinstance(code, str) else ""


def build_object_storage(settings: Settings) -> ObjectStorageProvider:
    provider_name = settings.normalized_object_storage_provider()

    if provider_name == MOCK_PROVIDER:
        return MockObjectStorageProvider()

    if provider_name != S3_COMPATIBLE_PROVIDER:
        raise ObjectStorageConfigurationError(
            f"unsupported object storage provider: {settings.object_storage_provider}"
        )

    missing_fields = _missing_required_s3_config(settings)
    if missing_fields:
        missing = ",".join(missing_fields)
        raise ObjectStorageConfigurationError(
            f"missing required object storage configuration: {missing}"
        )

    return S3CompatibleObjectStorageProvider(
        bucket=settings.object_storage_bucket or "",
        region=settings.object_storage_region or "",
        endpoint_url=settings.object_storage_endpoint_url or "",
        access_key=settings.object_storage_access_key or "",
        secret_key=settings.object_storage_secret_key or "",
        public_base_url=settings.object_storage_public_base_url,
        presign_ttl_seconds=settings.object_storage_presign_ttl_seconds,
    )


@lru_cache(maxsize=1)
def get_default_object_storage() -> ObjectStorageProvider:
    return build_object_storage(get_settings())
