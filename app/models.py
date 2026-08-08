import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    DateTime,
    Enum,
    Float,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Shared base for all ORM models."""
    pass


class AnalysisStatus(str, enum.Enum):
    """Lifecycle states for article AI analysis."""
    PENDING = "PENDING"         # Freshly ingested, not yet queued
    QUEUED = "QUEUED"           # Published to RabbitMQ
    PROCESSING = "PROCESSING"  # Worker acquired, calling OpenAI
    COMPLETED = "COMPLETED"    # Summary + sentiment written
    FAILED = "FAILED"          # Error captured


class Sentiment(str, enum.Enum):
    """Sentiment classification labels."""
    POSITIVE = "POSITIVE"
    NEUTRAL = "NEUTRAL"
    NEGATIVE = "NEGATIVE"


class Article(Base):
    """
    Stores news articles fetched from external APIs along with
    their AI-generated analysis results (summary + sentiment).
    """
    __tablename__ = "articles"

    # --- Primary key ---
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # --- Article metadata (from GNews) ---
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    url: Mapped[str] = mapped_column(String(2048), unique=True, nullable=False)
    image_url: Mapped[Optional[str]] = mapped_column(String(2048), nullable=True)
    source_name: Mapped[str] = mapped_column(String(255), nullable=False)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # --- AI analysis results ---
    analysis_status: Mapped[AnalysisStatus] = mapped_column(
        Enum(AnalysisStatus, name="analysis_status_enum"),
        default=AnalysisStatus.PENDING,
        nullable=False,
    )
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    sentiment: Mapped[Optional[Sentiment]] = mapped_column(
        Enum(Sentiment, name="sentiment_enum"), nullable=True
    )
    sentiment_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    analysis_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # --- Timestamps (updated_at managed by DB trigger, see database.py) ---
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

    def __repr__(self) -> str:
        return f"<Article id={self.id} title='{self.title[:40]}...' status={self.analysis_status}>"
