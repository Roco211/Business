from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class SessionRecord(Base):
    __tablename__ = "sessions"

    session_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    shop_id: Mapped[str] = mapped_column(ForeignKey("shops.shop_id"), nullable=False)
    session_type: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    participants: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    last_event_seq: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    last_message_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False)

    shop = relationship("Shop")
