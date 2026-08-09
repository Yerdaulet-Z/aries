from datetime import datetime
from typing import Optional, Union
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.db.models import AnalysisStatus, Sentiment
import enum

class SortBy(str, enum.Enum):
    PUBLISHED_AT = "publishedAt"
    RELEVANCE = "relevance"


class VaultSortBy(str, enum.Enum):
    DEFAULT = "default"
    DATE_DESC = "date_desc"
    DATE_ASC = "date_asc"
    SCORE_DESC = "score_desc"
    SCORE_ASC = "score_asc"


class SearchArticlesQuery(BaseModel):
    q: str = Field(..., max_length=100, description="Query to search on GNews")
    max_results: int = Field(10, ge=1, le=10)
    lang: str = Field("en", min_length=2, max_length=2, description="Language code (e.g. 'en')")
    country: Optional[str] = Field(None, description="Country code (e.g. 'us')")
    sortby: Optional[Union[SortBy, str]] = Field(None, description="'publishedAt' or 'relevance'")
    from_date: Optional[datetime] = Field(None, description="UTC ISO format date (e.g. '2023-01-01T00:00:00Z')")
    to_date: Optional[datetime] = Field(None, description="UTC ISO format date (e.g. '2023-01-01T00:00:00Z')")

    @field_validator("country", "sortby", mode="before")
    @classmethod
    def empty_str_to_none_search(cls, v):
        if not v or v == "":
            return None
        return v

    @model_validator(mode='after')
    def check_dates(self) -> 'SearchArticlesQuery':
        if self.from_date and self.to_date and self.from_date > self.to_date:
            raise ValueError('from_date cannot be after to_date')
        return self


class ListArticlesQuery(BaseModel):
    q: Optional[str] = Field(None, max_length=100, description="Full-text search on DB")
    status: Optional[Union[AnalysisStatus, str]] = Field(None, description="Filter by status")
    sentiment: Optional[Union[Sentiment, str]] = Field(None, description="Filter by sentiment")
    min_score: Optional[float] = Field(None, ge=-1.0, le=1.0)
    max_score: Optional[float] = Field(None, ge=-1.0, le=1.0)
    sort_by: Union[VaultSortBy, str] = Field(VaultSortBy.DEFAULT)
    start_date: Optional[datetime] = Field(None)
    end_date: Optional[datetime] = Field(None)
    limit: int = Field(20, ge=1, le=100)
    offset: int = Field(0, ge=0)

    @field_validator("q", mode="before")
    @classmethod
    def parse_q(cls, v):
        if not v or v == "":
            return None
        return v

    @field_validator("status", mode="before")
    @classmethod
    def parse_status(cls, v):
        if not v or v == "":
            return None
        if isinstance(v, AnalysisStatus):
            return v
        try:
            return AnalysisStatus(v)
        except ValueError:
            raise ValueError(f"Invalid status: {v}")

    @field_validator("sentiment", mode="before")
    @classmethod
    def parse_sentiment(cls, v):
        if not v or v == "":
            return None
        if isinstance(v, Sentiment):
            return v
        try:
            return Sentiment(v)
        except ValueError:
            raise ValueError(f"Invalid sentiment: {v}")

    @field_validator("sort_by", mode="before")
    @classmethod
    def parse_sort_by(cls, v):
        if not v or v == "":
            return VaultSortBy.DEFAULT
        if isinstance(v, VaultSortBy):
            return v
        try:
            return VaultSortBy(v)
        except ValueError:
            return VaultSortBy.DEFAULT

    @model_validator(mode='after')
    def check_dates(self) -> 'ListArticlesQuery':
        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValueError('start_date cannot be after end_date')
        return self

class AISummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    summary: Optional[str] = Field(None, description="AI-generated comprehensive summary of the article")
    sentiment: Optional[Sentiment] = Field(None, description="Overall sentiment category (POSITIVE, NEUTRAL, NEGATIVE)")
    sentiment_score: Optional[float] = Field(None, description="Granular sentiment score from -1.0 (highly negative) to 1.0 (highly positive)")
    analysis_error: Optional[str] = Field(None, description="Error message if the AI analysis failed")
    ai_raw_response: Optional[dict] = Field(None, description="Raw structured JSON response output from the OpenAI API")

class ArticleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(..., description="Unique identifier for the article")
    title: str = Field(..., description="Headline or title of the article")
    description: Optional[str] = Field(None, description="Short summary or excerpt provided by the news source")
    content: Optional[str] = Field(None, description="Full or partial content of the article")
    url: str = Field(..., description="Original URL to the full article")
    image_url: Optional[str] = Field(None, description="URL to the article's featured image")
    source_name: str = Field(..., description="Name of the publisher (e.g., 'Reuters', 'BBC News')")
    published_at: datetime = Field(..., description="Publication timestamp in UTC")

    analysis_status: AnalysisStatus = Field(..., description="Current lifecycle state of the AI analysis job")
    ai_summary: Optional[AISummaryResponse] = Field(None, description="AI analysis summary and sentiment, if available")

    created_at: datetime = Field(..., description="Timestamp when the article was first indexed into the database")
    updated_at: datetime = Field(..., description="Timestamp when the article record was last modified")

class AnalysisResult(BaseModel):
    summary: str = Field(..., description="A concise, factual, and well-structured summary of the article's core narrative.")
    sentiment: Sentiment = Field(..., description="The overall sentiment of the article towards its main subject.")
    sentiment_score: float = Field(..., description="A float between -1.0 and 1.0 representing the intensity of the sentiment. E.g., -0.9 is extremely negative, 0.0 is completely neutral.")
