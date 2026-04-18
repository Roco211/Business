from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.ids import new_prefixed_id
from app.models import V2ContextSession, V2MediaAsset
from app.services.object_storage import (
    ObjectStorageObjectNotFoundError,
    ObjectStorageProvider,
    ObjectStorageUnavailableError,
    ObjectStorageVerificationError,
    get_default_object_storage,
)
from app.services.v2_time import utc_now_naive

PENDING_MEDIA_ASSET_STATUS = "pending"
UPLOADED_MEDIA_ASSET_STATUS = "uploaded"
FAILED_MEDIA_ASSET_STATUS = "failed"
SUPPORTED_V2_MEDIA_TYPES = {"audio", "image", "receipt-image", "document"}
MAX_MEDIA_URL_LENGTH = 255
STORAGE_UPLOAD_REFERENCE_PREFIX = "storage-ref://"


class V2MediaAssetConflictError(ValueError):
    pass


class V2MediaAssetNotReadyError(ValueError):
    pass


class V2MediaAssetValidationError(ValueError):
    pass


class V2MediaAssetStorageUnavailableError(ValueError):
    pass


@dataclass(frozen=True)
class V2MediaAssetCreateResult:
    media_asset_id: str
    status: str
    upload_url: str
    public_url: str


@dataclass(frozen=True)
class V2MediaAssetCompleteResult:
    media_asset_id: str
    status: str


def derive_v2_media_object_key(*, tenant_id: str, shop_id: str, media_asset_id: str, file_name: str) -> str:
    safe_tenant_id = _sanitize_path_segment(tenant_id, fallback="tenant")
    safe_shop_id = _sanitize_path_segment(shop_id, fallback="shop")
    safe_media_asset_id = _sanitize_path_segment(media_asset_id, fallback="media")
    safe_file_name = _normalize_file_name(file_name)
    return f"tenants/{safe_tenant_id}/shops/{safe_shop_id}/media/{safe_media_asset_id}/{safe_file_name}"


def create_v2_media_asset_upload(
    db_session: Session,
    *,
    tenant_id: str,
    shop_id: str,
    context_session_id: str,
    uploaded_by_account_id: str,
    media_type: str,
    file_name: str,
    content_type: str,
    size_bytes: int,
    object_storage: ObjectStorageProvider | None = None,
) -> V2MediaAssetCreateResult:
    normalized_media_type = media_type.strip().lower()
    normalized_file_name = file_name.strip()
    normalized_content_type = content_type.strip()
    if normalized_media_type not in SUPPORTED_V2_MEDIA_TYPES:
        raise V2MediaAssetValidationError("Unsupported media_type")
    if not normalized_file_name:
        raise V2MediaAssetValidationError("file_name is required")
    if not normalized_content_type:
        raise V2MediaAssetValidationError("content_type is required")
    if size_bytes <= 0:
        raise V2MediaAssetValidationError("size_bytes must be greater than 0")
    _require_v2_context(
        db_session,
        tenant_id=tenant_id,
        shop_id=shop_id,
        context_session_id=context_session_id,
        account_id=uploaded_by_account_id,
    )

    now = utc_now_naive()
    media_asset_id = new_prefixed_id("vmedia")
    object_key = derive_v2_media_object_key(
        tenant_id=tenant_id,
        shop_id=shop_id,
        media_asset_id=media_asset_id,
        file_name=normalized_file_name,
    )
    storage_provider = _resolve_object_storage(object_storage)
    try:
        upload_target = storage_provider.create_upload_target(
            object_key=object_key,
            content_type=normalized_content_type,
            size_bytes=size_bytes,
        )
    except ObjectStorageUnavailableError as exc:
        raise V2MediaAssetStorageUnavailableError("Object storage is unavailable") from exc

    asset = V2MediaAsset(
        media_asset_id=media_asset_id,
        tenant_id=tenant_id,
        shop_id=shop_id,
        context_session_id=context_session_id,
        uploaded_by_account_id=uploaded_by_account_id,
        media_type=normalized_media_type,
        file_name=normalized_file_name,
        content_type=normalized_content_type,
        size_bytes=size_bytes,
        storage_provider=get_settings().normalized_object_storage_provider(),
        object_key=object_key,
        upload_url=_build_bounded_upload_reference(object_key),
        public_url=_build_bounded_public_url(upload_target.public_url),
        status=PENDING_MEDIA_ASSET_STATUS,
        checksum_sha256=None,
        metadata_json={},
        uploaded_at=None,
        created_at=now,
        updated_at=now,
    )
    db_session.add(asset)
    db_session.commit()
    return V2MediaAssetCreateResult(
        media_asset_id=asset.media_asset_id,
        status=asset.status,
        upload_url=upload_target.upload_url,
        public_url=upload_target.public_url,
    )


