AUTH_HEADERS = {"Authorization": "Bearer mock_owner_token"}


def _create_uploaded_receipt_media(client) -> str:
    create_response = client.post(
        "/api/v1/media-uploads",
        headers=AUTH_HEADERS,
        json={
            "media_type": "receipt-image",
            "file_name": "receipt-demo.jpg",
            "content_type": "image/jpeg",
            "size_bytes": 2048,
        },
    )
    assert create_response.status_code == 201
    media_id = create_response.json()["data"]["media_id"]

    complete_response = client.post(
        f"/api/v1/media-uploads/{media_id}/complete",
        headers=AUTH_HEADERS,
        json={
            "checksum_sha256": "receipt_demo_checksum",
            "size_bytes": 2048,
        },
    )
    assert complete_response.status_code == 200
    return media_id


def test_post_and_get_ocr_document_returns_completed_mock_result(client) -> None:
    media_id = _create_uploaded_receipt_media(client)

    create_response = client.post(
        "/api/v1/ocr-documents",
        headers=AUTH_HEADERS,
        json={
            "media_id": media_id,
            "document_type": "purchase-receipt",
        },
    )

    assert create_response.status_code == 201
    create_payload = create_response.json()["data"]
    assert create_payload["ocr_document_id"].startswith("ocr_")
    assert create_payload["status"] == "processing"

    detail_response = client.get(
        f"/api/v1/ocr-documents/{create_payload['ocr_document_id']}",
        headers=AUTH_HEADERS,
    )

    assert detail_response.status_code == 200
    detail_payload = detail_response.json()["data"]
    assert detail_payload["ocr_document_id"] == create_payload["ocr_document_id"]
    assert detail_payload["status"] == "completed"
    assert len(detail_payload["fields"]["items"]) > 0
    assert "total_amount" in detail_payload["fields"]
    assert isinstance(detail_payload["low_confidence_fields"], list)
