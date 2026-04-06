from conftest import auth_headers, login_and_get_token
from app.services import media_uploads as media_uploads_service
from app.services.object_storage import (
    ObjectStorageConfigurationError,
    ObjectStorageObjectNotFoundError,
    ObjectStorageUploadTarget,
    ObjectStorageUnavailableError,
    ObjectStorageVerificationError,
)

def _auth_headers(client, monkeypatch=None) -> dict[str, str]:
    return auth_headers(login_and_get_token(client, monkeypatch))


class _FailingVerificationStorage:
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
            upload_url=f"https://upload.example/{object_key}",
            public_url=f"https://public.example/{object_key}",
        )

    def verify_uploaded_object(
        self,
        *,
        object_key: str,
        expected_size_bytes: int | None = None,
    ) -> dict[str, object]:
        del expected_size_bytes
        raise ObjectStorageObjectNotFoundError(object_key)


class _SizeMismatchVerificationStorage:
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
            upload_url=f"https://upload.example/{object_key}",
            public_url=f"https://public.example/{object_key}",
        )

    def verify_uploaded_object(
        self,
        *,
        object_key: str,
        expected_size_bytes: int | None = None,
    ) -> dict[str, object]:
        del object_key, expected_size_bytes
        raise ObjectStorageVerificationError("object size mismatch")


class _UnavailableCreateStorage:
    def create_upload_target(
        self,
        *,
        object_key: str,
        content_type: str,
        size_bytes: int,
    ) -> ObjectStorageUploadTarget:
        del object_key, content_type, size_bytes
        raise ObjectStorageUnavailableError("storage backend unavailable")

    def verify_uploaded_object(
        self,
        *,
        object_key: str,
        expected_size_bytes: int | None = None,
    ) -> dict[str, object]:
        del object_key, expected_size_bytes
        raise ObjectStorageUnavailableError("storage backend unavailable")


class _UnavailableVerifyStorage:
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
            upload_url=f"https://upload.example/{object_key}",
            public_url=f"https://public.example/{object_key}",
        )

    def verify_uploaded_object(
        self,
        *,
        object_key: str,
        expected_size_bytes: int | None = None,
    ) -> dict[str, object]:
        del object_key, expected_size_bytes
        raise ObjectStorageUnavailableError("storage backend unavailable")


