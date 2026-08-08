from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models import AnalysisStatus, Sentiment
import enum

class SortBy(str, enum.Enum):
    PUBLISHED_AT = "publishedAt"
    RELEVANCE = "relevance"


class SearchArticlesQuery(BaseModel):
    q: str = Field(..., min_length=1, max_length=100, description="Query to search on GNews")
    max_results: int = Field(10, ge=1, le=10)
    lang: str = Field("en", min_length=2, max_length=2, description="Language code (e.g. 'en')")
    country: Optional[str] = Field(None, min_length=2, max_length=2, description="Country code (e.g. 'us')")
    sortby: Optional[SortBy] = Field(None, description="'publishedAt' or 'relevance'")
    from_date: Optional[datetime] = Field(None, description="UTC ISO format date (e.g. '2023-01-01T00:00:00Z')")
    to_date: Optional[datetime] = Field(None, description="UTC ISO format date (e.g. '2023-01-01T00:00:00Z')")

    @model_validator(mode='after')
    def check_dates(self) -> 'SearchArticlesQuery':
        if self.from_date and self.to_date and self.from_date > self.to_date:
            raise ValueError('from_date cannot be after to_date')
        return self


class ListArticlesQuery(BaseModel):
    q: Optional[str] = Field(None, min_length=1, max_length=100, description="Full-text search on DB")
    status: Optional[AnalysisStatus] = Field(None, description="Filter by status")
    start_date: Optional[datetime] = Field(None)
    end_date: Optional[datetime] = Field(None)
    limit: int = Field(20, ge=1, le=100)
    offset: int = Field(0, ge=0)

    @model_validator(mode='after')
    def check_dates(self) -> 'ListArticlesQuery':
        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValueError('start_date cannot be after end_date')
        return self

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
