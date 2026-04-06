from sqlalchemy import select
import pytest

from app.models import MediaUpload
from app.services.bootstrap import ensure_default_context
from app.services.media_uploads import (
    MediaUploadConflictError,
    MediaUploadNotReadyError,
    create_media_upload,
    ensure_media_uploads_ready,
    mark_media_upload_complete,
)
from app.services.object_storage import (
    ObjectStorageObjectNotFoundError,
    ObjectStorageUploadTarget,
    ObjectStorageVerificationError,
    derive_media_object_key,
)


class _StubObjectStorage:
    def __init__(self) -> None:
        self.create_calls: list[tuple[str, str, int]] = []
        self.verify_calls: list[tuple[str, int | None]] = []
        self.fail_verification = False
        self.object_size_bytes = 1024

    def create_upload_target(
        self,
        *,
        object_key: str,
        content_type: str,
        size_bytes: int,
    ) -> ObjectStorageUploadTarget:
        self.create_calls.append((object_key, content_type, size_bytes))
        return ObjectStorageUploadTarget(
            object_key=object_key,
            upload_url=f"https://upload.example/{object_key}",
            public_url=f"https://public.example/{object_key}",
        )

    def verify_uploaded_object(
        self,
        *,
        object_key: str,
        expected_size_bytes: int | None = None,
    ) -> dict[str, object]:
        self.verify_calls.append((object_key, expected_size_bytes))
        if self.fail_verification:
            raise ObjectStorageObjectNotFoundError(object_key)
        if expected_size_bytes is not None and expected_size_bytes != self.object_size_bytes:
            raise ObjectStorageVerificationError("object size mismatch")
        return {"object_key": object_key, "size_bytes": expected_size_bytes}


def test_create_media_upload_persists_pending_record(db_session) -> None:
    context = ensure_default_context(db_session)
    storage = _StubObjectStorage()

    result = create_media_upload(
        db_session,
        shop_id=context.shop.shop_id,
        uploader_actor_type="owner",
        uploader_actor_id="owner_default",
        media_type="audio",
        file_name="voice.m4a",
        content_type="audio/m4a",
        size_bytes=1024,
        object_storage=storage,
    )

    media_upload = db_session.get(MediaUpload, result.media_id)
    expected_key = derive_media_object_key(
        shop_id=context.shop.shop_id,
        media_id=result.media_id,
        file_name="voice.m4a",
    )

    assert media_upload is not None
    assert media_upload.shop_id == context.shop.shop_id
    assert media_upload.media_type == "audio"
    assert media_upload.status == "pending"
    assert media_upload.file_name == "voice.m4a"
    assert media_upload.content_type == "audio/m4a"
    assert media_upload.size_bytes == 1024
    assert media_upload.uploaded_at is None
    assert result.upload_url == f"https://upload.example/{expected_key}"
    assert result.public_url == f"https://public.example/{expected_key}"
    assert storage.create_calls == [(expected_key, "audio/m4a", 1024)]


def test_mark_media_upload_complete_sets_uploaded_fields(db_session) -> None:
    context = ensure_default_context(db_session)
    storage = _StubObjectStorage()
    created = create_media_upload(
        db_session,
        shop_id=context.shop.shop_id,
        uploader_actor_type="owner",
        uploader_actor_id="owner_default",
        media_type="audio",
        file_name="voice.m4a",
        content_type="audio/m4a",
        size_bytes=1024,
        object_storage=storage,
    )
    expected_key = derive_media_object_key(
        shop_id=context.shop.shop_id,
        media_id=created.media_id,
        file_name="voice.m4a",
    )

    result = mark_media_upload_complete(
        db_session,
        media_id=created.media_id,
        checksum_sha256="abc123",
        size_bytes=1024,
        object_storage=storage,
    )
    media_upload = db_session.get(MediaUpload, created.media_id)

    assert result.media_id == created.media_id
    assert result.status == "uploaded"
    assert media_upload is not None
    assert media_upload.status == "uploaded"
    assert media_upload.checksum_sha256 == "abc123"
    assert media_upload.uploaded_at is not None
    assert storage.verify_calls == [(expected_key, 1024)]


def test_mark_media_upload_complete_rejects_when_uploaded_object_is_missing(db_session) -> None:
    context = ensure_default_context(db_session)
    storage = _StubObjectStorage()
    created = create_media_upload(
        db_session,
        shop_id=context.shop.shop_id,
        uploader_actor_type="owner",
        uploader_actor_id="owner_default",
        media_type="audio",
        file_name="voice.m4a",
        content_type="audio/m4a",
        size_bytes=1024,
        object_storage=storage,
    )
    storage.fail_verification = True

    with pytest.raises(MediaUploadNotReadyError):
        mark_media_upload_complete(
            db_session,
            media_id=created.media_id,
            checksum_sha256="abc123",
            size_bytes=1024,
            object_storage=storage,
        )

    media_upload = db_session.get(MediaUpload, created.media_id)
    assert media_upload is not None
    assert media_upload.status == "pending"
    assert media_upload.uploaded_at is None


