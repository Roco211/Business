def summarize_completed_task(
    *,
    task_type: str,
    transcript: str | None,
) -> tuple[str, str]:
    normalized_transcript = (transcript or "").strip()

    if task_type == "voice-stock-query":
        return (
            f"Mock runtime query processed: {normalized_transcript or 'query'}",
            "Mock runtime: stock query accepted. Fixture inventory shows low stock for the requested item.",
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
