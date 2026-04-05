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
            f"Mock runtime query processed: {normalized_transcript or 'query'}",
            "Mock runtime: stock query accepted. Fixture inventory shows low stock for the requested item.",
        )
    if task_type == "photo-stock-query":
        item_name = str(normalized_payload.get("item_name") or "recognized item")
        stock = normalized_payload.get("stock")
        unit = str(normalized_payload.get("unit") or "unit")
        return (
            f"Mock runtime photo query processed: {item_name}",
            f"Mock runtime: photo query recognized {item_name}. Current stock: {stock} {unit}.",
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
            f"Mock runtime receipt OCR processed: total {total_amount}",
            f"Mock runtime: receipt OCR completed. Total amount: {total_amount}.{low_confidence_suffix}",
        )

    return (
        f"Mock runtime stock-in intent captured: {normalized_transcript or 'stock-in'}",
        "Mock runtime: stock-in intent accepted. Inventory writes are deferred to later confirmation and inventory phases.",
    )


def summarize_failed_task(
    *,
    error_code: str,
    error_message: str,
) -> tuple[str, str]:
    return (
        f"Runtime failed with {error_code}",
        f"Mock runtime could not process this task: {error_message}",
    )