def test_mark_media_upload_complete_rejects_when_uploaded_object_size_mismatches(db_session) -> None:
    context = ensure_default_context(db_session)
    storage = _StubObjectStorage()
    created = create_media_upload(
        db_session,
        shop_id=context.shop.shop_id,
        uploader_actor_type="owner",
        uploader_actor_id="owner_default",
        media_type="audio",
        file_name="voice.m4a",
        content_type="audio/m4a",
        size_bytes=1024,
        object_storage=storage,
    )
    storage.object_size_bytes = 4096

    with pytest.raises(MediaUploadConflictError):
        mark_media_upload_complete(
            db_session,
            media_id=created.media_id,
            checksum_sha256="abc123",
            size_bytes=1024,
            object_storage=storage,
        )

    media_upload = db_session.get(MediaUpload, created.media_id)
    assert media_upload is not None
    assert media_upload.status == "pending"
    assert media_upload.uploaded_at is None


def test_mark_media_upload_complete_rejects_already_uploaded_record(db_session) -> None:
    context = ensure_default_context(db_session)
    storage = _StubObjectStorage()
    created = create_media_upload(
        db_session,
        shop_id=context.shop.shop_id,
        uploader_actor_type="owner",
        uploader_actor_id="owner_default",
        media_type="audio",
        file_name="voice.m4a",
        content_type="audio/m4a",
        size_bytes=1024,
        object_storage=storage,
    )
    mark_media_upload_complete(
        db_session,
        media_id=created.media_id,
        checksum_sha256="abc123",
        size_bytes=1024,
        object_storage=storage,
    )

    with pytest.raises(MediaUploadConflictError):
        mark_media_upload_complete(
            db_session,
            media_id=created.media_id,
            checksum_sha256="abc123",
            size_bytes=1024,
            object_storage=storage,
        )


def test_ensure_media_uploads_ready_requires_uploaded_status_for_all_media_ids(db_session) -> None:
    context = ensure_default_context(db_session)
    storage = _StubObjectStorage()
    created = create_media_upload(
        db_session,
        shop_id=context.shop.shop_id,
        uploader_actor_type="owner",
        uploader_actor_id="owner_default",
        media_type="audio",
        file_name="voice.m4a",
        content_type="audio/m4a",
        size_bytes=1024,
        object_storage=storage,
    )

    with pytest.raises(MediaUploadNotReadyError):
        ensure_media_uploads_ready(
            db_session,
            shop_id=context.shop.shop_id,
            media_ids=[created.media_id],
        )

    mark_media_upload_complete(
        db_session,
        media_id=created.media_id,
        checksum_sha256="abc123",
        size_bytes=1024,
        object_storage=storage,
    )

    ensure_media_uploads_ready(
        db_session,
        shop_id=context.shop.shop_id,
        media_ids=[created.media_id],
    )


def test_ensure_media_uploads_ready_rejects_missing_or_foreign_shop_media(db_session) -> None:
    context = ensure_default_context(db_session)
    foreign = MediaUpload(
        media_id="media_foreign_shop",
        shop_id="shop_foreign",
        uploader_actor_type="owner",
        uploader_actor_id="owner_other",
        media_type="audio",
        file_name="voice.m4a",
        content_type="audio/m4a",
        size_bytes=1024,
        status="uploaded",
        upload_url="https://mock.example/uploads/media_foreign_shop",
        public_url="https://mock.example/media/media_foreign_shop",
        checksum_sha256="abc123",
        uploaded_at=context.shop.created_at,
        created_at=context.shop.created_at,
        updated_at=context.shop.created_at,
    )
    db_session.add(foreign)
    db_session.commit()

    with pytest.raises(MediaUploadNotReadyError):
        ensure_media_uploads_ready(
            db_session,
            shop_id=context.shop.shop_id,
            media_ids=["media_missing"],
        )

    with pytest.raises(MediaUploadNotReadyError):
        ensure_media_uploads_ready(
            db_session,
            shop_id=context.shop.shop_id,
            media_ids=[foreign.media_id],
        )

    persisted = db_session.scalars(select(MediaUpload).where(MediaUpload.media_id == foreign.media_id)).one()
    assert persisted.shop_id == "shop_foreign"
