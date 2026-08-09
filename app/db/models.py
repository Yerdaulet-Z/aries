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
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"), doc="Unique identifier for the article"
    )

    title: Mapped[str] = mapped_column(String(512), nullable=False, doc="Headline of the news article")
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True, doc="Short description or excerpt provided by the source")
    content: Mapped[Optional[str]] = mapped_column(Text, nullable=True, doc="Full text content of the article")
    url: Mapped[str] = mapped_column(String(2048), unique=True, nullable=False, doc="Original URL to the article")
    image_url: Mapped[Optional[str]] = mapped_column(String(2048), nullable=True, doc="URL of the main image associated with the article")
    source_name: Mapped[str] = mapped_column(String(255), nullable=False, doc="Name of the publisher or news source")
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False, doc="Date and time the article was published (UTC)")

    analysis_status: Mapped[AnalysisStatus] = mapped_column(
        Enum(AnalysisStatus, name="analysis_status_enum", create_type=False),
        default=AnalysisStatus.PENDING,
        nullable=False,
        doc="Current state of the AI analysis for this article"
    )
    
    ai_summary: Mapped[Optional["AISummary"]] = relationship(
        "AISummary", back_populates="article", cascade="all, delete-orphan", doc="Associated AI analysis results"
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), server_default=func.timezone('utc', func.now()), nullable=False, doc="Timestamp when the record was created"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), server_default=func.timezone('utc', func.now()), nullable=False, doc="Timestamp when the record was last updated"
    )

    __table_args__ = (
        Index("ix_articles_published_at_desc", published_at.desc()),
        Index("ix_articles_status", "analysis_status"),
    )

class AISummary(Base):
    __tablename__ = "ai_summary"

    article_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("articles.id", ondelete="CASCADE"), primary_key=True, doc="Foreign key referencing the parent article"
    )
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True, doc="AI-generated summary of the article")
    sentiment: Mapped[Optional[Sentiment]] = mapped_column(
        Enum(Sentiment, name="sentiment_enum", create_type=False), nullable=True, doc="Overall sentiment classification (POSITIVE, NEUTRAL, NEGATIVE)"
    )
    sentiment_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True, doc="Numerical score of the sentiment, typically between 0 and 1 or -1 and 1")
    analysis_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True, doc="Error message if the AI analysis failed")
    ai_raw_response: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True, doc="Raw JSON response payload from the AI service")

    article: Mapped["Article"] = relationship("Article", back_populates="ai_summary")
