from app.models import MediaUpload


AUTH_HEADERS = {"Authorization": "Bearer mock_owner_token"}


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
        headers=AUTH_HEADERS,
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
    assert payload["upload_url"].endswith(payload["media_id"])
    assert payload["public_url"].endswith(payload["media_id"])


def test_complete_media_upload_marks_record_uploaded(client) -> None:
    create_response = client.post(
        "/api/v1/media-uploads",
        headers=AUTH_HEADERS,
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
        headers=AUTH_HEADERS,
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
        headers=AUTH_HEADERS,
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
        headers=AUTH_HEADERS,
        json={
            "checksum_sha256": "abc123",
            "size_bytes": 1024,
        },
    )

    complete_again = client.post(
        f"/api/v1/media-uploads/{media_id}/complete",
        headers=AUTH_HEADERS,
        json={
            "checksum_sha256": "abc123",
            "size_bytes": 1024,
        },
    )

    assert complete_again.status_code == 409
    assert complete_again.json()["error"]["code"] == "media_upload_conflict"
