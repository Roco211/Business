from app.models import V2Confirmation


def _coerce_object_dict(value: object) -> dict[str, object]:
    if isinstance(value, dict):
        return value
    return {}


def _normalize_optional_string(value: object) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def build_v2_confirmation_source_payload(
    confirmation: V2Confirmation,
    *,
    default_source_type: str | None = None,
    default_source_id: str | None = None,
) -> dict[str, str | None]:
    resolution_payload = _coerce_object_dict(confirmation.resolution_payload)
    resolved_fields = _coerce_object_dict(resolution_payload.get("fields"))
    draft_payload = _coerce_object_dict(confirmation.draft_payload)

    source_type = (
        _normalize_optional_string(resolved_fields.get("source_type"))
        or _normalize_optional_string(draft_payload.get("source_type"))
        or default_source_type
    )
    source_document_id = (
        _normalize_optional_string(resolved_fields.get("source_document_id"))
        or _normalize_optional_string(draft_payload.get("source_document_id"))
    )
    source_media_asset_id = (
        _normalize_optional_string(resolved_fields.get("source_media_asset_id"))
        or _normalize_optional_string(draft_payload.get("source_media_asset_id"))
    )

    return {
        "source_type": source_type,
        "source_id": source_document_id or default_source_id,
        "source_document_id": source_document_id,
        "source_media_asset_id": source_media_asset_id,
    }
