import enum
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    DateTime,
    Enum,
    Float,
    Index,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

class Base(DeclarativeBase):
    pass

class AnalysisStatus(str, enum.Enum):
    PENDING = "PENDING"
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

class Sentiment(str, enum.Enum):
    POSITIVE = "POSITIVE"
    NEUTRAL = "NEUTRAL"
    NEGATIVE = "NEGATIVE"

class Article(Base):
    __tablename__ = "articles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    title: Mapped[str] = mapped_column(String(512), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    url: Mapped[str] = mapped_column(String(2048), unique=True, nullable=False)
    image_url: Mapped[Optional[str]] = mapped_column(String(2048), nullable=True)
    source_name: Mapped[str] = mapped_column(String(255), nullable=False)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    analysis_status: Mapped[AnalysisStatus] = mapped_column(
        Enum(AnalysisStatus, name="analysis_status_enum", create_type=False),
        default=AnalysisStatus.PENDING,
        nullable=False,
    )
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    sentiment: Mapped[Optional[Sentiment]] = mapped_column(
        Enum(Sentiment, name="sentiment_enum", create_type=False), nullable=True
    )
    sentiment_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    analysis_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ai_raw_response: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_articles_published_at_desc", published_at.desc()),
        Index("ix_articles_status", "analysis_status"),
    )
