from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models import AnalysisStatus, Sentiment

class ArticleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
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
    ai_raw_response: Optional[dict] = None

    created_at: datetime
    updated_at: datetime

class AnalysisResult(BaseModel):
    summary: str
    sentiment: Sentiment
    sentiment_score: float
