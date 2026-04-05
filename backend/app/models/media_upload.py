from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class MediaUpload(Base):
    __tablename__ = "media_uploads"

    media_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    shop_id: Mapped[str] = mapped_column(ForeignKey("shops.shop_id"), nullable=False)
    uploader_actor_type: Mapped[str] = mapped_column(String(16), nullable=False)
    uploader_actor_id: Mapped[str] = mapped_column(String(40), nullable=False)
    media_type: Mapped[str] = mapped_column(String(24), nullable=False)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(120), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer(), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    upload_url: Mapped[str] = mapped_column(String(255), nullable=False)
    public_url: Mapped[str] = mapped_column(String(255), nullable=False)
    checksum_sha256: Mapped[str | None] = mapped_column(String(128), nullable=True)
    uploaded_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False)

    shop = relationship("Shop")