def mark_v2_media_asset_uploaded(
    db_session: Session,
    *,
    tenant_id: str,
    shop_id: str,
    media_asset_id: str,
    checksum_sha256: str,
    size_bytes: int,
    object_storage: ObjectStorageProvider | None = None,
) -> V2MediaAssetCompleteResult:
    asset = _require_v2_media_asset_for_context(
        db_session,
        tenant_id=tenant_id,
        shop_id=shop_id,
        media_asset_id=media_asset_id,
    )
    if asset.status != PENDING_MEDIA_ASSET_STATUS:
        raise V2MediaAssetConflictError(media_asset_id)
    normalized_checksum_sha256 = checksum_sha256.strip().lower()
    if not normalized_checksum_sha256:
        raise V2MediaAssetValidationError("checksum_sha256 is required")
    if size_bytes <= 0:
        raise V2MediaAssetValidationError("size_bytes must be greater than 0")

    try:
        _resolve_object_storage(object_storage).verify_uploaded_object(
            object_key=asset.object_key,
            expected_size_bytes=size_bytes,
            expected_checksum_sha256=normalized_checksum_sha256,
        )
    except ObjectStorageObjectNotFoundError as exc:
        raise V2MediaAssetNotReadyError(media_asset_id) from exc
    except ObjectStorageUnavailableError as exc:
        raise V2MediaAssetStorageUnavailableError("Object storage is unavailable") from exc
    except ObjectStorageVerificationError as exc:
        raise V2MediaAssetConflictError(media_asset_id) from exc

    now = utc_now_naive()
    asset.status = UPLOADED_MEDIA_ASSET_STATUS
    asset.size_bytes = size_bytes
    asset.checksum_sha256 = normalized_checksum_sha256
    asset.uploaded_at = now
    asset.updated_at = now
    db_session.commit()
    return V2MediaAssetCompleteResult(media_asset_id=asset.media_asset_id, status=asset.status)


def get_ready_v2_media_asset(
    db_session: Session,
    *,
    tenant_id: str,
    shop_id: str,
    media_asset_id: str,
    expected_media_types: set[str] | None = None,
) -> V2MediaAsset:
    asset = _require_v2_media_asset_for_context(
        db_session,
        tenant_id=tenant_id,
        shop_id=shop_id,
        media_asset_id=media_asset_id,
    )
    if asset.status != UPLOADED_MEDIA_ASSET_STATUS:
        raise V2MediaAssetNotReadyError(media_asset_id)
    if expected_media_types is not None and asset.media_type not in expected_media_types:
        raise V2MediaAssetNotReadyError(media_asset_id)
    return asset


def _require_v2_context(
    db_session: Session,
    *,
    tenant_id: str,
    shop_id: str,
    context_session_id: str,
    account_id: str,
) -> None:
    context_session = db_session.scalar(
        select(V2ContextSession).where(
            V2ContextSession.context_session_id == context_session_id,
            V2ContextSession.tenant_id == tenant_id,
            V2ContextSession.shop_id == shop_id,
            V2ContextSession.account_id == account_id,
            V2ContextSession.status == "active",
        )
    )
    if context_session is None:
        raise LookupError(context_session_id)


def _require_v2_media_asset_for_context(
    db_session: Session,
    *,
    tenant_id: str,
    shop_id: str,
    media_asset_id: str,
) -> V2MediaAsset:
    asset = db_session.scalar(
        select(V2MediaAsset).where(
            V2MediaAsset.media_asset_id == media_asset_id,
            V2MediaAsset.tenant_id == tenant_id,
            V2MediaAsset.shop_id == shop_id,
        )
    )
    if asset is None:
        raise LookupError(media_asset_id)
    return asset


def _resolve_object_storage(object_storage: ObjectStorageProvider | None) -> ObjectStorageProvider:
    if object_storage is not None:
        return object_storage
    return get_default_object_storage()


def _build_bounded_upload_reference(object_key: str) -> str:
    reference = f"{STORAGE_UPLOAD_REFERENCE_PREFIX}{object_key}"
    if len(reference) > MAX_MEDIA_URL_LENGTH:
        raise V2MediaAssetStorageUnavailableError("Object storage key is too long to persist")
    return reference


def _build_bounded_public_url(public_url: str) -> str:
    if len(public_url) > MAX_MEDIA_URL_LENGTH:
        raise V2MediaAssetStorageUnavailableError("Object storage public URL is too long to persist")
    return public_url


def _sanitize_path_segment(value: str, *, fallback: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in ("-", "_") else "-" for ch in value.strip().lower())
    normalized = cleaned.strip("-")
    return normalized or fallback


def _normalize_file_name(file_name: str) -> str:
    normalized = "".join(ch if ch.isalnum() or ch in (".", "-", "_") else "_" for ch in file_name.strip())
    normalized = normalized.strip("._")
    return normalized or "asset.bin"
