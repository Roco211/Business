import pytest

from conftest import auth_headers, login_and_get_token


@pytest.fixture
def seeded_shop(db_session):
    from app.services.bootstrap import ensure_default_context

    return ensure_default_context(db_session).shop


@pytest.fixture
def uploaded_receipt_media(db_session, seeded_shop):
    from app.models import MediaUpload
    from app.services.media_uploads import create_media_upload, mark_media_upload_complete

    create_result = create_media_upload(
        db_session,
        shop_id=seeded_shop.shop_id,
        uploader_actor_type="owner",
        uploader_actor_id="owner_default",
        media_type="receipt-image",
        file_name="receipt-demo.jpg",
        content_type="image/jpeg",
        size_bytes=2048,
    )
    mark_media_upload_complete(
        db_session,
        media_id=create_result.media_id,
        checksum_sha256="receipt_demo_checksum",
        size_bytes=2048,
    )
    record = db_session.get(MediaUpload, create_result.media_id)
    assert record is not None
    return record


def _auth_headers(client, monkeypatch=None) -> dict[str, str]:
    return auth_headers(login_and_get_token(client, monkeypatch))


def _create_uploaded_receipt_media(client) -> str:
    create_response = client.post(
        "/api/v1/media-uploads",
        headers=_auth_headers(client),
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
        headers=_auth_headers(client),
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
        headers=_auth_headers(client),
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
        headers=_auth_headers(client),
    )

    assert detail_response.status_code == 200
    detail_payload = detail_response.json()["data"]
    assert detail_payload["ocr_document_id"] == create_payload["ocr_document_id"]
    assert detail_payload["status"] == "completed"
    assert len(detail_payload["fields"]["items"]) > 0
    assert "total_amount" in detail_payload["fields"]
    assert isinstance(detail_payload["low_confidence_fields"], list)


def test_create_ocr_document_uses_gateway_result(db_session, seeded_shop, uploaded_receipt_media, monkeypatch) -> None:
    from app.services.ocr_types import OcrExtractedLineItem, OcrExtraction
    from app.services import ocr_documents

    class StubGateway:
        def extract_purchase_receipt(self, media_input):
            assert media_input.media_id == uploaded_receipt_media.media_id
            return OcrExtraction(
                document_type="purchase-receipt",
                provider_name="stub-ocr",
                raw_text="demo receipt",
                line_items=[OcrExtractedLineItem("Red Bull 250ml", 3, "can", 41.0)],
                total_amount=123.0,
                low_confidence_fields=["items[0].price"],
                used_fallback=False,
                raw_payload={"provider": "stub"},
            )

    monkeypatch.setattr(ocr_documents, "get_default_ocr_gateway", lambda: StubGateway())

    result = ocr_documents.create_ocr_document(
        db_session,
        shop_id=seeded_shop.shop_id,
        media_id=uploaded_receipt_media.media_id,
        document_type="purchase-receipt",
        task_run_id=None,
    )

    assert result.ocr_document.provider_name == "stub-ocr"
    assert result.ocr_document.low_confidence_fields == ["items[0].price"]
