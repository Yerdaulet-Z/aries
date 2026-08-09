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
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.schema import ForeignKey

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

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )

    title: Mapped[str] = mapped_column(String(512), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    url: Mapped[str] = mapped_column(String(2048), unique=True, nullable=False)
    image_url: Mapped[Optional[str]] = mapped_column(String(2048), nullable=True)
    source_name: Mapped[str] = mapped_column(String(255), nullable=False)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)

    analysis_status: Mapped[AnalysisStatus] = mapped_column(
        Enum(AnalysisStatus, name="analysis_status_enum", create_type=False),
        default=AnalysisStatus.PENDING,
        nullable=False,
    )
    
    ai_summary: Mapped[Optional["AISummary"]] = relationship(
        "AISummary", back_populates="article", cascade="all, delete-orphan"
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), server_default=func.timezone('utc', func.now()), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), server_default=func.timezone('utc', func.now()), nullable=False
    )

    __table_args__ = (
        Index("ix_articles_published_at_desc", published_at.desc()),
        Index("ix_articles_status", "analysis_status"),
    )

class AISummary(Base):
    __tablename__ = "ai_summary"

    article_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("articles.id", ondelete="CASCADE"), primary_key=True
    )
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    sentiment: Mapped[Optional[Sentiment]] = mapped_column(
        Enum(Sentiment, name="sentiment_enum", create_type=False), nullable=True
    )
    sentiment_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    analysis_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ai_raw_response: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    article: Mapped["Article"] = relationship("Article", back_populates="ai_summary")
