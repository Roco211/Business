from dataclasses import dataclass
from functools import lru_cache
import hashlib
import re
from typing import Any, Protocol

from app.core.config import Settings, get_settings

MOCK_PROVIDER = "mock"
S3_COMPATIBLE_PROVIDER = "s3-compatible"
MOCK_UPLOAD_URL_PREFIX = "mock-upload://"
DEFAULT_MOCK_PUBLIC_BASE_URL = "https://mock.example/media"
MAX_OBJECT_KEY_LENGTH = 180
MAX_FILENAME_SEGMENT_LENGTH = 96
MAX_ID_SEGMENT_LENGTH = 40
_SAFE_SEGMENT_PATTERN = re.compile(r"[^a-zA-Z0-9._-]+")
_SAFE_FILENAME_PATTERN = re.compile(r"[^a-z0-9]+")


class ObjectStorageError(ValueError):
    pass


class ObjectStorageUnavailableError(ObjectStorageError):
    pass


class ObjectStorageConfigurationError(ObjectStorageUnavailableError):
    pass


class ObjectStorageVerificationError(ObjectStorageError):
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
    etag: str | None = None
    checksum_sha256: str | None = None


class ObjectStorageProvider(Protocol):
    def create_upload_target(
        self,
        *,
        object_key: str,
        content_type: str,
        size_bytes: int = 0,
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


def _sanitize_path_segment(value: str, *, fallback: str, max_length: int = MAX_ID_SEGMENT_LENGTH) -> str:
    cleaned = _SAFE_SEGMENT_PATTERN.sub("-", value.strip())
    cleaned = cleaned.strip("-.")
    cleaned = cleaned[:max_length].strip("-.")
    return cleaned or fallback


def _safe_extension(raw_extension: str) -> str:
    extension = raw_extension.lower()
    safe_extension = "".join(character for character in extension if character.isalnum())
    if not safe_extension:
        return ""
    return f".{safe_extension[:8]}"


def _normalize_file_name(file_name: str, *, max_length: int) -> str:
    normalized_name = file_name.strip().replace("\\", "/")
    leaf_name = normalized_name.rsplit("/", maxsplit=1)[-1].strip() or "file"
    stem, has_extension, raw_extension = leaf_name.rpartition(".")
    extension = _safe_extension(raw_extension) if has_extension else ""
    stem = stem if has_extension else leaf_name
    stem = stem or "file"
    stem_slug = _SAFE_FILENAME_PATTERN.sub("-", stem.lower()).strip("-") or "file"
    digest = hashlib.sha256(leaf_name.encode("utf-8")).hexdigest()[:12]

    reserved_char_count = len(extension) + len(digest) + 1
    stem_budget = max(1, min(MAX_FILENAME_SEGMENT_LENGTH, max_length - reserved_char_count))
    stem_prefix = stem_slug[:stem_budget].rstrip("-") or "file"
    candidate = f"{stem_prefix}-{digest}{extension}"

    if len(candidate) <= max_length:
        return candidate

    safe_extension = extension[: max(0, max_length - 1)]
    fallback_budget = max(1, max_length - len(safe_extension))
    return f"{digest[:fallback_budget]}{safe_extension}"[:max_length]


def derive_media_object_key(*, shop_id: str, media_id: str, file_name: str) -> str:
    safe_shop_id = _sanitize_path_segment(shop_id, fallback="shop")
    safe_media_id = _sanitize_path_segment(media_id, fallback="media")
    prefix = f"shops/{safe_shop_id}/media/{safe_media_id}/"
    max_filename_length = max(24, MAX_OBJECT_KEY_LENGTH - len(prefix))
    safe_file_name = _normalize_file_name(file_name, max_length=max_filename_length)
    return f"{prefix}{safe_file_name}"


class MockObjectStorageProvider:
    def __init__(
        self,
        *,
        public_base_url: str = DEFAULT_MOCK_PUBLIC_BASE_URL,
    ) -> None:
        self.public_base_url = public_base_url
        self._objects: dict[str, bytes] = {}

    def create_upload_target(
        self,
        *,
        object_key: str,
        content_type: str,
        size_bytes: int = 0,
    ) -> ObjectStorageUploadTarget:
        del content_type, size_bytes
        return ObjectStorageUploadTarget(
            object_key=object_key,
            upload_url=f"{MOCK_UPLOAD_URL_PREFIX}{object_key}",
            public_url=_join_url(self.public_base_url, object_key),
        )

    def store_uploaded_object(self, *, object_key: str, payload: bytes) -> None:
        self._objects[object_key] = payload

    def verify_uploaded_object(
        self,
        *,
        object_key: str,
        expected_size_bytes: int | None = None,
        expected_checksum_sha256: str | None = None,
    ) -> ObjectStorageObjectMetadata:
        uploaded_bytes = self._objects.get(object_key)
        if uploaded_bytes is None:
            raise ObjectStorageObjectNotFoundError(object_key)

        size_bytes = len(uploaded_bytes)
        if expected_size_bytes is not None and size_bytes != expected_size_bytes:
            raise ObjectStorageVerificationError(
                f"object size mismatch for {object_key}: expected {expected_size_bytes}, got {size_bytes}"
            )

        checksum_sha256 = hashlib.sha256(uploaded_bytes).hexdigest()
        if expected_checksum_sha256 is not None and checksum_sha256 != expected_checksum_sha256.strip().lower():
            raise ObjectStorageVerificationError(f"object checksum mismatch for {object_key}")

        return ObjectStorageObjectMetadata(
            object_key=object_key,
            size_bytes=size_bytes,
            checksum_sha256=checksum_sha256,
        )


class S3CompatibleObjectStorageProvider:
    def __init__(
        self,
        *,
        bucket: str,
        region: str,
        endpoint_url: str,
        access_key: str | None = None,
        secret_key: str | None = None,
        access_key_id: str | None = None,
        secret_access_key: str | None = None,
        public_base_url: str | None,
        presign_ttl_seconds: int,
        s3_client: Any | None = None,
        addressing_style: str = "auto",
    ) -> None:
        self.bucket = bucket
        self.region = region
        self.endpoint_url = endpoint_url
        self.access_key = access_key_id or access_key or ""
        self.secret_key = secret_access_key or secret_key or ""
        self.public_base_url = public_base_url
        self.presign_ttl_seconds = presign_ttl_seconds
        self.addressing_style = addressing_style
        self._s3_client = s3_client

    def _get_client(self) -> Any:
        if self._s3_client is not None:
            return self._s3_client
        try:
            import boto3
            from botocore.config import Config
        except ModuleNotFoundError as exc:  # pragma: no cover - environment-dependent
            raise ObjectStorageConfigurationError(
                "boto3 is required for s3-compatible object storage"
            ) from exc
        try:
            self._s3_client = boto3.client(
                "s3",
                region_name=self.region,
                endpoint_url=self.endpoint_url,
                aws_access_key_id=self.access_key,
                aws_secret_access_key=self.secret_key,
                config=Config(signature_version="s3v4", s3={"addressing_style": self.addressing_style}),
            )
        except Exception as exc:  # pragma: no cover - boto3 transport setup failure
            raise ObjectStorageUnavailableError("failed to initialize s3 object storage client") from exc
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
        size_bytes: int = 0,
    ) -> ObjectStorageUploadTarget:
        del size_bytes
        try:
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
        except Exception as exc:
            raise ObjectStorageUnavailableError("failed to generate upload target") from exc
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
            raise ObjectStorageUnavailableError(f"failed to verify uploaded object: {object_key}") from exc

        size_bytes = int(head.get("ContentLength", 0))
        if expected_size_bytes is not None and size_bytes != expected_size_bytes:
            raise ObjectStorageVerificationError(
                f"object size mismatch for {object_key}: expected {expected_size_bytes}, got {size_bytes}"
            )

        etag = head.get("ETag")
        if isinstance(etag, str):
            etag = etag.strip('"')

        checksum_sha256: str | None = None
        if expected_checksum_sha256 is not None:
            checksum_sha256 = self._sha256_for_object(object_key)
            if checksum_sha256 != expected_checksum_sha256.strip().lower():
                raise ObjectStorageVerificationError(f"object checksum mismatch for {object_key}")

        return ObjectStorageObjectMetadata(
            object_key=object_key,
            size_bytes=size_bytes,
            etag=etag if isinstance(etag, str) else None,
            checksum_sha256=checksum_sha256,
        )

    def read_object_bytes(self, *, object_key: str) -> bytes:
        return self._read_object_bytes(object_key)

    def _sha256_for_object(self, object_key: str) -> str:
        return hashlib.sha256(self._read_object_bytes(object_key)).hexdigest()

    def _read_object_bytes(self, object_key: str) -> bytes:
        try:
            get_object_response = self._get_client().get_object(Bucket=self.bucket, Key=object_key)
        except Exception as exc:
            error_code = _extract_s3_error_code(exc)
            if error_code in {"404", "NoSuchKey", "NotFound"}:
                raise ObjectStorageObjectNotFoundError(object_key) from exc
            raise ObjectStorageUnavailableError(f"failed to fetch uploaded object: {object_key}") from exc

        body_reader = get_object_response.get("Body")
        if not hasattr(body_reader, "read"):
            raise ObjectStorageUnavailableError(f"failed to fetch uploaded object bytes: {object_key}")

        try:
            payload = body_reader.read()
        except Exception as exc:
            raise ObjectStorageUnavailableError(f"failed to read uploaded object bytes: {object_key}") from exc

        if not isinstance(payload, (bytes, bytearray)):
            raise ObjectStorageUnavailableError(f"uploaded object payload was not bytes: {object_key}")

        return bytes(payload)


def _s3_addressing_style(settings: Settings) -> str:
    provider = settings.object_storage_provider.strip().lower()
    endpoint = (settings.object_storage_endpoint_url or "").strip().lower()
    if provider in {"cos", "tencent-cos", "tencent_cos", "qcloud-cos", "qcloud_cos"} or "myqcloud.com" in endpoint:
        return "virtual"
    return "auto"


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
        addressing_style=_s3_addressing_style(settings),
    )


@lru_cache(maxsize=1)
def get_default_object_storage() -> ObjectStorageProvider:
    return build_object_storage(get_settings())
