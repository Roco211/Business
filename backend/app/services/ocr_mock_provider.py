from app.services.ocr_types import OcrExtractedLineItem, OcrExtraction, OcrMediaInput


_MOCK_RECEIPT_FIXTURES = {
    "receipt_demo": {
        "document_type": "purchase-receipt",
        "provider_name": "mock-ocr-provider",
        "raw_text": "Red Bull 250ml x 3 @ 41.0; Coca Cola 500ml x 2 @ 12.0",
        "items": [
            {"name": "Red Bull 250ml", "quantity": 3.0, "unit": "can", "price": 41.0},
            {"name": "Coca Cola 500ml", "quantity": 2.0, "unit": "bottle", "price": 12.0},
        ],
        "total_amount": 147.0,
        "low_confidence_fields": [],
    },
}


class MockOcrProvider:
    def extract_purchase_receipt(self, media_input: OcrMediaInput) -> OcrExtraction:
        fixture = _MOCK_RECEIPT_FIXTURES.get(media_input.media_id, _MOCK_RECEIPT_FIXTURES["receipt_demo"])

        line_items = [
            OcrExtractedLineItem(
                item_name=item["name"],
                quantity=item["quantity"],
                unit=item["unit"],
                price=item["price"],
            )
            for item in fixture["items"]
        ]

        return OcrExtraction(
            document_type=fixture["document_type"],
            provider_name=fixture["provider_name"],
            raw_text=fixture["raw_text"],
            line_items=line_items,
            total_amount=fixture["total_amount"],
            low_confidence_fields=list(fixture["low_confidence_fields"]),
            used_fallback=False,
            raw_payload={"items": list(fixture["items"]), "total_amount": fixture["total_amount"]},
        )
