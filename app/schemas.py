from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models import AnalysisStatus, Sentiment


class SearchArticlesQuery(BaseModel):
    q: str = Field(..., description="Query to search on GNews")
    max_results: int = Field(10, ge=1, le=10)
    lang: str = Field("en", description="Language code (e.g. 'en')")
    country: Optional[str] = Field(None, description="Country code (e.g. 'us')")
    sortby: Optional[str] = Field(None, description="'publishedAt' or 'relevance'")
    from_date: Optional[str] = Field(None, description="UTC ISO format date (e.g. '2023-01-01T00:00:00Z')")
    to_date: Optional[str] = Field(None, description="UTC ISO format date (e.g. '2023-01-01T00:00:00Z')")


class ListArticlesQuery(BaseModel):
    q: Optional[str] = Field(None, description="Full-text search on DB")
    status: Optional[AnalysisStatus] = Field(None, description="Filter by status")
    start_date: Optional[datetime] = Field(None)
    end_date: Optional[datetime] = Field(None)
    limit: int = Field(20, ge=1, le=100)
    offset: int = Field(0, ge=0)

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
