from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.ids import new_prefixed_id
from app.models import MediaUpload
from app.services.object_storage import (
    ObjectStorageObjectNotFoundError,
    ObjectStorageProvider,
    ObjectStorageUnavailableError,
    ObjectStorageVerificationError,
    derive_media_object_key,
    get_default_object_storage,
)

PENDING_STATUS = "pending"
UPLOADED_STATUS = "uploaded"
FAILED_STATUS = "failed"
SUPPORTED_MEDIA_TYPES = {"audio", "image", "receipt-image"}
MAX_MEDIA_URL_LENGTH = 255
STORAGE_UPLOAD_REFERENCE_PREFIX = "storage-ref://"


class MediaUploadConflictError(ValueError):
    pass


class MediaUploadNotReadyError(ValueError):
    pass


class MediaUploadValidationError(ValueError):
    pass


class MediaUploadStorageUnavailableError(ValueError):
    pass


@dataclass(frozen=True)
class MediaUploadCreateResult:
    media_id: str
    upload_url: str
    public_url: str


@dataclass(frozen=True)
class MediaUploadCompleteResult:
    media_id: str
    status: str


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def create_media_upload(
    db_session: Session,
    *,
    shop_id: str,
    uploader_actor_type: str,
    uploader_actor_id: str,
    media_type: str,
    file_name: str,
    content_type: str,
    size_bytes: int,
    object_storage: ObjectStorageProvider | None = None,
) -> MediaUploadCreateResult:
    if media_type not in SUPPORTED_MEDIA_TYPES:
        raise MediaUploadValidationError("Unsupported media_type")
    if not file_name.strip():
        raise MediaUploadValidationError("file_name is required")
    if not content_type.strip():
        raise MediaUploadValidationError("content_type is required")
    if size_bytes <= 0:
        raise MediaUploadValidationError("size_bytes must be greater than 0")

    now = _now()
    media_id = new_prefixed_id("media")
    object_key = derive_media_object_key(
        shop_id=shop_id,
        media_id=media_id,
        file_name=file_name,
    )
    try:
        upload_target = _resolve_object_storage(object_storage).create_upload_target(
            object_key=object_key,
            content_type=content_type.strip(),
            size_bytes=size_bytes,
        )
    except ObjectStorageUnavailableError as exc:
        raise MediaUploadStorageUnavailableError("Object storage is unavailable") from exc

    persisted_upload_url = _build_bounded_upload_reference(object_key)
    persisted_public_url = _build_bounded_public_url(upload_target.public_url, object_key=object_key)
    upload = MediaUpload(
        media_id=media_id,
        shop_id=shop_id,
        uploader_actor_type=uploader_actor_type,
        uploader_actor_id=uploader_actor_id,
        media_type=media_type,
        file_name=file_name.strip(),
        content_type=content_type.strip(),
        size_bytes=size_bytes,
        status=PENDING_STATUS,
        upload_url=persisted_upload_url,
        public_url=persisted_public_url,
        checksum_sha256=None,
        uploaded_at=None,
        created_at=now,
        updated_at=now,
    )
    db_session.add(upload)
    db_session.commit()
    return MediaUploadCreateResult(
        media_id=upload.media_id,
        upload_url=upload_target.upload_url,
        public_url=upload_target.public_url,
    )


def mark_media_upload_complete(
    db_session: Session,
    *,
    media_id: str,
    checksum_sha256: str,
    size_bytes: int,
    object_storage: ObjectStorageProvider | None = None,
) -> MediaUploadCompleteResult:
    media_upload = db_session.get(MediaUpload, media_id)
    if media_upload is None:
        raise LookupError(media_id)
    if media_upload.status != PENDING_STATUS:
        raise MediaUploadConflictError(media_id)
    if size_bytes <= 0:
        raise MediaUploadValidationError("size_bytes must be greater than 0")
    if not checksum_sha256.strip():
        raise MediaUploadValidationError("checksum_sha256 is required")

    object_key = derive_media_object_key(
        shop_id=media_upload.shop_id,
        media_id=media_upload.media_id,
        file_name=media_upload.file_name,
    )
    try:
        _resolve_object_storage(object_storage).verify_uploaded_object(
            object_key=object_key,
            expected_size_bytes=size_bytes,
        )
    except ObjectStorageObjectNotFoundError as exc:
        raise MediaUploadNotReadyError(media_id) from exc
    except ObjectStorageUnavailableError as exc:
        raise MediaUploadStorageUnavailableError("Object storage is unavailable") from exc
    except ObjectStorageVerificationError as exc:
        raise MediaUploadConflictError(media_id) from exc

    now = _now()
    media_upload.status = UPLOADED_STATUS
    media_upload.size_bytes = size_bytes
    media_upload.checksum_sha256 = checksum_sha256.strip()
    media_upload.uploaded_at = now
    media_upload.updated_at = now
    db_session.commit()
    return MediaUploadCompleteResult(media_id=media_upload.media_id, status=media_upload.status)


def ensure_media_uploads_ready(
    db_session: Session,
    *,
    shop_id: str,
    media_ids: list[str],
) -> None:
    if not media_ids:
        return

    unique_ids = list(dict.fromkeys(media_ids))
    records = db_session.scalars(
        select(MediaUpload).where(MediaUpload.media_id.in_(unique_ids))
    ).all()
    records_by_id = {record.media_id: record for record in records}

    for media_id in unique_ids:
        record = records_by_id.get(media_id)
        if record is None:
            raise MediaUploadNotReadyError(media_id)
        if record.shop_id != shop_id:
            raise MediaUploadNotReadyError(media_id)
        if record.status != UPLOADED_STATUS:
            raise MediaUploadNotReadyError(media_id)


def _resolve_object_storage(
    object_storage: ObjectStorageProvider | None,
) -> ObjectStorageProvider:
    if object_storage is not None:
        return object_storage
    return get_default_object_storage()


def _build_bounded_upload_reference(object_key: str) -> str:
    reference = f"{STORAGE_UPLOAD_REFERENCE_PREFIX}{object_key}"
    if len(reference) > MAX_MEDIA_URL_LENGTH:
        raise MediaUploadStorageUnavailableError("Object storage key is too long to persist")
    return reference


def _build_bounded_public_url(public_url: str, *, object_key: str) -> str:
    if len(public_url) <= MAX_MEDIA_URL_LENGTH:
        return public_url

    del object_key
    raise MediaUploadStorageUnavailableError("Object storage public URL is too long to persist")


def get_ready_media_upload(
    db_session: Session,
    *,
    shop_id: str,
    media_id: str,
    expected_media_types: set[str] | None = None,
) -> MediaUpload:
    record = db_session.get(MediaUpload, media_id)
    if record is None:
        raise MediaUploadNotReadyError(media_id)
    if record.shop_id != shop_id or record.status != UPLOADED_STATUS:
        raise MediaUploadNotReadyError(media_id)
    if expected_media_types is not None and record.media_type not in expected_media_types:
        raise MediaUploadNotReadyError(media_id)
    return record
