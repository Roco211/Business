from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.services.v2_time import utc_now_naive


class V2MediaAsset(Base):
    __tablename__ = "v2_media_assets"

    media_asset_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("v2_tenants.tenant_id"), nullable=False, index=True)
    shop_id: Mapped[str] = mapped_column(ForeignKey("v2_shops.shop_id"), nullable=False, index=True)
    context_session_id: Mapped[str] = mapped_column(
        ForeignKey("v2_context_sessions.context_session_id"),
        nullable=False,
        index=True,
    )
    uploaded_by_account_id: Mapped[str] = mapped_column(
        ForeignKey("v2_accounts.account_id"),
        nullable=False,
        index=True,
    )
    media_type: Mapped[str] = mapped_column(String(32), nullable=False)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(120), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer(), nullable=False)
    storage_provider: Mapped[str] = mapped_column(String(32), nullable=False)
    object_key: Mapped[str] = mapped_column(String(255), nullable=False)
    upload_url: Mapped[str] = mapped_column(String(255), nullable=False)
    public_url: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    checksum_sha256: Mapped[str | None] = mapped_column(String(128), nullable=True)
    metadata_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    uploaded_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False, default=utc_now_naive)
    updated_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False, default=utc_now_naive)


class V2Document(Base):
    __tablename__ = "v2_documents"

    document_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("v2_tenants.tenant_id"), nullable=False, index=True)
    shop_id: Mapped[str] = mapped_column(ForeignKey("v2_shops.shop_id"), nullable=False, index=True)
    context_session_id: Mapped[str] = mapped_column(
        ForeignKey("v2_context_sessions.context_session_id"),
        nullable=False,
        index=True,
    )
    media_asset_id: Mapped[str] = mapped_column(
        ForeignKey("v2_media_assets.media_asset_id"),
        nullable=False,
        index=True,
    )
    model_call_log_id: Mapped[str | None] = mapped_column(
        ForeignKey("v2_model_call_logs.model_call_log_id"),
        nullable=True,
        index=True,
    )
    created_by_account_id: Mapped[str] = mapped_column(
        ForeignKey("v2_accounts.account_id"),
        nullable=False,
        index=True,
    )
    document_type: Mapped[str] = mapped_column(String(32), nullable=False)
    extraction_status: Mapped[str] = mapped_column(String(24), nullable=False)
    extracted_fields: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    confidence_summary: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False, default=utc_now_naive)
    updated_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False, default=utc_now_naive)


class V2ModelCallLog(Base):
    __tablename__ = "v2_model_call_logs"

    model_call_log_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("v2_tenants.tenant_id"), nullable=False, index=True)
    shop_id: Mapped[str] = mapped_column(ForeignKey("v2_shops.shop_id"), nullable=False, index=True)
    context_session_id: Mapped[str] = mapped_column(
        ForeignKey("v2_context_sessions.context_session_id"),
        nullable=False,
        index=True,
    )
    requested_by_account_id: Mapped[str] = mapped_column(
        ForeignKey("v2_accounts.account_id"),
        nullable=False,
        index=True,
    )
    media_asset_id: Mapped[str | None] = mapped_column(
        ForeignKey("v2_media_assets.media_asset_id"),
        nullable=True,
        index=True,
    )
    task_run_id: Mapped[str | None] = mapped_column(ForeignKey("v2_task_runs.task_run_id"), nullable=True, index=True)
    conversation_session_id: Mapped[str | None] = mapped_column(
        ForeignKey("v2_conversation_sessions.session_id"),
        nullable=True,
        index=True,
    )
    provider_type: Mapped[str] = mapped_column(String(32), nullable=False)
    provider_key: Mapped[str] = mapped_column(String(64), nullable=False)
    model_name: Mapped[str] = mapped_column(String(120), nullable=False)
    operation_type: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    request_payload: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    response_payload: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer(), nullable=True)
    cost_micros: Mapped[int | None] = mapped_column(Integer(), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False, default=utc_now_naive)