def test_create_media_upload_requires_authorization(client) -> None:
    response = client.post(
        "/api/v1/media-uploads",
        json={
          "media_type": "audio",
          "file_name": "voice.m4a",
          "content_type": "audio/m4a",
          "size_bytes": 1024,
        },
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


def test_create_media_upload_returns_pending_upload_contract(client) -> None:
    response = client.post(
        "/api/v1/media-uploads",
        headers=_auth_headers(client),
        json={
            "media_type": "audio",
            "file_name": "voice.m4a",
            "content_type": "audio/m4a",
            "size_bytes": 1024,
        },
    )

    assert response.status_code == 201
    payload = response.json()["data"]
    assert payload["media_id"].startswith("media_")
    assert payload["media_id"] in payload["upload_url"]
    assert payload["media_id"] in payload["public_url"]


def test_complete_media_upload_marks_record_uploaded(client) -> None:
    create_response = client.post(
        "/api/v1/media-uploads",
        headers=_auth_headers(client),
        json={
            "media_type": "audio",
            "file_name": "voice.m4a",
            "content_type": "audio/m4a",
            "size_bytes": 1024,
        },
    )
    media_id = create_response.json()["data"]["media_id"]

    complete_response = client.post(
        f"/api/v1/media-uploads/{media_id}/complete",
        headers=_auth_headers(client),
        json={
            "checksum_sha256": "abc123",
            "size_bytes": 1024,
        },
    )

    assert complete_response.status_code == 200
    assert complete_response.json()["data"] == {
        "media_id": media_id,
        "status": "uploaded",
    }


def test_complete_media_upload_rejects_already_uploaded_record(client) -> None:
    create_response = client.post(
        "/api/v1/media-uploads",
        headers=_auth_headers(client),
        json={
            "media_type": "audio",
            "file_name": "voice.m4a",
            "content_type": "audio/m4a",
            "size_bytes": 1024,
        },
    )
    media_id = create_response.json()["data"]["media_id"]
    client.post(
        f"/api/v1/media-uploads/{media_id}/complete",
        headers=_auth_headers(client),
        json={
            "checksum_sha256": "abc123",
            "size_bytes": 1024,
        },
    )

    complete_again = client.post(
        f"/api/v1/media-uploads/{media_id}/complete",
        headers=_auth_headers(client),
        json={
            "checksum_sha256": "abc123",
            "size_bytes": 1024,
        },
    )

    assert complete_again.status_code == 409
    assert complete_again.json()["error"]["code"] == "media_upload_conflict"


def test_complete_media_upload_returns_conflict_when_object_is_missing(client, monkeypatch) -> None:
    monkeypatch.setattr(
        media_uploads_service,
        "get_default_object_storage",
        lambda: _FailingVerificationStorage(),
    )
    create_response = client.post(
        "/api/v1/media-uploads",
        headers=_auth_headers(client),
        json={
            "media_type": "audio",
            "file_name": "voice.m4a",
            "content_type": "audio/m4a",
            "size_bytes": 1024,
        },
    )
    media_id = create_response.json()["data"]["media_id"]

    complete_response = client.post(
        f"/api/v1/media-uploads/{media_id}/complete",
        headers=_auth_headers(client),
        json={
            "checksum_sha256": "abc123",
            "size_bytes": 1024,
        },
    )

    assert complete_response.status_code == 409
    assert complete_response.json()["error"]["code"] == "media_upload_conflict"


def test_complete_media_upload_returns_conflict_when_object_size_mismatches(client, monkeypatch) -> None:
    monkeypatch.setattr(
        media_uploads_service,
        "get_default_object_storage",
        lambda: _SizeMismatchVerificationStorage(),
    )
    create_response = client.post(
        "/api/v1/media-uploads",
        headers=_auth_headers(client),
        json={
            "media_type": "audio",
            "file_name": "voice.m4a",
            "content_type": "audio/m4a",
            "size_bytes": 1024,
        },
    )
    media_id = create_response.json()["data"]["media_id"]

    complete_response = client.post(
        f"/api/v1/media-uploads/{media_id}/complete",
        headers=_auth_headers(client),
        json={
            "checksum_sha256": "abc123",
            "size_bytes": 1024,
        },
    )

    assert complete_response.status_code == 409
    assert complete_response.json()["error"]["code"] == "media_upload_conflict"


def test_create_media_upload_returns_503_when_storage_is_unavailable(client, monkeypatch) -> None:
    monkeypatch.setattr(
        media_uploads_service,
        "get_default_object_storage",
        lambda: _UnavailableCreateStorage(),
    )

    response = client.post(
        "/api/v1/media-uploads",
        headers=_auth_headers(client),
        json={
            "media_type": "audio",
            "file_name": "voice.m4a",
            "content_type": "audio/m4a",
            "size_bytes": 1024,
        },
    )

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "storage_unavailable"


def test_create_media_upload_returns_503_when_storage_is_misconfigured(client, monkeypatch) -> None:
    def _raise_misconfigured() -> object:
        raise ObjectStorageConfigurationError("missing required object storage configuration: bucket")

    monkeypatch.setattr(
        media_uploads_service,
        "get_default_object_storage",
        _raise_misconfigured,
    )

    response = client.post(
        "/api/v1/media-uploads",
        headers=_auth_headers(client),
        json={
            "media_type": "audio",
            "file_name": "voice.m4a",
            "content_type": "audio/m4a",
            "size_bytes": 1024,
        },
    )

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "storage_unavailable"


def test_complete_media_upload_returns_503_when_storage_is_unavailable(client, monkeypatch) -> None:
    monkeypatch.setattr(
        media_uploads_service,
        "get_default_object_storage",
        lambda: _UnavailableVerifyStorage(),
    )
    create_response = client.post(
        "/api/v1/media-uploads",
        headers=_auth_headers(client),
        json={
            "media_type": "audio",
            "file_name": "voice.m4a",
            "content_type": "audio/m4a",
            "size_bytes": 1024,
        },
    )
    media_id = create_response.json()["data"]["media_id"]

    complete_response = client.post(
        f"/api/v1/media-uploads/{media_id}/complete",
        headers=_auth_headers(client),
        json={
            "checksum_sha256": "abc123",
            "size_bytes": 1024,
        },
    )

    assert complete_response.status_code == 503
    assert complete_response.json()["error"]["code"] == "storage_unavailable"
