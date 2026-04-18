from datetime import datetime

from pydantic import BaseModel


class V2CreateMediaAssetRequest(BaseModel):
    media_type: str
    file_name: str
    content_type: str
    size_bytes: int


class V2CreateMediaAssetData(BaseModel):
    media_asset_id: str
    status: str
    upload_url: str
    public_url: str


class V2CompleteMediaAssetRequest(BaseModel):
    checksum_sha256: str
    size_bytes: int


class V2CompleteMediaAssetData(BaseModel):
    media_asset_id: str
    status: str


class V2MediaAssetData(BaseModel):
    media_asset_id: str
    tenant_id: str
    shop_id: str
    context_session_id: str
    uploaded_by_account_id: str
    media_type: str
    file_name: str
    content_type: str
    size_bytes: int
    storage_provider: str
    object_key: str
    public_url: str
    status: str
    checksum_sha256: str | None
    uploaded_at: datetime | None
    created_at: datetime
    updated_at: datetime


class V2CreateDocumentRequest(BaseModel):
    media_asset_id: str
    model_call_log_id: str | None = None
    document_type: str
    extraction_status: str
    extracted_fields: dict[str, object]
    confidence_summary: dict[str, object]


class V2DocumentData(BaseModel):
    document_id: str
    media_asset_id: str
    model_call_log_id: str | None
    document_type: str
    extraction_status: str
    extracted_fields: dict[str, object]
    confidence_summary: dict[str, object]
    created_at: datetime
    updated_at: datetime
