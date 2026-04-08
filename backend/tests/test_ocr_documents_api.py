import hashlib

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
    from app.services.object_storage import MOCK_UPLOAD_URL_PREFIX, MockObjectStorageProvider, get_default_object_storage

    upload_bytes = b"receipt-bytes-for-tests"
    checksum_sha256 = hashlib.sha256(upload_bytes).hexdigest()

    create_result = create_media_upload(
        db_session,
        shop_id=seeded_shop.shop_id,
        uploader_actor_type="owner",
        uploader_actor_id="owner_default",
        media_type="receipt-image",
        file_name="receipt-demo.jpg",
        content_type="image/jpeg",
        size_bytes=len(upload_bytes),
    )
    object_storage = get_default_object_storage()
    if isinstance(object_storage, MockObjectStorageProvider) and create_result.upload_url.startswith(MOCK_UPLOAD_URL_PREFIX):
        object_storage.store_uploaded_object(
            object_key=create_result.upload_url[len(MOCK_UPLOAD_URL_PREFIX) :],
            payload=upload_bytes,
        )

    mark_media_upload_complete(
        db_session,
        media_id=create_result.media_id,
        checksum_sha256=checksum_sha256,
        size_bytes=len(upload_bytes),
    )
    record = db_session.get(MediaUpload, create_result.media_id)
    assert record is not None
    return record


def _auth_headers(client, monkeypatch=None) -> dict[str, str]:
    return auth_headers(login_and_get_token(client, monkeypatch))


def _create_uploaded_receipt_media(client) -> str:
    upload_bytes = b"receipt-bytes-for-tests"
    checksum_sha256 = hashlib.sha256(upload_bytes).hexdigest()
    create_response = client.post(
        "/api/v1/media-uploads",
        headers=_auth_headers(client),
        json={
            "media_type": "receipt-image",
            "file_name": "receipt-demo.jpg",
            "content_type": "image/jpeg",
            "size_bytes": len(upload_bytes),
        },
    )
    assert create_response.status_code == 201
    upload_url = create_response.json()["data"]["upload_url"]
    media_id = create_response.json()["data"]["media_id"]
    upload_response = client.put(
        upload_url,
        content=upload_bytes,
        headers={"Content-Type": "image/jpeg"},
    )
    assert upload_response.status_code == 200

    complete_response = client.post(
        f"/api/v1/media-uploads/{media_id}/complete",
        headers=_auth_headers(client),
        json={
            "checksum_sha256": checksum_sha256,
            "size_bytes": len(upload_bytes),
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
    extracted_fields = result.ocr_document.extracted_fields
    assert isinstance(extracted_fields, dict)
    assert extracted_fields["items"][0]["name"] == "Red Bull 250ml"
    assert extracted_fields["total_amount"] == 123.0


def test_post_create_ocr_document_returns_structured_503_for_ocr_provider_error(client, monkeypatch) -> None:
    from app.services import ocr_documents as ocr_documents_service
    from app.services.ocr_types import OcrProviderError

    class StubGateway:
        def extract_purchase_receipt(self, _media_input):
            raise OcrProviderError(
                "ocr_unavailable",
                "OCR provider is not configured",
                retryable=False,
            )

    monkeypatch.setattr(ocr_documents_service, "get_default_ocr_gateway", lambda: StubGateway())

    media_id = _create_uploaded_receipt_media(client)
    response = client.post(
        "/api/v1/ocr-documents",
        headers=_auth_headers(client),
        json={
            "media_id": media_id,
            "document_type": "purchase-receipt",
        },
    )

    assert response.status_code == 503
    payload = response.json()["error"]
    assert payload["code"] == "ocr_unavailable"
    assert payload["message"] == "OCR provider is not configured"
