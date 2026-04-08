def summarize_completed_task(
    *,
    task_type: str,
    transcript: str | None,
    payload: dict[str, object] | None = None,
) -> tuple[str, str]:
    normalized_transcript = (transcript or "").strip()
    normalized_payload = payload or {}

    if task_type == "voice-stock-query":
        return (
            f"Stock query processed: {normalized_transcript or 'query'}",
            "Stock query accepted. Inventory currently shows low stock for the requested item.",
        )
    if task_type == "photo-stock-query":
        item_name = str(normalized_payload.get("item_name") or "recognized item")
        stock = normalized_payload.get("stock")
        unit = str(normalized_payload.get("unit") or normalized_payload.get("packaging_hint") or "unit")
        return (
            f"Photo stock query processed: {item_name}",
            f"Photo query recognized {item_name}. Current stock: {stock} {unit}.",
        )
    if task_type == "receipt-ocr":
        total_amount = normalized_payload.get("total_amount") or "unknown"
        low_confidence_fields = normalized_payload.get("low_confidence_fields") or []
        low_confidence_suffix = (
            f" Low confidence: {', '.join(str(value) for value in low_confidence_fields)}."
            if low_confidence_fields
            else ""
        )
        return (
            f"Receipt OCR processed: total {total_amount}",
            f"Receipt OCR completed. Total amount: {total_amount}.{low_confidence_suffix}",
        )

    return (
        f"Stock-in intent captured: {normalized_transcript or 'stock-in'}",
        "Stock-in intent accepted. Inventory writes are deferred to later confirmation and inventory phases.",
    )


def summarize_failed_task(
    *,
    error_code: str,
    error_message: str,
) -> tuple[str, str]:
    return (
        f"Runtime failed with {error_code}",
        f"Runtime could not process this task: {error_message}",
    )
