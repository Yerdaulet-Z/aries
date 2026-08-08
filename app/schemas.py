from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict

from app.models import AnalysisStatus, Sentiment


# --- Response schemas ---


class ArticleResponse(BaseModel):
    """Full article representation returned by all endpoints."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: Optional[str] = None
    content: Optional[str] = None
    url: str
    image_url: Optional[str] = None
    source_name: str
    published_at: datetime

    analysis_status: AnalysisStatus
    summary: Optional[str] = None
    sentiment: Optional[Sentiment] = None
    sentiment_score: Optional[float] = None
    analysis_error: Optional[str] = None

    created_at: datetime
    updated_at: datetime


# --- Internal schemas (not exposed via API) ---


class AnalysisResult(BaseModel):
    """Structured output parsed from OpenAI response."""

    summary: str
    sentiment: Sentiment
    sentiment_score: float
